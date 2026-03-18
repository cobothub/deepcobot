"""Cron 服务

定时任务调度和执行。

与 HeartbeatService 类似，作为消息触发源，通过 on_execute 回调调用 Agent，
结果通过 MessageBus 投递到配置的渠道。
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Coroutine

from loguru import logger

from deepcobot.cron.types import (
    CronJob,
    compute_next_run,
)

if TYPE_CHECKING:
    from deepcobot.bus.queue import MessageBus


class CronService:
    """
    定时任务服务。

    作为消息触发源，类似于 HeartbeatService。
    通过 on_execute 回调调用 Agent，结果通过 MessageBus 投递。

    Attributes:
        store_path: 任务存储文件路径
        bus: 消息总线
        on_execute: 任务执行回调函数
    """

    def __init__(
        self,
        store_path: Path,
        bus: "MessageBus | None" = None,
        on_execute: Callable[[str, str, str], Coroutine[Any, Any, str]] | None = None,
    ):
        """
        初始化 Cron 服务。

        Args:
            store_path: 任务存储文件路径
            bus: 消息总线（可选，用于结果投递）
            on_execute: 任务执行回调，接收 (message, session_key, channel) 返回响应
        """
        self.store_path = Path(store_path).expanduser()
        self.bus = bus
        self.on_execute = on_execute
        self._jobs: list[CronJob] = []
        self._timer_task: asyncio.Task | None = None
        self._running = False

    def _load_jobs(self) -> None:
        """从文件加载任务"""
        if not self.store_path.exists():
            return

        try:
            data = json.loads(self.store_path.read_text(encoding="utf-8"))
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
        self.store_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    async def start(self) -> None:
        """启动定时任务服务"""
        self._running = True
        self._load_jobs()

        # 计算所有启用任务的下次执行时间
        now = datetime.now()
        for job in self._jobs:
            if job.enabled:
                job.next_run_at = compute_next_run(job.schedule, now)

        self._save_jobs()
        self._arm_timer()
        logger.info(f"Cron service started with {len(self._jobs)} jobs")

    async def stop(self) -> None:
        """停止定时任务服务"""
        self._running = False
        if self._timer_task:
            self._timer_task.cancel()
            try:
                await self._timer_task
            except asyncio.CancelledError:
                pass
            self._timer_task = None
        logger.info("Cron service stopped")

    def _get_next_wake_time(self) -> datetime | None:
        """获取最近的执行时间"""
        times = [
            j.next_run_at
            for j in self._jobs
            if j.enabled and j.next_run_at
        ]
        return min(times) if times else None

    def _arm_timer(self) -> None:
        """设置下次执行的定时器"""
        if self._timer_task:
            self._timer_task.cancel()
            self._timer_task = None

        if not self._running:
            return

        next_wake = self._get_next_wake_time()
        if not next_wake:
            return

        now = datetime.now()
        if next_wake <= now:
            # 已经过期，立即执行
            delay = 0
        else:
            delay = (next_wake - now).total_seconds()

        async def tick():
            await asyncio.sleep(delay)
            if self._running:
                await self._on_timer()

        self._timer_task = asyncio.create_task(tick())

    async def _on_timer(self) -> None:
        """定时器触发，执行到期的任务"""
        now = datetime.now()
        due_jobs = [
            j for j in self._jobs
            if j.enabled and j.next_run_at and now >= j.next_run_at
        ]

        for job in due_jobs:
            # 并行执行任务
            asyncio.create_task(self._execute_job(job))

        self._save_jobs()
        self._arm_timer()

    async def _execute_job(self, job: CronJob) -> None:
        """
        执行单个任务。

        Args:
            job: 任务对象
        """
        logger.info(f"Cron: executing job '{job.name}' ({job.id})")

        try:
            if self.on_execute:
                session_key = f"cron:{job.id}"
                channel = job.channel or "cron"

                response = await asyncio.wait_for(
                    self.on_execute(job.message, session_key, channel),
                    timeout=job.timeout,
                )

                # 如果有响应且配置了投递目标，通过 MessageBus 投递
                if response and self.bus and job.channel and job.chat_id:
                    from deepcobot.channels.events import OutboundMessage
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=job.channel,
                        chat_id=job.chat_id,
                        content=response,
                    ))
                    logger.info(f"Cron: job '{job.name}' completed, dispatched to {job.channel}:{job.chat_id}")
                else:
                    logger.info(f"Cron: job '{job.name}' completed (no dispatch)")

                job.last_status = "ok"
                job.last_error = None
            else:
                logger.warning(f"Cron: no on_execute callback for job '{job.name}'")
                job.last_status = "error"
                job.last_error = "No execution callback"

        except asyncio.TimeoutError:
            logger.warning(f"Cron: job '{job.name}' timed out after {job.timeout}s")
            job.last_status = "error"
            job.last_error = f"Timeout after {job.timeout}s"
        except Exception as e:
            logger.error(f"Cron: job '{job.name}' failed: {e}")
            job.last_status = "error"
            job.last_error = str(e)

        job.last_run_at = datetime.now()
        job.next_run_at = compute_next_run(job.schedule, datetime.now())

        self._save_jobs()

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
        return sorted(jobs, key=lambda j: j.next_run_at or datetime.max)

    def get_job(self, job_id: str) -> CronJob | None:
        """
        获取指定任务。

        Args:
            job_id: 任务 ID

        Returns:
            任务对象或 None
        """
        for job in self._jobs:
            if job.id == job_id:
                return job
        return None

    def add_job(
        self,
        name: str,
        schedule: str,
        message: str,
        channel: str | None = None,
        chat_id: str | None = None,
        timeout: int = 120,
        enabled: bool = True,
    ) -> CronJob:
        """
        添加新任务。

        Args:
            name: 任务名称
            schedule: 调度表达式（cron 或 every 间隔）
            message: 发送给 Agent 的消息
            channel: 结果发送渠道
            chat_id: 结果发送目标
            timeout: 执行超时（秒）
            enabled: 是否启用

        Returns:
            新创建的任务
        """
        now = datetime.now()

        job = CronJob(
            id=str(uuid.uuid4())[:8],
            name=name,
            enabled=enabled,
            schedule=schedule,
            message=message,
            channel=channel,
            chat_id=chat_id,
            timeout=timeout,
            next_run_at=compute_next_run(schedule, now) if enabled else None,
        )

        self._jobs.append(job)
        self._save_jobs()
        self._arm_timer()

        logger.info(f"Cron: added job '{name}' ({job.id})")
        return job

    def update_job(
        self,
        job_id: str,
        name: str | None = None,
        schedule: str | None = None,
        message: str | None = None,
        channel: str | None = None,
        chat_id: str | None = None,
        timeout: int | None = None,
    ) -> CronJob | None:
        """
        更新任务。

        Args:
            job_id: 任务 ID
            name: 新名称
            schedule: 新调度
            message: 新消息
            channel: 新渠道
            chat_id: 新目标
            timeout: 新超时

        Returns:
            更新后的任务或 None
        """
        job = self.get_job(job_id)
        if not job:
            return None

        if name is not None:
            job.name = name
        if schedule is not None:
            job.schedule = schedule
            job.next_run_at = compute_next_run(schedule, datetime.now()) if job.enabled else None
        if message is not None:
            job.message = message
        if channel is not None:
            job.channel = channel
        if chat_id is not None:
            job.chat_id = chat_id
        if timeout is not None:
            job.timeout = timeout

        self._save_jobs()
        self._arm_timer()

        logger.info(f"Cron: updated job '{job.name}' ({job.id})")
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
        job = self.get_job(job_id)
        if not job:
            return False

        job.enabled = True
        job.next_run_at = compute_next_run(job.schedule, datetime.now())
        self._save_jobs()
        self._arm_timer()
        logger.info(f"Cron: enabled job '{job.name}' ({job.id})")
        return True

    def disable_job(self, job_id: str) -> bool:
        """禁用任务"""
        job = self.get_job(job_id)
        if not job:
            return False

        job.enabled = False
        job.next_run_at = None
        self._save_jobs()
        self._arm_timer()
        logger.info(f"Cron: disabled job '{job.name}' ({job.id})")
        return True

    def status(self) -> dict:
        """获取服务状态"""
        return {
            "running": self._running,
            "jobs": len(self._jobs),
            "enabled_jobs": len([j for j in self._jobs if j.enabled]),
            "next_wake": self._get_next_wake_time().isoformat() if self._get_next_wake_time() else None,
        }

    async def run_job_now(self, job_id: str) -> bool:
        """
        立即执行任务（异步）。

        Args:
            job_id: 任务 ID

        Returns:
            是否成功触发
        """
        job = self.get_job(job_id)
        if not job:
            return False

        asyncio.create_task(self._execute_job(job))
        logger.info(f"Cron: manually triggered job '{job.name}' ({job.id})")
        return True