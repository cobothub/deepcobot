"""Cron 数据模型

定义定时任务的数据结构。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class CronSchedule:
    """
    调度配置。

    支持三种调度模式：
    - at: 一次性执行（指定时间戳）
    - every: 间隔执行（指定间隔毫秒数）
    - cron: Cron 表达式（5 字段）

    Attributes:
        kind: 调度类型（"at" | "every" | "cron"）
        at_ms: 一次性执行时间戳（毫秒）
        every_ms: 间隔执行间隔（毫秒）
        expr: Cron 表达式（5 字段）
        timezone: 时区（默认 UTC）
    """

    kind: str = "every"  # "at" | "every" | "cron"
    at_ms: int | None = None
    every_ms: int | None = None
    expr: str | None = None
    timezone: str = "UTC"


@dataclass
class CronPayload:
    """
    任务执行内容。

    Attributes:
        message: 发送给 Agent 的消息
        channel: 结果发送渠道
        chat_id: 结果发送目标
    """

    message: str = ""
    channel: str | None = None
    chat_id: str | None = None


@dataclass
class CronJobState:
    """
    任务运行状态。

    Attributes:
        next_run_at_ms: 下次执行时间戳（毫秒）
        last_run_at_ms: 上次执行时间戳（毫秒）
        last_status: 上次执行状态（"ok" | "error"）
        last_error: 上次执行错误信息
    """

    next_run_at_ms: int | None = None
    last_run_at_ms: int | None = None
    last_status: str | None = None
    last_error: str | None = None


@dataclass
class CronJob:
    """
    定时任务。

    Attributes:
        id: 任务 ID
        name: 任务名称
        enabled: 是否启用
        schedule: 调度配置
        payload: 执行内容
        state: 运行状态
        created_at_ms: 创建时间戳（毫秒）
        updated_at_ms: 更新时间戳（毫秒）
    """

    id: str
    name: str
    enabled: bool = True
    schedule: CronSchedule = field(default_factory=lambda: CronSchedule(kind="every"))
    payload: CronPayload = field(default_factory=CronPayload)
    state: CronJobState = field(default_factory=CronJobState)
    created_at_ms: int = 0
    updated_at_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "enabled": self.enabled,
            "schedule": {
                "kind": self.schedule.kind,
                "at_ms": self.schedule.at_ms,
                "every_ms": self.schedule.every_ms,
                "expr": self.schedule.expr,
                "timezone": self.schedule.timezone,
            },
            "payload": {
                "message": self.payload.message,
                "channel": self.payload.channel,
                "chat_id": self.payload.chat_id,
            },
            "state": {
                "next_run_at_ms": self.state.next_run_at_ms,
                "last_run_at_ms": self.state.last_run_at_ms,
                "last_status": self.state.last_status,
                "last_error": self.state.last_error,
            },
            "created_at_ms": self.created_at_ms,
            "updated_at_ms": self.updated_at_ms,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CronJob":
        """从字典创建"""
        return cls(
            id=data["id"],
            name=data["name"],
            enabled=data.get("enabled", True),
            schedule=CronSchedule(
                kind=data.get("schedule", {}).get("kind", "every"),
                at_ms=data.get("schedule", {}).get("at_ms"),
                every_ms=data.get("schedule", {}).get("every_ms"),
                expr=data.get("schedule", {}).get("expr"),
                timezone=data.get("schedule", {}).get("timezone", "UTC"),
            ),
            payload=CronPayload(
                message=data.get("payload", {}).get("message", ""),
                channel=data.get("payload", {}).get("channel"),
                chat_id=data.get("payload", {}).get("chat_id"),
            ),
            state=CronJobState(
                next_run_at_ms=data.get("state", {}).get("next_run_at_ms"),
                last_run_at_ms=data.get("state", {}).get("last_run_at_ms"),
                last_status=data.get("state", {}).get("last_status"),
                last_error=data.get("state", {}).get("last_error"),
            ),
            created_at_ms=data.get("created_at_ms", 0),
            updated_at_ms=data.get("updated_at_ms", 0),
        )


def _now_ms() -> int:
    """获取当前时间戳（毫秒）"""
    return int(datetime.now().timestamp() * 1000)


def parse_interval(interval_str: str) -> int:
    """
    解析间隔字符串为毫秒数。

    支持格式:
    - "30s" -> 30000
    - "5m" -> 300000
    - "1h" -> 3600000
    - "1d" -> 86400000

    Args:
        interval_str: 间隔字符串

    Returns:
        毫秒数

    Raises:
        ValueError: 格式无效
    """
    interval_str = interval_str.strip().lower()

    if not interval_str:
        raise ValueError("Empty interval string")

    unit = interval_str[-1]
    try:
        value = int(interval_str[:-1])
    except ValueError:
        raise ValueError(f"Invalid interval format: {interval_str}")

    multipliers = {
        "s": 1000,
        "m": 60 * 1000,
        "h": 60 * 60 * 1000,
        "d": 24 * 60 * 60 * 1000,
    }

    if unit not in multipliers:
        raise ValueError(f"Unknown time unit: {unit}")

    return value * multipliers[unit]