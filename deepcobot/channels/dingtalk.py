"""钉钉渠道实现

使用 dingtalk-stream 库实现钉钉机器人渠道。
支持 AI Card 进度反馈。
"""

import asyncio
import json
import threading
import time
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import httpx
from loguru import logger

from deepcobot.channels.base import BaseChannel
from deepcobot.channels.events import InboundMessage, OutboundMessage

if TYPE_CHECKING:
    from deepcobot.bus.queue import MessageBus

# AI Card 状态常量
CARD_PROCESSING = "1"
CARD_INPUTING = "2"
CARD_FINISHED = "3"
CARD_FAILED = "5"

# AI Card 配置
AI_CARD_MIN_INTERVAL_SECONDS = 0.6  # 最小更新间隔
AI_CARD_PROCESSING_TEXT = "处理中..."

# 延迟导入标记
_DINGTALK_AVAILABLE = False
_CallbackHandler = object
_CallbackMessage = None
_AckMessage = None
_ChatbotMessage = None
_Credential = None
_DingTalkStreamClient = None


def _ensure_dingtalk():
    """确保 dingtalk-stream 已安装"""
    global _DINGTALK_AVAILABLE, _CallbackHandler, _CallbackMessage, _AckMessage
    global _ChatbotMessage, _Credential, _DingTalkStreamClient

    if _DINGTALK_AVAILABLE:
        return True

    try:
        from dingtalk_stream import (
            AckMessage,
            CallbackHandler,
            CallbackMessage,
            Credential,
            DingTalkStreamClient,
        )
        from dingtalk_stream.chatbot import ChatbotMessage

        _CallbackHandler = CallbackHandler
        _CallbackMessage = CallbackMessage
        _AckMessage = AckMessage
        _ChatbotMessage = ChatbotMessage
        _Credential = Credential
        _DingTalkStreamClient = DingTalkStreamClient
        _DINGTALK_AVAILABLE = True
        return True
    except ImportError:
        return False


@dataclass
class ActiveCard:
    """活跃的 AI Card"""

    card_instance_id: str
    access_token: str
    conversation_id: str
    created_at: int
    last_updated: int
    state: str
    last_content: str = ""


