"""配置 Schema 定义

使用 Pydantic 模型定义配置结构和验证规则。
"""

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# 支持的语言
Language = Literal["en", "zh"]


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

    @model_validator(mode="after")
    def expand_defaults(self) -> "AgentDefaults":
        """确保默认值中的路径也被展开"""
        if not self.workspace.is_absolute():
            self.workspace = self.workspace.expanduser()
        return self


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


class HeartbeatConfig(BaseModel):
    """Heartbeat 服务配置"""

    enabled: bool = Field(default=False, description="是否启用 Heartbeat")
    every: str = Field(default="30m", description="执行间隔，如 '30m', '1h', '2h30m'")
    active_hours: str | None = Field(
        default=None,
        description="活跃时段，如 '09:00-18:00'，仅在此时段内执行",
    )
    target: str | None = Field(
        default=None,
        description="结果投递目标：'last' 投递到上次交互渠道，或 'channel:chat_id' 指定渠道",
    )
    timeout: int = Field(default=120, description="执行超时时间（秒）")


class HeartbeatConfig(BaseModel):
    """Heartbeat 服务配置"""

    enabled: bool = Field(default=False, description="是否启用 Heartbeat")
    every: str = Field(default="30m", description="执行间隔，如 '30m', '1h', '2h30m'")
    active_hours: str | None = Field(
        default=None,
        description="活跃时段，如 '09:00-18:00'，仅在此时段内执行",
    )
    target: str | None = Field(
        default=None,
        description="结果投递目标：'last' 投递到上次交互渠道，或 'channel:chat_id' 指定渠道",
    )
    timeout: int = Field(default=120, description="执行超时时间（秒）")


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

    @model_validator(mode="after")
    def expand_defaults(self) -> "CronConfig":
        """确保默认值中的路径也被展开"""
        if not self.store_path.is_absolute():
            self.store_path = self.store_path.expanduser()
        return self


class ServicesConfig(BaseModel):
    """服务配置"""

    health_enabled: bool = False
    health_port: int = 8081
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


class LangSmithConfig(BaseModel):
    """LangSmith 配置"""

    enabled: bool = Field(default=False, description="是否启用 LangSmith tracing")
    api_key: str | None = Field(default=None, description="LangSmith API 密钥 (格式: lsv2_pt_...)")
    project: str | None = Field(default=None, description="LangSmith 项目名称")


class Config(BaseModel):
    """完整配置"""

    language: Language = Field(
        default="en",
        description="CLI language (en or zh)",
    )
    agent: AgentDefaults = Field(default_factory=AgentDefaults)
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    channels: ChannelConfig = Field(default_factory=ChannelConfig)
    async_subagents: list[AsyncSubAgentConfig] = Field(default_factory=list)
    cron: CronConfig = Field(default_factory=CronConfig)
    heartbeat: HeartbeatConfig = Field(default_factory=HeartbeatConfig)
    services: ServicesConfig = Field(default_factory=ServicesConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    langsmith: LangSmithConfig = Field(default_factory=LangSmithConfig)

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