"""审批状态管理

管理 Bot 场景下的审批请求和响应。
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from loguru import logger


@dataclass
class ApprovalRequest:
    """审批请求"""

    session_key: str  # channel:chat_id
    action_requests: list[dict]  # 待审批的工具调用列表
    created_at: datetime = field(default_factory=datetime.now)
    future: asyncio.Future = field(default=None)

    def __post_init__(self):
        if self.future is None:
            self.future = asyncio.get_event_loop().create_future()


class ApprovalManager:
    """
    审批状态管理器

    管理等待中的审批请求，匹配用户响应。

    使用方式:
    1. Agent 发起审批时调用 create_request() 创建请求并等待
    2. 收到用户消息时调用 handle_response() 检查是否是审批响应
    3. 如果是审批响应，设置结果并唤醒等待的 Agent
    """

    def __init__(self, timeout: float = 300.0):
        """
        初始化审批管理器

        Args:
            timeout: 审批超时时间（秒），默认 5 分钟
        """
        self._pending: dict[str, ApprovalRequest] = {}  # session_key -> ApprovalRequest
        self._timeout = timeout
        self._lock = asyncio.Lock()

    def has_pending(self, session_key: str) -> bool:
        """检查指定会话是否有等待中的审批"""
        return session_key in self._pending

    async def create_request(
        self,
        session_key: str,
        action_requests: list[dict],
    ) -> ApprovalRequest:
        """
        创建审批请求

        Args:
            session_key: 会话标识 (channel:chat_id)
            action_requests: 待审批的工具调用列表

        Returns:
            ApprovalRequest 实例
        """
        async with self._lock:
            # 如果已有等待中的请求，先取消
            if session_key in self._pending:
                old_request = self._pending[session_key]
                if not old_request.future.done():
                    old_request.future.cancel()
                    try:
                        await old_request.future
                    except asyncio.CancelledError:
                        pass

            request = ApprovalRequest(
                session_key=session_key,
                action_requests=action_requests,
            )
            self._pending[session_key] = request
            logger.info(f"[Approval] Created request for {session_key}, {len(action_requests)} actions")
            return request

    async def wait_for_response(
        self,
        request: ApprovalRequest,
    ) -> list[dict]:
        """
        等待用户响应

        Args:
            request: 审批请求

        Returns:
            用户决策列表
        """
        try:
            decisions = await asyncio.wait_for(
                request.future,
                timeout=self._timeout,
            )
            return decisions
        except asyncio.TimeoutError:
            logger.warning(f"[Approval] Timeout for {request.session_key}")
            # 超时后自动拒绝
            return [{"type": "reject", "message": "Approval timeout"} for _ in request.action_requests]
        finally:
            # 清理
            async with self._lock:
                if request.session_key in self._pending:
                    del self._pending[request.session_key]

    def handle_response(self, session_key: str, content: str) -> bool:
        """
        处理用户响应

        检查消息是否是审批响应，如果是则设置结果。

        Args:
            session_key: 会话标识
            content: 用户消息内容

        Returns:
            是否是审批响应
        """
        if session_key not in self._pending:
            return False

        request = self._pending[session_key]
        if request.future.done():
            return False

        content = content.strip().lower()

        # 解析用户响应
        decisions = self._parse_response(content, request.action_requests)
        if decisions is None:
            # 不是有效的审批响应
            return False

        # 设置结果
        request.future.set_result(decisions)
        logger.info(f"[Approval] Got response for {session_key}: {len(decisions)} decisions")
        return True

    def _parse_response(self, content: str, action_requests: list[dict]) -> list[dict] | None:
        """
        解析用户响应

        Args:
            content: 用户消息内容
            action_requests: 待审批的工具调用列表

        Returns:
            决策列表，如果无法解析则返回 None
        """
        # 支持的审批命令
        # y/yes/a/all - 全部批准
        # n/no - 全部拒绝
        # 数字+y/n - 单独批准/拒绝

        content = content.strip().lower()

        # 全部批准
        if content in ("y", "yes", "a", "all", "批准", "同意"):
            return [{"type": "approve"} for _ in action_requests]

        # 全部拒绝
        if content in ("n", "no", "拒绝"):
            return [{"type": "reject"} for _ in action_requests]

        # TODO: 支持单独批准/拒绝，如 "1y 2n"
        # 暂不实现，保持简单

        return None

    def cancel(self, session_key: str) -> None:
        """
        取消审批请求

        Args:
            session_key: 会话标识
        """
        if session_key in self._pending:
            request = self._pending[session_key]
            if not request.future.done():
                request.future.cancel()
            del self._pending[session_key]
            logger.info(f"[Approval] Cancelled request for {session_key}")

    def get_pending_count(self) -> int:
        """获取等待中的审批请求数量"""
        return len(self._pending)


# 全局审批管理器实例
_approval_manager: ApprovalManager | None = None


def get_approval_manager() -> ApprovalManager:
    """获取全局审批管理器实例"""
    global _approval_manager
    if _approval_manager is None:
        _approval_manager = ApprovalManager()
    return _approval_manager