"""Cron 服务

定时任务调度和执行。
"""

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Coroutine

from loguru import logger

from deepcobot.cron.types import (
    CronJob,
    CronSchedule,
    CronPayload,
    CronJobState,
    _now_ms,
    parse_interval,
)

# 可选导入 croniter
try:
    from croniter import croniter
except ImportError:
    croniter = None


def _compute_next_run(schedule: CronSchedule, now_ms: int) -> int | None:
    """
    计算下次执行时间。

    Args:
        schedule: 调度配置
        now_ms: 当前时间戳（毫秒）

    Returns:
        下次执行时间戳（毫秒），或 None 表示不再执行
    """
    if schedule.kind == "at":
        return schedule.at_ms if schedule.at_ms and schedule.at_ms > now_ms else None

    if schedule.kind == "every":
        if not schedule.every_ms or schedule.every_ms <= 0:
            return None
        return now_ms + schedule.every_ms

    if schedule.kind == "cron" and schedule.expr and croniter:
        try:
            cron = croniter(schedule.expr, datetime.now())
            next_time = cron.get_next(datetime)
            return int(next_time.timestamp() * 1000)
        except Exception:
            return None

    return None


class CronService:
    """
    定时任务服务。

    支持三种调度模式：
    - at: 一次性执行
    - every: 间隔执行
    - cron: Cron 表达式

    Attributes:
        store_path: 任务存储文件路径
        on_job: 任务执行回调函数
    """

    def __init__(
        self,
        store_path: Path,
        on_job: Callable[[CronJob], Coroutine[Any, Any, str | None]] | None = None,
    ):
        """
        初始化 Cron 服务。

        Args:
            store_path: 任务存储文件路径
            on_job: 任务执行回调函数
        """
        self.store_path = Path(store_path).expanduser()
        self.on_job = on_job
        self._jobs: list[CronJob] = []
        self._timer_task: asyncio.Task | None = None
        self._running = False

    def _load_jobs(self) -> None:
        """从文件加载任务"""
        if not self.store_path.exists():
            return

        try:
            data = json.loads(self.store_path.read_text())
            jobs_data = data.get("jobs", [])
            self._jobs = [CronJob.from_dict(j) for j in jobs_data]
            logger.info(f"Loaded {len(self._jobs)} cron jobs")
        except Exception as e:
            logger.warning(f"Failed to load cron store: {e}")
            self._jobs = []

    def _save_jobs(self) -> None:
        """保存任务到文件"""
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": 1,
            "jobs": [j.to_dict() for j in self._jobs],
        }
        self.store_path.write_text(json.dumps(data, indent=2))

    async def start(self) -> None:
        """启动定时任务服务"""
        self._running = True
        self._load_jobs()
        self._recompute_next_runs()
        self._save_jobs()
        self._arm_timer()
        logger.info(f"Cron service started with {len(self._jobs)} jobs")

    def stop(self) -> None:
        """停止定时任务服务"""
        self._running = False
        if self._timer_task:
            self._timer_task.cancel()
            self._timer_task = None
        logger.info("Cron service stopped")

    def _recompute_next_runs(self) -> None:
        """重新计算所有任务的下次执行时间"""
        now = _now_ms()
        for job in self._jobs:
            if job.enabled:
                job.state.next_run_at_ms = _compute_next_run(job.schedule, now)

    def _get_next_wake_ms(self) -> int | None:
        """获取最近的执行时间"""
        times = [
            j.state.next_run_at_ms
            for j in self._jobs
            if j.enabled and j.state.next_run_at_ms
        ]
        return min(times) if times else None

    def _arm_timer(self) -> None:
        """设置下次执行的定时器"""
        if self._timer_task:
            self._timer_task.cancel()

        next_wake = self._get_next_wake_ms()
        if not next_wake or not self._running:
            return

        delay_ms = max(0, next_wake - _now_ms())
        delay_s = delay_ms / 1000

        async def tick():
            await asyncio.sleep(delay_s)
            if self._running:
                await self._on_timer()

        self._timer_task = asyncio.create_task(tick())

    async def _on_timer(self) -> None:
        """定时器触发，执行到期的任务"""
        now = _now_ms()
        due_jobs = [
            j for j in self._jobs
            if j.enabled and j.state.next_run_at_ms and now >= j.state.next_run_at_ms
        ]

        for job in due_jobs:
            await self._execute_job(job)

        self._save_jobs()
        self._arm_timer()

    async def _execute_job(self, job: CronJob) -> None:
        """
        执行单个任务。

        Args:
            job: 任务对象
        """
        start_ms = _now_ms()
        logger.info(f"Cron: executing job '{job.name}' ({job.id})")

        try:
            if self.on_job:
                await self.on_job(job)
            job.state.last_status = "ok"
            job.state.last_error = None
        except Exception as e:
            job.state.last_status = "error"
            job.state.last_error = str(e)
            logger.error(f"Cron: job '{job.name}' failed: {e}")

        job.state.last_run_at_ms = start_ms
        job.updated_at_ms = _now_ms()

        # 更新下次执行时间
        job.state.next_run_at_ms = _compute_next_run(job.schedule, _now_ms())

    # ========== 公共 API ==========

    def list_jobs(self, include_disabled: bool = False) -> list[CronJob]:
        """
        列出所有任务。

        Args:
            include_disabled: 是否包含禁用的任务

        Returns:
            任务列表（按下次执行时间排序）
        """
        jobs = self._jobs if include_disabled else [j for j in self._jobs if j.enabled]
        return sorted(jobs, key=lambda j: j.state.next_run_at_ms or float("inf"))

    def add_job(
        self,
        name: str,
        schedule: CronSchedule,
        message: str,
        channel: str | None = None,
        chat_id: str | None = None,
    ) -> CronJob:
        """
        添加新任务。

        Args:
            name: 任务名称
            schedule: 调度配置
            message: 发送给 Agent 的消息
            channel: 结果发送渠道
            chat_id: 结果发送目标

        Returns:
            新创建的任务
        """
        now = _now_ms()

        job = CronJob(
            id=str(uuid.uuid4())[:8],
            name=name,
            enabled=True,
            schedule=schedule,
            payload=CronPayload(
                message=message,
                channel=channel,
                chat_id=chat_id,
            ),
            state=CronJobState(next_run_at_ms=_compute_next_run(schedule, now)),
            created_at_ms=now,
            updated_at_ms=now,
        )

        self._jobs.append(job)
        self._save_jobs()
        self._arm_timer()

        logger.info(f"Cron: added job '{name}' ({job.id})")
        return job

    def remove_job(self, job_id: str) -> bool:
        """
        移除任务。

        Args:
            job_id: 任务 ID

        Returns:
            是否成功移除
        """
        before = len(self._jobs)
        self._jobs = [j for j in self._jobs if j.id != job_id]
        removed = len(self._jobs) < before

        if removed:
            self._save_jobs()
            self._arm_timer()
            logger.info(f"Cron: removed job {job_id}")

        return removed

    def enable_job(self, job_id: str) -> bool:
        """启用任务"""
        for job in self._jobs:
            if job.id == job_id:
                job.enabled = True
                job.state.next_run_at_ms = _compute_next_run(job.schedule, _now_ms())
                job.updated_at_ms = _now_ms()
                self._save_jobs()
                self._arm_timer()
                return True
        return False

    def disable_job(self, job_id: str) -> bool:
        """禁用任务"""
        for job in self._jobs:
            if job.id == job_id:
                job.enabled = False
                job.updated_at_ms = _now_ms()
                self._save_jobs()
                self._arm_timer()
                return True
        return False

    def status(self) -> dict:
        """获取服务状态"""
        return {
            "running": self._running,
            "jobs": len(self._jobs),
            "enabled_jobs": len([j for j in self._jobs if j.enabled]),
            "next_wake_at_ms": self._get_next_wake_ms(),
        }

    async def run_job_now(self, job_id: str) -> bool:
        """
        立即执行任务。

        Args:
            job_id: 任务 ID

        Returns:
            是否成功执行
        """
        for job in self._jobs:
            if job.id == job_id:
                await self._execute_job(job)
                self._save_jobs()
                return True
        return False