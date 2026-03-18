"""Prometheus 指标端点

提供 Prometheus 监控指标。
"""

from typing import Any

from loguru import logger

# 可选导入 prometheus_client
try:
    from prometheus_client import Counter, Gauge, Histogram, generate_latest, REGISTRY
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


class MetricsCollector:
    """
    Prometheus 指标收集器。

    收集请求计数、响应时间、活跃会话数等指标。
    """

    def __init__(self, namespace: str = "deepcobot"):
        """
        初始化指标收集器。

        Args:
            namespace: 指标命名空间
        """
        self.namespace = namespace
        self._metrics: dict[str, Any] = {}

        if PROMETHEUS_AVAILABLE:
            self._setup_metrics()

    def _setup_metrics(self) -> None:
        """设置指标"""
        from prometheus_client import Counter, Gauge, Histogram

        # 请求计数
        self._metrics["requests_total"] = Counter(
            f"{self.namespace}_requests_total",
            "Total number of requests",
            ["channel", "method"],
        )

        # 请求延迟
        self._metrics["request_duration_seconds"] = Histogram(
            f"{self.namespace}_request_duration_seconds",
            "Request duration in seconds",
            ["channel"],
            buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
        )

        # 活跃会话数
        self._metrics["active_sessions"] = Gauge(
            f"{self.namespace}_active_sessions",
            "Number of active sessions",
            ["channel"],
        )

        # 消息队列大小
        self._metrics["message_queue_size"] = Gauge(
            f"{self.namespace}_message_queue_size",
            "Size of message queues",
            ["queue_type"],
        )

        # Agent 调用计数
        self._metrics["agent_invocations_total"] = Counter(
            f"{self.namespace}_agent_invocations_total",
            "Total number of agent invocations",
            ["status"],
        )

        # Cron 任务计数
        self._metrics["cron_jobs_total"] = Gauge(
            f"{self.namespace}_cron_jobs_total",
            "Total number of cron jobs",
            ["status"],
        )

        # 渠道状态
        self._metrics["channel_up"] = Gauge(
            f"{self.namespace}_channel_up",
            "Whether a channel is up (1) or down (0)",
            ["channel"],
        )

    def inc_requests(self, channel: str, method: str = "message") -> None:
        """增加请求计数"""
        if PROMETHEUS_AVAILABLE and "requests_total" in self._metrics:
            self._metrics["requests_total"].labels(channel=channel, method=method).inc()

    def observe_request_duration(
        self,
        channel: str,
        duration: float,
    ) -> None:
        """记录请求延迟"""
        if PROMETHEUS_AVAILABLE and "request_duration_seconds" in self._metrics:
            self._metrics["request_duration_seconds"].labels(channel=channel).observe(
                duration
            )

    def set_active_sessions(self, channel: str, count: int) -> None:
        """设置活跃会话数"""
        if PROMETHEUS_AVAILABLE and "active_sessions" in self._metrics:
            self._metrics["active_sessions"].labels(channel=channel).set(count)

    def set_queue_size(self, queue_type: str, size: int) -> None:
        """设置队列大小"""
        if PROMETHEUS_AVAILABLE and "message_queue_size" in self._metrics:
            self._metrics["message_queue_size"].labels(queue_type=queue_type).set(size)

    def inc_agent_invocations(self, status: str = "success") -> None:
        """增加 Agent 调用计数"""
        if PROMETHEUS_AVAILABLE and "agent_invocations_total" in self._metrics:
            self._metrics["agent_invocations_total"].labels(status=status).inc()

    def set_cron_jobs(self, enabled: int, disabled: int) -> None:
        """设置 Cron 任务数量"""
        if PROMETHEUS_AVAILABLE and "cron_jobs_total" in self._metrics:
            self._metrics["cron_jobs_total"].labels(status="enabled").set(enabled)
            self._metrics["cron_jobs_total"].labels(status="disabled").set(disabled)

    def set_channel_status(self, channel: str, up: bool) -> None:
        """设置渠道状态"""
        if PROMETHEUS_AVAILABLE and "channel_up" in self._metrics:
            self._metrics["channel_up"].labels(channel=channel).set(1 if up else 0)

    def get_metrics(self) -> str:
        """获取指标输出"""
        if PROMETHEUS_AVAILABLE:
            return generate_latest(REGISTRY).decode("utf-8")
        return "# Prometheus client not available\n"


# 全局指标收集器
_metrics_collector: MetricsCollector | None = None


def get_metrics_collector() -> MetricsCollector:
    """获取全局指标收集器"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def create_metrics_app(host: str = "0.0.0.0", port: int = 9090):
    """
    创建指标端点 FastAPI 应用。

    Args:
        host: 监听地址
        port: 监听端口

    Returns:
        FastAPI 应用
    """
    try:
        from fastapi import FastAPI, Response
    except ImportError:
        raise ImportError(
            "FastAPI not installed. "
            "Install it with: pip install deepcobot[web]"
        )

    app = FastAPI(
        title="DeepCoBot Metrics",
        docs_url=None,
        redoc_url=None,
    )

    collector = get_metrics_collector()

    @app.get("/metrics")
    async def metrics():
        """Prometheus 指标端点"""
        return Response(
            content=collector.get_metrics(),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    return app


async def run_metrics_server(
    host: str = "0.0.0.0",
    port: int = 9090,
) -> None:
    """
    运行指标服务器。

    Args:
        host: 监听地址
        port: 监听端口
    """
    import uvicorn

    app = create_metrics_app(host, port)
    config = uvicorn.Config(app, host=host, port=port, log_level="error")
    server = uvicorn.Server(config)

    logger.info(f"Metrics server starting on {host}:{port}")
    await server.serve()