class DingTalkChannel(BaseChannel):
    """
    钉钉渠道实现，使用 Stream 模式连接。

    特点：
    - 无需公网 IP
    - 支持 Stream 模式
    - 支持 AI Card 进度反馈（类似 spinner）
    - 使用独立线程运行 stream，支持优雅关闭

    Attributes:
        name: 渠道名称（"dingtalk"）
    """

    name = "dingtalk"

    def __init__(self, config, bus: "MessageBus"):
        """
        初始化钉钉渠道。

        Args:
            config: 渠道配置（包含 client_id, client_secret, allowed_users）
            bus: 消息总线
        """
        super().__init__(config, bus)
        self.client_id = getattr(config, "client_id", "")
        self.client_secret = getattr(config, "client_secret", "")
        # AI Card 配置（可选）
        self.card_template_id = getattr(config, "card_template_id", "")
        self.card_template_key = getattr(config, "card_template_key", "content")

        self._client = None
        self._http: httpx.AsyncClient | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stream_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._background_tasks: set[asyncio.Task] = set()

        # Access Token 缓存
        self._access_token: str | None = None
        self._token_expiry: float = 0

        # AI Card 状态管理
        self._active_cards: dict[str, ActiveCard] = {}
        self._cards_lock = asyncio.Lock()

        # 会话上下文（用于 AI Card 创建）
        self._session_contexts: dict[str, dict[str, Any]] = {}

    async def start(self) -> None:
        """启动钉钉 Bot"""
        if not self.client_id or not self.client_secret:
            logger.error("DingTalk client_id or client_secret not configured")
            return

        if not _ensure_dingtalk():
            logger.error(
                "dingtalk-stream not installed. "
                "Install it with: pip install deepcobot[dingtalk]"
            )
            return

        self._running = True

        # 创建自定义处理器
        class CustomDingTalkHandler(_CallbackHandler):
            def __init__(self, channel):
                super().__init__()
                self.channel = channel

            async def process(self, message: _CallbackMessage):
                """处理入站消息"""
                try:
                    # 调试日志：原始消息和 topic
                    logger.info("=" * 50)
                    logger.info("DingTalk callback received!")
                    logger.info("Topic: {}", message.headers.topic if hasattr(message, 'headers') else 'N/A')
                    logger.info("Raw message data: {}", message.data)
                    logger.debug("Received raw message: {}", message.data)

                    # 使用 SDK 的 ChatbotMessage 解析消息
                    chatbot_msg = _ChatbotMessage.from_dict(message.data)

                    # 调试日志：消息类型
                    logger.info(
                        "DingTalk message received - type: {}, sender: {}",
                        chatbot_msg.message_type,
                        chatbot_msg.sender_nick or chatbot_msg.sender_id,
                    )

                    # 提取文本内容
                    content = ""
                    if chatbot_msg.text:
                        content = chatbot_msg.text.content.strip()
                    elif chatbot_msg.extensions.get("content", {}).get("recognition"):
                        content = chatbot_msg.extensions["content"]["recognition"].strip()
                    if not content:
                        content = message.data.get("text", {}).get("content", "").strip()

                    if not content:
                        logger.warning(
                            "Received empty or unsupported message type: {}",
                            chatbot_msg.message_type,
                        )
                        return _AckMessage.STATUS_OK, "OK"

                    # 提取发送者信息
                    sender_id = chatbot_msg.sender_staff_id or chatbot_msg.sender_id
                    sender_name = chatbot_msg.sender_nick or "Unknown"

                    # 提取会话信息
                    conversation_type = message.data.get("conversationType")
                    conversation_id = (
                        message.data.get("conversationId")
                        or message.data.get("openConversationId")
                    )

                    # 群聊消息需要特殊处理 chat_id
                    is_group = conversation_type == "2" and conversation_id
                    chat_id = f"group:{conversation_id}" if is_group else sender_id

                    # 保存会话信息用于 AI Card 创建
                    self.channel._session_contexts[chat_id] = {
                        "conversation_id": conversation_id,
                        "is_group": is_group,
                        "sender_staff_id": chatbot_msg.sender_staff_id or sender_id,
                    }

                    logger.info(
                        "Received DingTalk message from {} ({}): {}",
                        sender_name,
                        sender_id,
                        content,
                    )

                    # 构建入站消息
                    inbound_msg = InboundMessage(
                        channel=self.channel.name,
                        sender_id=str(sender_id),
                        chat_id=str(chat_id),
                        content=content,
                        media_urls=[],
                        metadata={
                            "sender_name": sender_name,
                            "conversation_type": conversation_type,
                            "sender_staff_id": chatbot_msg.sender_staff_id or sender_id,
                            "conversation_id": conversation_id,
                            "is_group": is_group,
                        },
                    )

                    # 使用 threadsafe 方法发布消息到主事件循环
                    # 因为钉钉 Stream 运行在独立线程中，有自己的事件循环
                    logger.info("Publishing DingTalk message to bus (threadsafe)...")
                    self.channel.bus.publish_inbound_threadsafe(inbound_msg)
                    logger.info("DingTalk message published to bus")

                    return _AckMessage.STATUS_OK, "OK"

                except Exception as e:
                    logger.error("Error processing DingTalk message: {}", e)
                    return _AckMessage.STATUS_OK, "Error"

        # 创建凭证和客户端
        credential = _Credential(self.client_id, self.client_secret)
        self._client = _DingTalkStreamClient(credential)

        # 注册回调处理器
        handler = CustomDingTalkHandler(self)
        self._client.register_callback_handler(_ChatbotMessage.TOPIC, handler)

        logger.info("DingTalk client initialized")

        # 保存当前事件循环引用
        self._loop = asyncio.get_running_loop()

        # 清除停止信号
        self._stop_event.clear()

        # 在独立线程中运行 stream，支持优雅关闭
        self._stream_thread = threading.Thread(
            target=self._run_stream_forever,
            daemon=True,
        )
        self._stream_thread.start()

        logger.info("DingTalk stream thread started")

    def _run_stream_forever(self) -> None:
        """在独立线程中运行 stream 循环"""
        logger.info("DingTalk stream thread running...")
        try:
            if self._client:
                asyncio.run(self._stream_loop())
        except Exception as e:
            logger.exception("DingTalk stream thread failed: {}", e)
        finally:
            self._stop_event.set()
            logger.info("DingTalk stream thread stopped")

    async def _stream_loop(self) -> None:
        """
        驱动 DingTalkStreamClient.start() 并在 _stop_event 设置时优雅停止。

        关闭 websocket 并取消任务，避免进程退出时出现 "Task was destroyed but it is pending"。
        """
        client = self._client
        if not client:
            return

        main_task = asyncio.create_task(client.start())

        async def stop_watcher() -> None:
            """监控停止信号，触发时关闭 websocket"""
            while not self._stop_event.is_set():
                await asyncio.sleep(0.5)
            # 关闭 websocket 以中断 client.start()
            if client.websocket is not None:
                try:
                    await client.websocket.close()
                except Exception:
                    pass
            await asyncio.sleep(0.2)
            # 取消主任务
            if not main_task.done():
                main_task.cancel()

        watcher_task = asyncio.create_task(stop_watcher())

        try:
            await main_task
        except asyncio.CancelledError:
            logger.debug("DingTalk stream main task cancelled")
        except Exception as e:
            logger.warning("DingTalk stream error: {}", e)

        # 取消 watcher
        watcher_task.cancel()
        try:
            await watcher_task
        except asyncio.CancelledError:
            pass

        # 取消剩余的后台任务，确保循环干净退出
        loop = asyncio.get_running_loop()
        pending = [
            t
            for t in asyncio.all_tasks(loop)
            if t is not asyncio.current_task() and not t.done()
        ]
        for t in pending:
            t.cancel()
        if pending:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*pending, return_exceptions=True),
                    timeout=4.0,
                )
            except asyncio.TimeoutError:
                pass

    async def stop(self) -> None:
        """停止钉钉 Bot"""
        logger.info("Stopping DingTalk channel...")
        self._running = False

        # 设置停止信号，触发 stop_watcher 关闭 websocket
        self._stop_event.set()

        # 等待 stream 线程结束
        if self._stream_thread and self._stream_thread.is_alive():
            self._stream_thread.join(timeout=5)
            if self._stream_thread.is_alive():
                logger.warning("DingTalk stream thread did not stop gracefully")

        # 完成 AI Card
        if self._loop and not self._loop.is_closed():
            for conv_id, card in list(self._active_cards.items()):
                if card.state not in (CARD_FINISHED, CARD_FAILED):
                    try:
                        await self._stream_ai_card(
                            card, card.last_content or AI_CARD_PROCESSING_TEXT, finalize=True
                        )
                    except Exception:
                        logger.debug("DingTalk finalize card on stop failed", exc_info=True)

            # 取消后台任务
            for task in self._background_tasks:
                if not task.done():
                    task.cancel()
            self._background_tasks.clear()

        # 关闭 HTTP 客户端
        if self._http:
            await self._http.aclose()
            self._http = None

        self._client = None
        logger.info("DingTalk channel stopped")

    async def _get_access_token(self) -> str | None:
        """获取 access_token（带缓存）"""
        if self._access_token and time.time() < self._token_expiry:
            return self._access_token

        # 检查 SDK 客户端是否可用
        if self._client:
            try:
                token = self._client.get_access_token()
                if token:
                    self._access_token = token
                    self._token_expiry = time.time() + 3600  # 1小时过期
                    return token
            except Exception as e:
                logger.warning("Failed to get token from SDK: {}", e)

        # 手动获取 token
        url = "https://api.dingtalk.com/v1.0/oauth2/accessToken"
        data = {
            "appKey": self.client_id,
            "appSecret": self.client_secret,
        }

        if not self._http:
            self._http = httpx.AsyncClient()

        try:
            resp = await self._http.post(url, json=data)
            resp.raise_for_status()
            result = resp.json()
            self._access_token = result.get("accessToken")
            self._token_expiry = time.time() + int(result.get("expireIn", 7200)) - 60
            return self._access_token
        except Exception as e:
            logger.error("Failed to get DingTalk access token: {}", e)
            return None

    def _ai_card_enabled(self) -> bool:
        """检查 AI Card 是否已配置"""
        return bool(self.card_template_id)

    async def _create_ai_card(
        self,
        conversation_id: str,
        is_group: bool = False,
        sender_staff_id: str = "",
    ) -> ActiveCard | None:
        """
        创建 AI Card 用于进度显示。

        钉钉 AI Card 需要两步：
        1. 创建卡片实例 (card/instances)
        2. 投递卡片到会话 (card/instances/deliver)

        Args:
            conversation_id: 会话 ID
            is_group: 是否群聊
            sender_staff_id: 发送者员工 ID（私聊需要）

        Returns:
            ActiveCard 或 None
        """
        if not self._ai_card_enabled():
            return None

        token = await self._get_access_token()
        if not token:
            return None

        if not self._http:
            self._http = httpx.AsyncClient()

        card_instance_id = f"card_{uuid.uuid4()}"
        headers = {
            "Content-Type": "application/json",
            "x-acs-dingtalk-access-token": token,
        }

        # Step 1: 创建卡片实例
        create_url = "https://api.dingtalk.com/v1.0/card/instances"
        create_payload: dict[str, Any] = {
            "cardTemplateId": self.card_template_id,
            "outTrackId": card_instance_id,
            "cardData": {"cardParamMap": {self.card_template_key: ""}},
            "callbackType": "STREAM",
            "imGroupOpenSpaceModel": {"supportForward": True},
            "imRobotOpenSpaceModel": {"supportForward": True},
        }

        try:
            resp = await self._http.post(create_url, json=create_payload, headers=headers)
            if resp.status_code >= 400:
                logger.warning(
                    "DingTalk create AI card failed: status={}, body={}",
                    resp.status_code,
                    resp.text[:500],
                )
                return None

            logger.debug(
                "DingTalk AI card instance created: card_instance_id={}",
                card_instance_id,
            )

        except Exception as e:
            logger.error("Failed to create DingTalk AI card instance: {}", e)
            return None

        # Step 2: 投递卡片到会话
        if is_group:
            open_space_id = f"dtv1.card//IM_GROUP.{conversation_id}"
            deliver_payload = {
                "outTrackId": card_instance_id,
                "userIdType": 1,
                "openSpaceId": open_space_id,
                "imGroupOpenDeliverModel": {
                    "robotCode": self.client_id,
                },
            }
        else:
            if not sender_staff_id:
                logger.warning("DingTalk AI card need sender_staff_id for private chat")
                return None
            open_space_id = f"dtv1.card//IM_ROBOT.{sender_staff_id}"
            deliver_payload = {
                "outTrackId": card_instance_id,
                "userIdType": 1,
                "openSpaceId": open_space_id,
                "imRobotOpenDeliverModel": {
                    "spaceType": "IM_ROBOT",
                },
            }

        deliver_url = "https://api.dingtalk.com/v1.0/card/instances/deliver"
        try:
            resp = await self._http.post(deliver_url, json=deliver_payload, headers=headers)
            if resp.status_code >= 400:
                logger.warning(
                    "DingTalk deliver AI card failed: status={}, body={}",
                    resp.status_code,
                    resp.text[:500],
                )
                return None

            logger.info(
                "DingTalk AI card delivered: conversation_id={}, card_instance_id={}",
                conversation_id,
                card_instance_id,
            )

        except Exception as e:
            logger.error("Failed to deliver DingTalk AI card: {}", e)
            return None

        now_ms = int(time.time() * 1000)
        card = ActiveCard(
            card_instance_id=card_instance_id,
            access_token=token,
            conversation_id=conversation_id,
            created_at=now_ms,
            last_updated=now_ms,
            state=CARD_PROCESSING,
        )
        async with self._cards_lock:
            self._active_cards[conversation_id] = card
        return card

    async def _stream_ai_card(
        self,
        card: ActiveCard,
        content: str,
        finalize: bool = False,
    ) -> bool:
        """更新 AI Card 内容"""
        if card.state in (CARD_FINISHED, CARD_FAILED):
            return False

        content = (content or "").strip()
        if not content:
            return False

        now_ms = int(time.time() * 1000)

        # 节流：非 finalize 时限制更新频率
        if not finalize:
            if content == card.last_content:
                return False
            if (now_ms - card.last_updated) < AI_CARD_MIN_INTERVAL_SECONDS * 1000:
                return False

        token = await self._get_access_token()
        if not token:
            return False

        if not self._http:
            self._http = httpx.AsyncClient()

        payload = {
            "outTrackId": card.card_instance_id,
            "guid": str(uuid.uuid4()),
            "key": self.card_template_key,
            "content": content,
            "isFull": True,
            "isFinalize": finalize,
            "isError": False,
        }
        url = "https://api.dingtalk.com/v1.0/card/streaming"
        headers = {
            "Content-Type": "application/json",
            "x-acs-dingtalk-access-token": token,
        }

        try:
            resp = await self._http.put(url, json=payload, headers=headers)
            if resp.status_code == 401:
                # Token 过期，刷新后重试
                token = await self._get_access_token()
                if token:
                    headers["x-acs-dingtalk-access-token"] = token
                    resp = await self._http.put(url, json=payload, headers=headers)

            if resp.status_code >= 400:
                logger.warning(
                    "DingTalk stream AI card failed: status={}, body={}",
                    resp.status_code,
                    resp.text[:500],
                )
                return False

            logger.debug(
                "DingTalk AI card updated: conversation_id={}, finalize={}",
                card.conversation_id,
                finalize,
            )

            card.last_content = content
            card.last_updated = now_ms

            if finalize:
                card.state = CARD_FINISHED
                async with self._cards_lock:
                    self._active_cards.pop(card.conversation_id, None)
            elif card.state == CARD_PROCESSING:
                card.state = CARD_INPUTING

            return True

        except Exception as e:
            logger.error("Failed to stream DingTalk AI card: {}", e)
            return False

    async def send(self, msg: OutboundMessage) -> None:
        """
        发送消息到钉钉。

        注意：需要通过 HTTP API 发送消息，Stream SDK 只用于接收。

        Args:
            msg: 出站消息
        """
        token = await self._get_access_token()
        if not token:
            logger.warning("DingTalk access token not available")
            return

        if not self._http:
            self._http = httpx.AsyncClient()

        chat_id = msg.chat_id
        headers = {"x-acs-dingtalk-access-token": token}

        # 检查是否有活跃的 AI Card
        conversation_id = chat_id[6:] if chat_id.startswith("group:") else chat_id
        card = self._active_cards.get(conversation_id)

        # 如果有活跃的 AI Card，尝试 finalize 并发送
        if card and self._ai_card_enabled():
            await self._stream_ai_card(card, msg.content, finalize=True)
            return

        # 常规消息发送
        if chat_id.startswith("group:"):
            url = "https://api.dingtalk.com/v1.0/robot/groupMessages/send"
            payload = {
                "robotCode": self.client_id,
                "openConversationId": chat_id[6:],
                "msgKey": "sampleMarkdown",
                "msgParam": json.dumps(
                    {"title": "Reply", "text": msg.content}, ensure_ascii=False
                ),
            }
        else:
            url = "https://api.dingtalk.com/v1.0/robot/oToMessages/batchSend"
            payload = {
                "robotCode": self.client_id,
                "userIds": [chat_id],
                "msgKey": "sampleMarkdown",
                "msgParam": json.dumps(
                    {"title": "Reply", "text": msg.content}, ensure_ascii=False
                ),
            }

        try:
            resp = await self._http.post(url, json=payload, headers=headers)
            if resp.status_code != 200:
                logger.error(
                    "DingTalk send failed: status={}, body={}",
                    resp.status_code,
                    resp.text[:500],
                )
            else:
                logger.debug("DingTalk message sent to {}", chat_id)
        except Exception as e:
            logger.error("Error sending DingTalk message: {}", e)

    async def send_progress(self, chat_id: str, content: str) -> None:
        """
        发送进度更新（使用 AI Card）。

        如果配置了 card_template_id，会创建/更新 AI Card 显示进度。
        这类似于 CLI 中的 spinner 效果，让用户知道 Agent 正在工作。

        Args:
            chat_id: 会话 ID
            content: 进度内容
        """
        if not self._ai_card_enabled():
            # 未配置 AI Card，不支持进度显示
            return

        conversation_id = chat_id[6:] if chat_id.startswith("group:") else chat_id

        # 获取或创建 AI Card
        async with self._cards_lock:
            card = self._active_cards.get(conversation_id)

        if not card:
            # 获取会话上下文
            ctx = self._session_contexts.get(chat_id, {})
            card = await self._create_ai_card(
                conversation_id=conversation_id,
                is_group=ctx.get("is_group", False),
                sender_staff_id=ctx.get("sender_staff_id", ""),
            )
            if not card:
                return

        # 更新 AI Card 内容
        await self._stream_ai_card(card, content, finalize=False)