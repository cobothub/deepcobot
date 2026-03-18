"""Cron 数据模型

定义定时任务的数据结构。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# 可选导入 croniter
try:
    from croniter import croniter
except ImportError:
    croniter = None


@dataclass
class CronJob:
    """
    定时任务。

    Attributes:
        id: 任务 ID
        name: 任务名称
        enabled: 是否启用
        schedule: 调度表达式（cron 或 every）
        message: 发送给 Agent 的消息
        channel: 结果发送渠道
        chat_id: 结果发送目标
        timeout: 执行超时（秒）
        next_run_at: 下次执行时间（datetime）
        last_run_at: 上次执行时间（datetime）
        last_status: 上次执行状态
        last_error: 上次执行错误
    """

    id: str
    name: str
    enabled: bool = True
    schedule: str = "1h"  # cron 表达式或 every 间隔
    message: str = ""
    channel: str | None = None
    chat_id: str | None = None
    timeout: int = 120
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    last_status: str | None = None  # "ok" | "error"
    last_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "enabled": self.enabled,
            "schedule": self.schedule,
            "message": self.message,
            "channel": self.channel,
            "chat_id": self.chat_id,
            "timeout": self.timeout,
            "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "last_status": self.last_status,
            "last_error": self.last_error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CronJob":
        """从字典创建"""
        def parse_datetime(s: str | None) -> datetime | None:
            if not s:
                return None
            try:
                return datetime.fromisoformat(s)
            except (ValueError, TypeError):
                return None

        return cls(
            id=data["id"],
            name=data["name"],
            enabled=data.get("enabled", True),
            schedule=data.get("schedule", "1h"),
            message=data.get("message", ""),
            channel=data.get("channel"),
            chat_id=data.get("chat_id"),
            timeout=data.get("timeout", 120),
            next_run_at=parse_datetime(data.get("next_run_at")),
            last_run_at=parse_datetime(data.get("last_run_at")),
            last_status=data.get("last_status"),
            last_error=data.get("last_error"),
        )


def parse_interval(interval_str: str) -> int:
    """
    解析间隔字符串为秒数。

    支持格式:
    - "30s" -> 30
    - "5m" -> 300
    - "1h" -> 3600
    - "1d" -> 86400
    - "2h30m" -> 9000

    Args:
        interval_str: 间隔字符串

    Returns:
        秒数

    Raises:
        ValueError: 格式无效
    """
    import re

    interval_str = (interval_str or "").strip().lower()
    if not interval_str:
        raise ValueError("Empty interval string")

    # 尝试解析复合格式如 "2h30m"
    pattern = r'^(?:(?P<hours>\d+)h)?(?:(?P<minutes>\d+)m)?(?:(?P<seconds>\d+)s)?(?:(?P<days>\d+)d)?$'
    match = re.match(pattern, interval_str)

    if match:
        hours = int(match.group("hours") or 0)
        minutes = int(match.group("minutes") or 0)
        seconds = int(match.group("seconds") or 0)
        days = int(match.group("days") or 0)
        total = days * 86400 + hours * 3600 + minutes * 60 + seconds
        if total > 0:
            return total

    # 简单格式如 "30s", "5m"
    unit = interval_str[-1]
    try:
        value = int(interval_str[:-1])
    except ValueError:
        raise ValueError(f"Invalid interval format: {interval_str}")

    multipliers = {
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 86400,
    }

    if unit not in multipliers:
        raise ValueError(f"Unknown time unit: {unit}")

    return value * multipliers[unit]


def is_cron_expression(schedule: str) -> bool:
    """判断是否为 cron 表达式"""
    # cron 表达式有 5 个字段（分 时 日 月 周）
    parts = schedule.strip().split()
    return len(parts) == 5


def compute_next_run(schedule: str, now: datetime | None = None) -> datetime | None:
    """
    计算下次执行时间。

    Args:
        schedule: 调度表达式（cron 或 every）
        now: 当前时间，默认为 datetime.now()

    Returns:
        下次执行时间，或 None 表示无效
    """
    if now is None:
        now = datetime.now()

    # 尝试作为 cron 表达式解析
    if is_cron_expression(schedule):
        if croniter is None:
            return None
        try:
            cron = croniter(schedule, now)
            return cron.get_next(datetime)
        except Exception:
            return None

    # 尝试作为间隔解析
    try:
        interval_seconds = parse_interval(schedule)
        from datetime import timedelta
        return now + timedelta(seconds=interval_seconds)
    except ValueError:
        return None