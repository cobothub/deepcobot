"""健康检查端点

提供 HTTP 健康检查接口。
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from loguru import logger


@dataclass
class HealthStatus:
    """健康状态"""

    healthy: bool
    status: str
    checks: dict[str, bool]
    timestamp: str
    uptime_seconds: float


class HealthChecker:
    """
    健康检查器，提供健康检查端点。

    Attributes:
        checks: 检查函数字典
    """

    def __init__(self):
        """初始化健康检查器"""
        self.checks: dict[str, Callable[[], bool]] = {}
        self._start_time = datetime.now()

    def add_check(self, name: str, check: Callable[[], bool]) -> None:
        """
        添加健康检查函数。

        Args:
            name: 检查名称
            check: 检查函数（返回 True 表示健康）
        """
        self.checks[name] = check
        logger.debug(f"Health check added: {name}")

    def check(self) -> HealthStatus:
        """
        执行所有健康检查。

        Returns:
            健康状态
        """
        checks = {}
        for name, check_fn in self.checks.items():
            try:
                checks[name] = check_fn()
            except Exception as e:
                checks[name] = False
                logger.warning(f"Health check '{name}' failed: {e}")

        all_healthy = all(checks.values()) if checks else True
        status = "healthy" if all_healthy else "unhealthy"

        uptime = (datetime.now() - self._start_time).total_seconds()

        return HealthStatus(
            healthy=all_healthy,
            status=status,
            checks=checks,
            timestamp=datetime.now().isoformat(),
            uptime_seconds=uptime,
        )

    def check_ready(self) -> bool:
        """
        检查服务是否就绪。

        Returns:
            是否就绪
        """
        # 可以添加更多就绪检查逻辑
        return True

    def check_live(self) -> bool:
        """
        检查服务是否存活。

        Returns:
            是否存活
        """
        return True

    def get_status_dict(self) -> dict[str, Any]:
        """
        获取状态字典（用于 JSON 响应）。

        Returns:
            状态字典
        """
        status = self.check()
        return {
            "status": status.status,
            "healthy": status.healthy,
            "timestamp": status.timestamp,
            "uptime_seconds": status.uptime_seconds,
            "checks": status.checks,
        }


def create_health_app(
    health_checker: HealthChecker,
    host: str = "0.0.0.0",
    port: int = 8081,
):
    """
    创建健康检查 FastAPI 应用。

    Args:
        health_checker: 健康检查器
        host: 监听地址
        port: 监听端口

    Returns:
        FastAPI 应用
    """
    try:
        from fastapi import FastAPI, Response
        import uvicorn
    except ImportError:
        raise ImportError(
            "FastAPI not installed. "
            "Install it with: pip install deepcobot[web]"
        )

    app = FastAPI(
        title="DeepCoBot Health",
        docs_url=None,
        redoc_url=None,
    )

    @app.get("/health")
    async def health():
        """健康检查端点"""
        status = health_checker.get_status_dict()
        code = 200 if status["healthy"] else 503
        return Response(
            content=__import__("json").dumps(status),
            status_code=code,
            media_type="application/json",
        )

    @app.get("/ready")
    async def ready():
        """就绪检查端点"""
        if health_checker.check_ready():
            return {"status": "ready"}
        return Response(
            content=__import__("json").dumps({"status": "not ready"}),
            status_code=503,
            media_type="application/json",
        )

    @app.get("/live")
    async def live():
        """存活检查端点"""
        if health_checker.check_live():
            return {"status": "alive"}
        return Response(
            content=__import__("json").dumps({"status": "dead"}),
            status_code=503,
            media_type="application/json",
        )

    return app


async def run_health_server(
    health_checker: HealthChecker,
    host: str = "0.0.0.0",
    port: int = 8081,
) -> None:
    """
    运行健康检查服务器。

    Args:
        health_checker: 健康检查器
        host: 监听地址
        port: 监听端口
    """
    import uvicorn

    app = create_health_app(health_checker, host, port)
    config = uvicorn.Config(app, host=host, port=port, log_level="error")
    server = uvicorn.Server(config)

    logger.info(f"Health check server starting on {host}:{port}")
    await server.serve()