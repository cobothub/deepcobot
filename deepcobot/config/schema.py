"""配置 Schema 定义

使用 Pydantic 模型定义配置结构和验证规则。
"""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ProviderConfig(BaseModel):
    """LLM 提供商配置"""

    api_key: str = Field(..., description="API 密钥")
    api_base: str | None = Field(None, description="自定义 API 端点")


class TelegramChannelConfig(BaseModel):
    """Telegram 渠道配置"""

    enabled: bool = False
    token: str = ""
    proxy: str | None = None
    allowed_users: list[str] = Field(default_factory=list)


class DiscordChannelConfig(BaseModel):
    """Discord 渠道配置"""

    enabled: bool = False
    token: str = ""
    allowed_users: list[str] = Field(default_factory=list)


class FeishuChannelConfig(BaseModel):
    """飞书渠道配置"""

    enabled: bool = False
    app_id: str = ""
    app_secret: str = ""
    encrypt_key: str | None = None
    verification_token: str | None = None
    allowed_users: list[str] = Field(default_factory=list)


class DingTalkChannelConfig(BaseModel):
    """钉钉渠道配置"""

    enabled: bool = False
    client_id: str = ""
    client_secret: str = ""
    allowed_users: list[str] = Field(default_factory=list)


class WebChannelConfig(BaseModel):
    """Web API 渠道配置"""

    enabled: bool = False
    host: str = "0.0.0.0"
    port: int = 8080
    api_key: str | None = None


class CLIChannelConfig(BaseModel):
    """CLI 渠道配置"""

    enabled: bool = True


class ChannelConfig(BaseModel):
    """所有渠道配置"""

    cli: CLIChannelConfig = Field(default_factory=CLIChannelConfig)
    telegram: TelegramChannelConfig = Field(default_factory=TelegramChannelConfig)
    discord: DiscordChannelConfig = Field(default_factory=DiscordChannelConfig)
    feishu: FeishuChannelConfig = Field(default_factory=FeishuChannelConfig)
    dingtalk: DingTalkChannelConfig = Field(default_factory=DingTalkChannelConfig)
    web: WebChannelConfig = Field(default_factory=WebChannelConfig)


class GatewayConfig(BaseModel):
    """Gateway 配置"""

    enabled: bool = False
    url: str | None = None
    api_key: str | None = None


class AgentDefaults(BaseModel):
    """Agent 默认配置"""

    workspace: Path = Field(
        default=Path("~/.deepcobot/workspace"),
        description="工作空间目录",
    )
    model: str = Field(
        default="anthropic:claude-sonnet-4-6",
        description="LLM 模型，格式: provider:model_name",
    )
    max_tokens: int = Field(default=8192, description="最大输出 token 数")
    system_prompt: str | None = Field(None, description="自定义系统提示词")
    enable_memory: bool = Field(default=True, description="是否启用记忆系统")
    enable_skills: bool = Field(default=True, description="是否启用技能系统")
    auto_approve: bool = Field(default=False, description="是否自动审批工具调用")

    @field_validator("workspace", mode="before")
    @classmethod
    def expand_workspace(cls, v: str | Path) -> Path:
        """扩展工作空间路径中的 ~"""
        if isinstance(v, str):
            v = Path(v)
        return v.expanduser()


class AsyncSubAgentConfig(BaseModel):
    """异步子 Agent 配置"""

    name: str = Field(..., description="子 Agent 名称")
    description: str = Field(default="", description="功能描述")
    graph_id: str = Field(..., description="LangGraph 图 ID")
    url: str = Field(..., description="远程服务器地址")


class CronJobConfig(BaseModel):
    """Cron 任务配置"""

    name: str = Field(..., description="任务名称")
    enabled: bool = True
    schedule: str | None = None  # cron 表达式
    every: str | None = None  # 间隔执行，如 "1h", "30m"
    at: str | None = None  # 一次性执行时间
    message: str = Field(..., description="发送给 Agent 的消息")
    channel: str | None = None  # 结果发送渠道
    chat_id: str | None = None  # 结果发送目标


class CronConfig(BaseModel):
    """Cron 服务配置"""

    enabled: bool = False
    store_path: Path = Field(
        default=Path("~/.deepcobot/cron_jobs.json"),
        description="任务存储路径",
    )
    jobs: list[CronJobConfig] = Field(default_factory=list)

    @field_validator("store_path", mode="before")
    @classmethod
    def expand_store_path(cls, v: str | Path) -> Path:
        """扩展路径中的 ~"""
        if isinstance(v, str):
            v = Path(v)
        return v.expanduser()


class ServicesConfig(BaseModel):
    """服务配置"""

    health_enabled: bool = False
    health_port: int = 8081
    heartbeat_interval: int = 60
    metrics_enabled: bool = False
    metrics_port: int = 9090


class LoggingConfig(BaseModel):
    """日志配置"""

    level: str = "INFO"
    json_format: bool = False
    file: Path | None = None

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        """验证日志级别"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v = v.upper()
        if v not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v


class Config(BaseModel):
    """完整配置"""

    agent: AgentDefaults = Field(default_factory=AgentDefaults)
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    channels: ChannelConfig = Field(default_factory=ChannelConfig)
    async_subagents: list[AsyncSubAgentConfig] = Field(default_factory=list)
    cron: CronConfig = Field(default_factory=CronConfig)
    services: ServicesConfig = Field(default_factory=ServicesConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    model_config = {
        "extra": "ignore",  # 忽略未知字段
    }

    def get_provider(self, name: str) -> ProviderConfig | None:
        """获取指定提供商配置"""
        return self.providers.get(name)

    def get_channels_config(self, channel_name: str) -> dict[str, Any]:
        """获取指定渠道配置"""
        channel_map = {
            "cli": self.channels.cli,
            "telegram": self.channels.telegram,
            "discord": self.channels.discord,
            "feishu": self.channels.feishu,
            "dingtalk": self.channels.dingtalk,
            "web": self.channels.web,
        }
        channel = channel_map.get(channel_name)
        return channel.model_dump() if channel else {}