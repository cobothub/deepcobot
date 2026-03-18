"""Heartbeat 服务

定期读取 HEARTBEAT.md 并触发 Agent 执行任务。
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, time, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Coroutine
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from loguru import logger

if TYPE_CHECKING:
    from deepcobot.bus.queue import MessageBus
    from deepcobot.config import HeartbeatConfig

# HEARTBEAT.md 文件名
HEARTBEAT_FILE = "HEARTBEAT.md"

# 间隔解析正则：支持 "30m", "1h", "2h30m", "90s"
_EVERY_PATTERN = re.compile(
    r"^(?:(?P<hours>\d+)h)?(?:(?P<minutes>\d+)m)?(?:(?P<seconds>\d+)s)?$",
    re.IGNORECASE,
)


def parse_interval(every: str) -> int:
    """解析间隔字符串为秒数。

    Args:
        every: 间隔字符串，如 "30m", "1h", "2h30m"

    Returns:
        间隔秒数
    """
    every = (every or "").strip()
    if not every:
        return 30 * 60  # 默认 30 分钟

    m = _EVERY_PATTERN.match(every)
    if not m:
        logger.warning("Invalid heartbeat interval: {}, using 30m", every)
        return 30 * 60

    hours = int(m.group("hours") or 0)
    minutes = int(m.group("minutes") or 0)
    seconds = int(m.group("seconds") or 0)
    total = hours * 3600 + minutes * 60 + seconds

    if total <= 0:
        return 30 * 60

    return total


def parse_active_hours(active_hours: str | None, user_timezone: str = "UTC") -> tuple[time, time] | None:
    """解析活跃时段。

    Args:
        active_hours: 活跃时段字符串，如 "09:00-18:00"
        user_timezone: 用户时区

    Returns:
        (start_time, end_time) 或 None
    """
    if not active_hours:
        return None

    try:
        parts = active_hours.strip().split("-")
        if len(parts) != 2:
            return None

        start_parts = parts[0].strip().split(":")
        end_parts = parts[1].strip().split(":")

        start_t = time(
            int(start_parts[0]),
            int(start_parts[1]) if len(start_parts) > 1 else 0,
        )
        end_t = time(
            int(end_parts[0]),
            int(end_parts[1]) if len(end_parts) > 1 else 0,
        )
        return start_t, end_t
    except (ValueError, IndexError, AttributeError):
        return None


def is_in_active_hours(
    active_hours: tuple[time, time] | None,
    user_timezone: str = "UTC",
) -> bool:
    """检查当前时间是否在活跃时段内。

    Args:
        active_hours: (start_time, end_time) 或 None
        user_timezone: 用户时区

    Returns:
        是否在活跃时段内
    """
    if not active_hours:
        return True

    start_t, end_t = active_hours

    try:
        tz = ZoneInfo(user_timezone)
        now = datetime.now(tz).time()
    except (ZoneInfoNotFoundError, KeyError):
        logger.warning("Invalid timezone: {}, using UTC", user_timezone)
        now = datetime.now(timezone.utc).time()

    # 处理跨午夜的情况，如 22:00-06:00
    if start_t <= end_t:
        return start_t <= now <= end_t
    else:
        return now >= start_t or now <= end_t


class HeartbeatService:
    """
    Heartbeat 服务：定期读取 HEARTBEAT.md 并触发 Agent 执行任务。

    作为消息触发源，类似于 Channel，构造 InboundMessage 发送到 MessageBus。
    Agent 层统一处理消息。

    Attributes:
        workspace: 工作空间目录
        bus: 消息总线
        config: Heartbeat 配置
        on_execute: 执行回调（调用 Agent）
    """

    def __init__(
        self,
        workspace: Path,
        bus: "MessageBus",
        config: "HeartbeatConfig",
        on_execute: Callable[[str, str, str], Coroutine[Any, Any, str]],
        get_last_dispatch: Callable[[], tuple[str, str] | None] | None = None,
        user_timezone: str = "UTC",
    ):
        """
        初始化 Heartbeat 服务。

        Args:
            workspace: 工作空间目录
            bus: 消息总线
            config: Heartbeat 配置
            on_execute: 执行回调，接收 (content, session_key, channel) 返回响应
            get_last_dispatch: 获取上次交互渠道的回调，返回 (channel, chat_id) 或 None
            user_timezone: 用户时区
        """
        self.workspace = workspace
        self.bus = bus
        self.config = config
        self.on_execute = on_execute
        self.get_last_dispatch = get_last_dispatch
        self.user_timezone = user_timezone

        self._running = False
        self._task: asyncio.Task | None = None
        self._interval_s = parse_interval(config.every)
        self._active_hours = parse_active_hours(config.active_hours, user_timezone)

    @property
    def heartbeat_file(self) -> Path:
        """HEARTBEAT.md 文件路径"""
        return self.workspace / HEARTBEAT_FILE

    def _read_heartbeat_file(self) -> str | None:
        """读取 HEARTBEAT.md 文件内容"""
        if not self.heartbeat_file.exists():
            return None

        try:
            content = self.heartbeat_file.read_text(encoding="utf-8").strip()
            return content if content else None
        except Exception as e:
            logger.error("Failed to read HEARTBEAT.md: {}", e)
            return None

    def _parse_target(self) -> tuple[str, str] | None:
        """解析结果投递目标。

        Returns:
            (channel, chat_id) 或 None（不投递）
        """
        target = (self.config.target or "").strip().lower()

        # 没有配置 target，不投递
        if not target:
            logger.info("Heartbeat: no target configured")
            return None

        # target = "last"，投递到上次交互渠道
        if target == "last":
            if self.get_last_dispatch:
                last = self.get_last_dispatch()
                logger.info("Heartbeat: get_last_dispatch returned {}", last)
                if last:
                    channel, chat_id = last
                    # CLI 渠道不投递
                    if channel != "cli":
                        return channel, chat_id
                else:
                    logger.warning("Heartbeat: target=last but no previous dispatch found")
            else:
                logger.warning("Heartbeat: target=last but get_last_dispatch not set")
            return None

        # target = "channel:chat_id"，投递到指定渠道
        if ":" in target:
            channel, chat_id = target.split(":", 1)
            channel = channel.strip()
            chat_id = chat_id.strip()
            # CLI 渠道不投递
            if channel == "cli":
                return None
            return channel, chat_id

        logger.warning("Heartbeat: invalid target format: {}", target)
        return None

    async def start(self) -> None:
        """启动 Heartbeat 服务"""
        if not self.config.enabled:
            logger.info("Heartbeat disabled")
            return

        if self._running:
            logger.warning("Heartbeat already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            "Heartbeat started: every {}s, active_hours={}",
            self._interval_s,
            self.config.active_hours or "always",
        )

    async def stop(self) -> None:
        """停止 Heartbeat 服务"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Heartbeat stopped")

    async def _run_loop(self) -> None:
        """主循环"""
        while self._running:
            try:
                await asyncio.sleep(self._interval_s)
                if self._running:
                    await self._tick()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Heartbeat error: {}", e)

    async def _tick(self) -> None:
        """执行一次 Heartbeat"""
        # 检查活跃时段
        if not is_in_active_hours(self._active_hours, self.user_timezone):
            logger.debug("Heartbeat: outside active hours")
            return

        # 读取 HEARTBEAT.md
        content = self._read_heartbeat_file()
        if not content:
            logger.debug("Heartbeat: no content in HEARTBEAT.md")
            return

        logger.info("Heartbeat: executing...")

        try:
            # 解析投递目标
            target = self._parse_target()
            session_key = "heartbeat"

            if target:
                channel, chat_id = target
                # 有投递目标，执行并通过 MessageBus 投递结果
                response = await asyncio.wait_for(
                    self.on_execute(content, session_key, channel),
                    timeout=self.config.timeout,
                )

                if response:
                    from deepcobot.channels.events import OutboundMessage
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=channel,
                        chat_id=chat_id,
                        content=response,
                    ))
                    logger.info("Heartbeat: completed and dispatched to {}:{}", channel, chat_id)
            else:
                # 无投递目标，仅执行
                await asyncio.wait_for(
                    self.on_execute(content, session_key, "heartbeat"),
                    timeout=self.config.timeout,
                )
                logger.info("Heartbeat: completed (no dispatch)")

        except asyncio.TimeoutError:
            logger.warning("Heartbeat: timed out after {}s", self.config.timeout)
        except Exception as e:
            logger.error("Heartbeat execution failed: {}", e)

    async def trigger_now(self) -> str | None:
        """手动触发一次 Heartbeat。

        Returns:
            Agent 响应或 None
        """
        content = self._read_heartbeat_file()
        if not content:
            return None

        try:
            return await asyncio.wait_for(
                self.on_execute(content, "heartbeat:manual", "heartbeat"),
                timeout=self.config.timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("Heartbeat trigger timed out")
            return None