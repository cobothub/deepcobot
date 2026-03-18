"""优雅关闭

处理信号和优雅关闭流程。
"""

import asyncio
import signal
from typing import Callable, Coroutine, Any

from loguru import logger


class GracefulShutdown:
    """
    优雅关闭处理器。

    Attributes:
        shutdown_handlers: 关闭处理器列表
    """

    def __init__(self):
        """初始化优雅关闭处理器"""
        self.shutdown_handlers: list[Callable[[], Coroutine[Any, Any, None]]] = []
        self._shutdown_event = asyncio.Event()
        self._shutting_down = False

    def add_handler(
        self,
        handler: Callable[[], Coroutine[Any, Any, None]],
    ) -> None:
        """
        添加关闭处理器。

        Args:
            handler: 异步处理函数
        """
        self.shutdown_handlers.append(handler)

    def setup_signal_handlers(self) -> None:
        """设置信号处理器"""
        loop = asyncio.get_event_loop()

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(
                sig,
                lambda s=sig: asyncio.create_task(self._signal_handler(s)),
            )

        logger.debug("Signal handlers set up")

    async def _signal_handler(self, sig: signal.Signals) -> None:
        """
        信号处理器。

        Args:
            sig: 信号类型
        """
        if self._shutting_down:
            return

        self._shutting_down = True
        logger.info(f"Received signal {sig.name}, initiating graceful shutdown...")

        await self.shutdown()

    async def shutdown(self) -> None:
        """执行优雅关闭"""
        logger.info(f"Running {len(self.shutdown_handlers)} shutdown handlers...")

        for handler in self.shutdown_handlers:
            try:
                await handler()
            except Exception as e:
                logger.error(f"Shutdown handler error: {e}")

        self._shutdown_event.set()
        logger.info("Graceful shutdown completed")

    async def wait_for_shutdown(self) -> None:
        """等待关闭信号"""
        await self._shutdown_event.wait()

    @property
    def is_shutting_down(self) -> bool:
        """是否正在关闭"""
        return self._shutting_down


async def run_with_graceful_shutdown(
    main_task: Callable[[], Coroutine[Any, Any, None]],
    shutdown_handlers: list[Callable[[], Coroutine[Any, Any, None]]] | None = None,
) -> None:
    """
    运行主任务并支持优雅关闭。

    Args:
        main_task: 主任务函数
        shutdown_handlers: 关闭处理器列表
    """
    shutdown = GracefulShutdown()

    if shutdown_handlers:
        for handler in shutdown_handlers:
            shutdown.add_handler(handler)

    shutdown.setup_signal_handlers()

    try:
        await main_task()
    except asyncio.CancelledError:
        pass
    finally:
        if not shutdown.is_shutting_down:
            await shutdown.shutdown()