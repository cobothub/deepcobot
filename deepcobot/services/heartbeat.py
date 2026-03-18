"""心跳服务

定期检查系统各组件状态。
"""

import asyncio
import time
from typing import Any, Callable, Coroutine

from loguru import logger


class HeartbeatService:
    """
    心跳服务，定期检查系统状态。

    Attributes:
        interval: 检查间隔（秒）
        checks: 检查函数列表
    """

    def __init__(
        self,
        interval: int = 60,
        checks: list[Callable[[], Coroutine[Any, Any, bool]]] | None = None,
    ):
        """
        初始化心跳服务。

        Args:
            interval: 检查间隔（秒）
            checks: 检查函数列表（返回 True 表示健康）
        """
        self.interval = interval
        self.checks = checks or []
        self._running = False
        self._task: asyncio.Task | None = None
        self._last_check: dict[str, Any] = {}

    def add_check(
        self,
        name: str,
        check: Callable[[], Coroutine[Any, Any, bool]],
    ) -> None:
        """
        添加健康检查函数。

        Args:
            name: 检查名称
            check: 检查函数
        """
        self.checks.append(check)

    async def start(self) -> None:
        """启动心跳服务"""
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info(f"Heartbeat service started (interval: {self.interval}s)")

    async def stop(self) -> None:
        """停止心跳服务"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Heartbeat service stopped")

    async def _loop(self) -> None:
        """心跳循环"""
        while self._running:
            try:
                await self._run_checks()
                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                await asyncio.sleep(self.interval)

    async def _run_checks(self) -> None:
        """运行所有检查"""
        start_time = time.time()
        results = {}

        for check in self.checks:
            try:
                result = await check()
                results[check.__name__] = result
            except Exception as e:
                results[check.__name__] = False
                logger.warning(f"Health check failed: {check.__name__}: {e}")

        duration = time.time() - start_time
        self._last_check = {
            "timestamp": start_time,
            "duration_ms": int(duration * 1000),
            "results": results,
            "healthy": all(results.values()) if results else True,
        }

        logger.debug(f"Heartbeat check completed in {duration:.2f}s")

    def get_status(self) -> dict[str, Any]:
        """获取最后检查状态"""
        return self._last_check