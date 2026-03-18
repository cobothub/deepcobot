"""Web API 渠道实现

提供 HTTP API 接口供外部应用调用。
"""

import asyncio
import json
import uuid
from typing import TYPE_CHECKING, Any

from loguru import logger

from deepcobot.channels.base import BaseChannel
from deepcobot.channels.events import InboundMessage, OutboundMessage

if TYPE_CHECKING:
    from deepcobot.bus.queue import MessageBus


class WebAPIChannel(BaseChannel):
    """
    Web API 渠道实现，提供 HTTP 接口。

    特点：
    - RESTful API
    - 支持 SSE 流式响应
    - 支持 API 认证

    Attributes:
        name: 渠道名称（"web"）
    """

    name = "web"

    def __init__(self, config, bus: "MessageBus"):
        """
        初始化 Web API 渠道。

        Args:
            config: 渠道配置（包含 host, port, api_key, allowed_users）
            bus: 消息总线
        """
        super().__init__(config, bus)
        self.host = getattr(config, "host", "0.0.0.0")
        self.port = getattr(config, "port", 8080)
        self.api_key = getattr(config, "api_key", None)
        self._app = None
        self._server = None
        self._pending_responses: dict[str, asyncio.Future] = {}

    async def start(self) -> None:
        """启动 Web API 服务"""
        try:
            from fastapi import FastAPI, HTTPException, Header
            from fastapi.responses import StreamingResponse
            import uvicorn
        except ImportError:
            raise ImportError(
                "FastAPI not installed. "
                "Install it with: pip install deepcobot[web]"
            )

        self._running = True

        # 创建 FastAPI 应用
        self._app = FastAPI(title="DeepCoBot API")

        # 添加路由
        @self._app.post("/chat")
        async def chat(
            request: dict,
            authorization: str | None = Header(default=None),
        ):
            # API 认证
            if self.api_key:
                if not authorization or authorization != f"Bearer {self.api_key}":
                    raise HTTPException(status_code=401, detail="Unauthorized")

            # 解析请求
            content = request.get("content", "")
            chat_id = request.get("chat_id", str(uuid.uuid4()))
            stream = request.get("stream", False)

            if not content:
                raise HTTPException(status_code=400, detail="Content is required")

            # 处理消息
            if stream:
                return StreamingResponse(
                    self._stream_response(chat_id, content),
                    media_type="text/event-stream",
                )
            else:
                response = await self._process_sync(chat_id, content)
                return {"content": response, "chat_id": chat_id}

        @self._app.get("/health")
        async def health():
            return {"status": "healthy"}

        # 启动服务器
        config = uvicorn.Config(
            self._app,
            host=self.host,
            port=self.port,
            log_level="error",
        )
        self._server = uvicorn.Server(config)

        logger.info(f"Web API server starting on {self.host}:{self.port}")

        try:
            await self._server.serve()
        except Exception as e:
            logger.error(f"Web API server error: {e}")
            self._running = False

    async def stop(self) -> None:
        """停止 Web API 服务"""
        self._running = False

        if self._server:
            self._server.should_exit = True
            self._server = None

        self._app = None
        logger.info("Web API channel stopped")

    async def send(self, msg: OutboundMessage) -> None:
        """
        发送响应（用于流式响应场景）。

        Args:
            msg: 出站消息
        """
        # 检查是否有等待的 Future
        future = self._pending_responses.get(msg.chat_id)
        if future and not future.done():
            future.set_result(msg.content)

    async def send_progress(self, chat_id: str, content: str) -> None:
        """
        发送进度更新。

        Web API 不支持进度指示，忽略。

        Args:
            chat_id: 会话 ID
            content: 进度内容
        """
        pass

    async def _process_sync(self, chat_id: str, content: str) -> str:
        """
        同步处理消息并返回响应。

        Args:
            chat_id: 会话 ID
            content: 消息内容

        Returns:
            响应内容
        """
        # 创建 Future 用于等待响应
        future: asyncio.Future[str] = asyncio.get_event_loop().create_future()
        self._pending_responses[chat_id] = future

        # 发送消息到总线
        await self._handle_message(
            sender_id="web_user",
            chat_id=chat_id,
            content=content,
        )

        # 等待响应（超时 60 秒）
        try:
            return await asyncio.wait_for(future, timeout=60.0)
        except asyncio.TimeoutError:
            return "Request timed out"
        finally:
            self._pending_responses.pop(chat_id, None)

    async def _stream_response(self, chat_id: str, content: str):
        """
        流式响应生成器。

        Args:
            chat_id: 会话 ID
            content: 消息内容

        Yields:
            SSE 事件数据
        """
        # 这个方法需要 Agent 支持流式输出
        # 这里提供一个简化的实现

        # 发送消息到总线
        await self._handle_message(
            sender_id="web_user",
            chat_id=chat_id,
            content=content,
        )

        # 等待响应并分块发送
        try:
            response = await self._process_sync(chat_id, content)

            # 简单分块发送
            chunk_size = 50
            for i in range(0, len(response), chunk_size):
                chunk = response[i:i + chunk_size]
                yield f"data: {json.dumps({'content': chunk})}\n\n"

            yield f"data: {json.dumps({'done': True})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"


def create_fastapi_app(channel: WebAPIChannel) -> "FastAPI":
    """
    创建 FastAPI 应用实例（用于外部部署）。

    Args:
        channel: Web API 渠道实例

    Returns:
        FastAPI 应用
    """
    from fastapi import FastAPI, HTTPException, Header

    app = FastAPI(title="DeepCoBot API")

    @app.post("/chat")
    async def chat(
        request: dict,
        authorization: str | None = Header(default=None),
    ):
        if channel.api_key:
            if not authorization or authorization != f"Bearer {channel.api_key}":
                raise HTTPException(status_code=401, detail="Unauthorized")

        content = request.get("content", "")
        chat_id = request.get("chat_id", str(uuid.uuid4()))

        if not content:
            raise HTTPException(status_code=400, detail="Content is required")

        response = await channel._process_sync(chat_id, content)
        return {"content": response, "chat_id": chat_id}

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    return app