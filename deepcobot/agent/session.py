"""Agent 会话管理"""

from pathlib import Path
from typing import Any, Callable, Awaitable

from loguru import logger

from deepcobot.config import Config
from deepcobot.agent.factory import create_agent_async
from deepcobot.agent.utils import sanitize_string


class AgentSession:
    """Agent 会话管理"""

    def __init__(self, config: Config):
        self.config = config
        self._graph = None
        self._checkpointer = None
        self._backend = None
        self._workspace: Path | None = None
        self._thread_id: str = "default"
        # 审批回调函数
        self._approval_callback: Callable[[list[dict]], Awaitable[list[dict]]] | None = None
        # 事件回调函数
        self._event_callback: Callable[[dict], Awaitable[None]] | None = None

    async def _ensure_initialized(self):
        """确保 Agent 已初始化（异步）"""
        if self._graph is None:
            resources = await create_agent_async(self.config)
            self._graph = resources["graph"]
            self._checkpointer = resources["checkpointer"]
            self._backend = resources["backend"]
            self._workspace = resources["workspace"]

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
            }
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

        if self._approval_callback is None:
            logger.warning("Interrupt found but no approval callback set")
            return False, None

        final_state = None

        # 循环处理所有中断，直到没有新的中断
        while True:
            # 收集所有中断的值
            action_requests = []
            for interrupt in state.interrupts:
                interrupt_value = interrupt.value
                if isinstance(interrupt_value, dict) and "action_requests" in interrupt_value:
                    action_requests.extend(interrupt_value["action_requests"])

            if not action_requests:
                break

            # 调用回调获取用户决策
            decisions = await self._approval_callback(action_requests)

            # 使用 Command 恢复执行，使用流式 API 以触发事件回调
            resume_value = {"decisions": decisions}
            final_state = None
            async for event in self._graph.astream_events(
                Command(resume=resume_value),
                config=self.get_thread_config(),
                version="v1",
            ):
                # 调用事件回调以显示 spinner
                if self._event_callback:
                    await self._event_callback(event)

                # 保存最终状态
                event_type = event.get("event")
                if event_type == "on_chain_end" and event.get("name") == "LangGraph":
                    output = event.get("data", {}).get("output")
                    if isinstance(output, dict) and "messages" in output:
                        final_state = output

            # 检查是否有新的中断
            state = await self._get_state()
            if not state.interrupts:
                break

        # 如果没有从事件中获取到最终状态，从 state.values 获取
        if final_state is None or "messages" not in final_state:
            state = await self._get_state()
            final_state = state.values

        return True, final_state

    async def invoke(self, message: str) -> str:
        """
        调用 Agent 处理消息。

        Args:
            message: 用户消息

        Returns:
            Agent 响应
        """
        await self._ensure_initialized()
        graph = self._graph
        thread_config = self.get_thread_config()

        # 使用流式事件处理
        final_state = None
        event_count = 0

        async for event in graph.astream_events(
            {"messages": [{"role": "user", "content": message}]} if message else None,
            config=thread_config,
            version="v1",
        ):
            event_count += 1
            event_type = event.get("event")
            event_name = event.get("name", "")

            # 记录工具相关事件
            if "tool" in event_type.lower() or "tool" in event_name.lower():
                logger.debug(f"Tool event #{event_count}: {event_type}, name: {event_name}")

            # 调用事件回调
            if self._event_callback:
                await self._event_callback(event)

        logger.debug(f"astream_events completed, received {event_count} events")

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
            version="v1",
        ):
            yield event

    def reset(self) -> None:
        """重置会话"""
        self._thread_id = "default"