"""
DeepCoBot - 极简封装的个人 AI 助理框架

基于 DeepAgents SDK 构建，提供配置驱动和多渠道接入能力。
"""

import json
import os
import sys

from loguru import logger

__version__ = "0.1.0"

# 配置日志
log_level = os.environ.get("DEEPCOBOT_LOG_LEVEL", "INFO").upper()
json_format = os.environ.get("DEEPCOBOT_LOG_JSON", "false").lower() == "true"
log_file = os.environ.get("DEEPCOBOT_LOG_FILE", "")

# 移除默认处理器
logger.remove()

# 根据配置选择格式
if json_format:
    # JSON 格式日志（生产环境）
    def json_sink(message):
        record = message.record
        log_entry = {
            "timestamp": record["time"].isoformat(),
            "level": record["level"].name,
            "message": record["message"],
            "module": record["module"],
            "function": record["function"],
            "line": record["line"],
        }
        if record.get("extra"):
            log_entry["extra"] = record["extra"]
        print(json.dumps(log_entry), file=sys.stderr)

    logger.add(
        json_sink,
        level=log_level,
        format="{message}",
    )
else:
    # 人类可读格式（开发环境）
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )

# 日志文件（如果配置）
if log_file:
    logger.add(
        os.path.expanduser(log_file),
        level=log_level,
        rotation="10 MB",
        retention="7 days",
        compression="gz",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    )


def configure_logging(
    level: str | None = None,
    json_output: bool | None = None,
    file_path: str | None = None,
) -> None:
    """
    配置日志输出。

    Args:
        level: 日志级别（DEBUG, INFO, WARNING, ERROR, CRITICAL）
        json_output: 是否输出 JSON 格式
        file_path: 日志文件路径
    """
    global log_level, json_format

    if level:
        log_level = level.upper()
    if json_output is not None:
        json_format = json_output

    # 重新配置日志
    logger.remove()

    if json_format:

        def json_sink(message):
            record = message.record
            log_entry = {
                "timestamp": record["time"].isoformat(),
                "level": record["level"].name,
                "message": record["message"],
                "module": record["module"],
                "function": record["function"],
                "line": record["line"],
            }
            print(json.dumps(log_entry), file=sys.stderr)

        logger.add(json_sink, level=log_level, format="{message}")
    else:
        logger.add(
            sys.stderr,
            level=log_level,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        )

    if file_path or log_file:
        path = os.path.expanduser(file_path or log_file)
        logger.add(
            path,
            level=log_level,
            rotation="10 MB",
            retention="7 days",
            compression="gz",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        )


__all__ = ["__version__", "logger", "configure_logging"]