"""Agent 会话管理"""

from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any, Callable, Awaitable

from loguru import logger

from deepcobot.config import Config
from deepcobot.agent.factory import create_agent_async
from deepcobot.agent.utils import sanitize_string
from deepcobot.agent.approval import get_approval_manager


class AgentSession:
    """Agent 会话管理

    支持两种使用场景：
    1. CLI 交互：通过 set_approval_callback 设置交互式审批
    2. Bot 服务：通过 set_send_callback 设置消息发送回调，用于审批交互
    """

    def __init__(self, config: Config):
        self.config = config
        self._graph = None
        self._checkpointer = None
        self._backend = None
        self._workspace: Path | None = None
        self._thread_id: str = "default"
        self._exit_stack: AsyncExitStack | None = None
        # 审批回调函数
        self._approval_callback: Callable[[list[dict]], Awaitable[list[dict]]] | None = None
        # 事件回调函数
        self._event_callback: Callable[[dict], Awaitable[None]] | None = None
        # Bot 场景的消息发送回调（用于审批时发送确认消息）
        self._send_callback: Callable[[str, str], Awaitable[None]] | None = None
        # 审批后结果发送回调（用于 Bot 场景，因为原处理流程已返回 None）
        self._result_callback: Callable[[str], Awaitable[None]] | None = None
        # 渠道信息（用于 Bot 审批场景）
        self._channel: str | None = None
        self._chat_id: str | None = None

    async def _ensure_initialized(self):
        """确保 Agent 已初始化（异步）"""
        if self._graph is None:
            resources = await create_agent_async(self.config)
            self._graph = resources["graph"]
            self._checkpointer = resources["checkpointer"]
            self._backend = resources["backend"]
            self._workspace = resources["workspace"]
            self._exit_stack = resources.get("exit_stack")

    @property
    def graph(self):
        """获取 Agent graph"""
        if self._graph is None:
            # 同步访问时，抛出错误提示
            raise RuntimeError(
                "Agent not initialized. Call 'await session.initialize()' first, "
                "or use an async context."
            )
        return self._graph

    @property
    def checkpointer(self):
        """获取 checkpointer"""
        if self._checkpointer is None:
            raise RuntimeError("Agent not initialized.")
        return self._checkpointer

    @property
    def workspace(self) -> Path:
        """获取工作空间路径"""
        if self._workspace is None:
            # workspace 可以同步初始化
            self._workspace = self.config.agent.workspace
            self._workspace.mkdir(parents=True, exist_ok=True)
        return self._workspace

    def set_thread_id(self, thread_id: str) -> None:
        """设置当前线程 ID"""
        self._thread_id = thread_id

    def get_thread_config(self) -> dict[str, Any]:
        """获取线程配置"""
        return {
            "configurable": {
                "thread_id": self._thread_id,
            },
            "recursion_limit": self.config.agent.recursion_limit,
        }

    def set_approval_callback(
        self, callback: Callable[[list[dict]], Awaitable[list[dict]]]
    ) -> None:
        """设置审批回调函数

        Args:
            callback: 异步回调函数，接收待审批的工具调用列表，
                     返回用户的决策列表
        """
        self._approval_callback = callback

    def set_event_callback(
        self, callback: Callable[[dict], Awaitable[None]]
    ) -> None:
        """设置事件回调函数，用于处理流式事件

        Args:
            callback: 异步回调函数，接收事件字典
        """
        self._event_callback = callback

    def set_send_callback(
        self, callback: Callable[[str, str], Awaitable[None]]
    ) -> None:
        """设置消息发送回调函数（用于 Bot 场景审批）

        Args:
            callback: 异步回调函数，接收 (chat_id, message) 参数
        """
        self._send_callback = callback

    def set_result_callback(
        self, callback: Callable[[str], Awaitable[None]] | None
    ) -> None:
        """设置结果发送回调（审批通过后发送最终结果）

        Args:
            callback: 异步回调函数，接收结果内容
        """
        self._result_callback = callback

    def set_channel_context(self, channel: str, chat_id: str) -> None:
        """设置当前渠道上下文（用于 Bot 场景）

        Args:
            channel: 渠道名称
            chat_id: 会话 ID
        """
        self._channel = channel
        self._chat_id = chat_id

    @property
    def auto_approve(self) -> bool:
        """是否自动审批"""
        return self.config.agent.auto_approve

    async def _get_state(self) -> Any:
        """获取当前状态"""
        return await self._graph.aget_state(self.get_thread_config())

    async def _check_and_handle_interrupt(self) -> tuple[bool, dict | None]:
        """检查并处理中断，循环处理所有可能的中断直到完成

        Returns:
            (是否有中断需要处理, 最终状态)
        """
        from langgraph.types import Command

        state = await self._get_state()
        if not state.interrupts:
            return False, None

        # 有中断，需要处理
        logger.info(f"Found {len(state.interrupts)} interrupt(s)")

        # 如果没有审批回调，根据 auto_approve 配置决定
        if self._approval_callback is None:
            if self.auto_approve:
                # 自动审批所有工具调用
                logger.info("Auto-approving all interrupts")
                decisions = [{"type": "approve"} for _ in state.interrupts]
            else:
                # Bot 场景：如果有发送回调，发送审批请求等待用户回复
                if self._send_callback and self._chat_id:
                    decisions = await self._handle_bot_approval(state.interrupts)
                else:
                    logger.warning("Interrupt found but no approval callback set")
                    return False, None
        else:
            # CLI 场景：使用审批回调
            action_requests = []
            for interrupt in state.interrupts:
                interrupt_value = interrupt.value
                if isinstance(interrupt_value, dict) and "action_requests" in interrupt_value:
                    action_requests.extend(interrupt_value["action_requests"])

            if not action_requests:
                return False, None

            decisions = await self._approval_callback(action_requests)

        final_state = None

        # 使用 Command 恢复执行，使用流式 API 以触发事件回调
        resume_value = {"decisions": decisions}
        async for event in self._graph.astream_events(
            Command(resume=resume_value),
            config=self.get_thread_config(),
            version="v2",
        ):
            # 调用事件回调
            if self._event_callback:
                await self._event_callback(event)

            # 保存最终状态
            event_type = event.get("event")
            if event_type == "on_chain_end" and event.get("name") == "LangGraph":
                output = event.get("data", {}).get("output")
                if isinstance(output, dict) and "messages" in output:
                    final_state = output

        # 检查是否有新的中断（可能需要多轮审批）
        state = await self._get_state()
        if state.interrupts:
            # 递归处理新的中断
            has_more, more_state = await self._check_and_handle_interrupt()
            if has_more and more_state is not None:
                final_state = more_state

        # 如果没有从事件中获取到最终状态，从 state.values 获取
        if final_state is None or "messages" not in final_state:
            state = await self._get_state()
            final_state = state.values

        return True, final_state

    async def _handle_bot_approval(self, interrupts: list) -> list[dict]:
        """处理 Bot 场景的审批请求

        通过发送回调向用户展示审批请求，并等待用户回复。

        Args:
            interrupts: 中断列表

        Returns:
            用户决策列表
        """
        import json

        # 收集所有审批请求
        action_requests = []
        for interrupt in interrupts:
            interrupt_value = interrupt.value
            if isinstance(interrupt_value, dict) and "action_requests" in interrupt_value:
                action_requests.extend(interrupt_value["action_requests"])

        if not action_requests:
            return []

        # 构建审批请求消息
        lines = ["🔔 **审批请求**\n"]
        lines.append(f"有 {len(action_requests)} 个工具调用需要审批：\n")

        for i, req in enumerate(action_requests, 1):
            tool_name = req.get("name", "unknown")
            tool_args = req.get("args", {})
            description = req.get("description", "")

            lines.append(f"**{i}. {tool_name}**")
            if description:
                lines.append(f"   说明: {description}")
            if tool_args:
                args_str = json.dumps(tool_args, ensure_ascii=False, indent=2)
                if len(args_str) > 300:
                    args_str = args_str[:300] + "..."
                lines.append(f"   参数: `{args_str}`")
            lines.append("")

        lines.append("请回复 `y` 批准，`n` 拒绝，或 `a` 全部批准")

        approval_msg = "\n".join(lines)

        # 获取会话标识
        session_key = f"{self._channel}:{self._chat_id}" if self._channel and self._chat_id else self._thread_id

        # 获取审批管理器
        approval_manager = get_approval_manager()

        # 创建审批请求
        request = await approval_manager.create_request(session_key, action_requests)

        # 发送审批请求
        if self._send_callback and self._chat_id:
            await self._send_callback(self._chat_id, approval_msg)

        # 等待用户响应
        logger.info(f"[Approval] Waiting for response from {session_key}")
        decisions = await approval_manager.wait_for_response(request)

        logger.info(f"[Approval] Got {len(decisions)} decisions for {session_key}")
        return decisions

    async def invoke(self, message: str) -> str:
        """
        调用 Agent 处理消息。

        Args:
            message: 用户消息

        Returns:
            Agent 响应
        """
        import time
        import json

        await self._ensure_initialized()
        graph = self._graph
        thread_config = self.get_thread_config()

        logger.debug(f"[Session] Starting invoke for thread: {self._thread_id}")
        logger.debug(f"[Session] User message: {message[:200]}..." if len(message) > 200 else f"[Session] User message: {message}")

        # 使用流式事件处理
        final_state = None
        event_count = 0
        start_time = time.time()
        event_type_list = []
        async for event in graph.astream_events(
            {"messages": [{"role": "user", "content": message}]} if message else None,
            config=thread_config,
            version="v2",
        ):
            event_count += 1
            event_type = event.get("event")
            event_name = event.get("name", "")
            event_data = event.get("data", {})
            if event_type not in event_type_list:
                event_type_list.append(event_type)

            # 详细记录工具调用事件
            if event_type == "on_tool_start":
                tool_input = event_data.get("input", {})
                logger.debug(f"[Tool] >>> {event_name} START")
                if tool_input:
                    try:
                        input_str = json.dumps(tool_input, ensure_ascii=False, indent=2)
                        if len(input_str) > 500:
                            input_str = input_str[:500] + "..."
                        logger.debug(f"[Tool] >>> {event_name} INPUT:\n{input_str}")
                    except Exception:
                        logger.debug(f"[Tool] >>> {event_name} INPUT: {tool_input}")

            elif event_type == "on_tool_end":
                tool_output = event_data.get("output", {})
                logger.debug(f"[Tool] <<< {event_name} END")
                if tool_output:
                    try:
                        output_str = str(tool_output)
                        if len(output_str) > 500:
                            output_str = output_str[:500] + "..."
                        logger.debug(f"[Tool] <<< {event_name} OUTPUT: {output_str}")
                    except Exception:
                        pass

            elif event_type == "on_tool_error":
                error = event_data.get("error", "Unknown error")
                logger.debug(f"[Tool] <<< {event_name} ERROR: {error}")

            # 记录 LLM 事件 (同时支持 on_llm_* 和 on_chat_model_* 两种事件类型)
            elif event_type in ("on_chat_model_start", "on_llm_start"):
                logger.debug(f"[LLM] >>> {event_name} START")
                input_data = event_data.get("input", {})
                if input_data and "messages" in input_data:
                    msg_count = len(input_data.get("messages", []))
                    logger.debug(f"[LLM] >>> {event_name} messages: {msg_count}")

            elif event_type in ("on_chat_model_end", "on_llm_end"):
                logger.debug(f"[LLM] <<< {event_name} END ({time.time() - start_time:.2f}s)")
                output = event_data.get("output", {})
                if output:
                    # 记录 token 使用情况
                    usage = output.get("usage_metadata") if isinstance(output, dict) else None
                    if usage:
                        logger.debug(f"[LLM] <<< tokens: input={usage.get('input_tokens')}, output={usage.get('output_tokens')}")

            elif event_type in ("on_chat_model_stream", "on_llm_stream"):
                # LLM 流式输出，只在第一个 chunk 时记录
                chunk = event_data.get("chunk", {})
                if chunk and event_count % 20 == 0:  # 每 20 个 chunk 记录一次
                    logger.debug(f"[LLM] ... streaming ({event_count} chunks)")

            # 记录链结束
            elif event_type == "on_chain_end" and event_name == "LangGraph":
                logger.debug(f"[Chain] LangGraph END, total events: {event_count}")

            # 调用事件回调
            if self._event_callback:
                await self._event_callback(event)

        logger.debug(f"[Session] astream_events completed in {time.time() - start_time:.2f}s, received {event_count} events. event_types: {event_type_list}")

        # 流结束后检查是否有中断
        has_interrupt, resume_final_state = await self._check_and_handle_interrupt()
        if has_interrupt and resume_final_state is not None:
            final_state = resume_final_state

        # 总是从 state.values 获取最终状态（因为 on_chain_end 的 output 可能不包含 messages）
        if final_state is None or "messages" not in final_state:
            state = await self._get_state()
            final_state = state.values

        # 提取最后一条助手消息
        if final_state and "messages" in final_state:
            for msg in reversed(final_state["messages"]):
                # 处理 langchain 消息对象（AIMessage, HumanMessage 等）
                msg_type = type(msg).__name__
                if msg_type == "AIMessage":
                    content = msg.content
                    # 处理 content 为 None 的情况（API 错误）
                    if content is None:
                        logger.error("API returned None content, possibly an authentication error")
                        return "Error: API returned empty response. Please check your API key and endpoint."
                    # OpenAI Responses API 返回的是列表格式
                    if isinstance(content, list):
                        # 提取所有 text 类型的内容
                        texts = []
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "text":
                                texts.append(item.get("text", ""))
                        return sanitize_string("\n".join(texts)) if texts else ""
                    return sanitize_string(str(content)) if content else ""
                # 兼容字典格式的消息
                elif isinstance(msg, dict) and msg.get("role") == "assistant":
                    return sanitize_string(msg.get("content", "") or "")

        return ""

    async def stream(self, message: str):
        """
        流式调用 Agent。

        Args:
            message: 用户消息

        Yields:
            流式响应事件
        """
        graph = self.graph
        thread_config = self.get_thread_config()

        async for event in graph.astream_events(
            {"messages": [{"role": "user", "content": message}]},
            config=thread_config,
            version="v2",
        ):
            yield event

    def reset(self) -> None:
        """重置会话（仅重置 thread_id，不清除历史）"""
        self._thread_id = "default"

    async def clear_history(self, thread_id: str | None = None) -> None:
        """
        清除指定会话的历史记录

        Args:
            thread_id: 要清除的会话 ID，如果为 None 则清除当前会话
        """
        await self._ensure_initialized()

        target_thread = thread_id or self._thread_id

        # 删除 checkpointer 中保存的状态
        await self._checkpointer.adelete_thread(target_thread)
        logger.info(f"[Session] Cleared history for thread: {target_thread}")

    async def close(self) -> None:
        """关闭会话并清理资源"""
        if self._exit_stack is not None:
            await self._exit_stack.aclose()
            self._exit_stack = None
            logger.info("[Session] Closed MCP connections")