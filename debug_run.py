#!/usr/bin/env python
"""
调试启动脚本 - 无需命令行，便于 IDE 中调试。

使用方法:
    1. 在 IDE 中直接运行此文件
    2. 或在终端执行: python debug_run.py

配置说明:
    - 修改 CONFIG_PATH 指定配置文件路径
    - 修改 LOG_LEVEL 设置日志级别
    - 修改 AUTO_APPROVE 设置是否自动批准工具调用
"""

import asyncio
from pathlib import Path

# ============== 调试配置 ==============
CONFIG_PATH: str | None = ""  # 设为 None 使用默认配置路径
THREAD_ID: str = "debug-session"
LOG_LEVEL: str = "DEBUG"  # DEBUG, INFO, WARNING, ERROR
AUTO_APPROVE: bool = True
# =====================================


def main():
    """调试入口"""
    # 设置日志级别（在导入 deepcobot 之前）
    import os
    os.environ["DEEPCOBOT_LOG_LEVEL"] = LOG_LEVEL

    # 禁用 LangSmith（调试时通常不需要）
    os.environ["LANGCHAIN_TRACING_V2"] = "false"

    from deepcobot import __version__, apply_config
    from deepcobot.config import load_config
    from deepcobot.agent import AgentSession
    from loguru import logger

    # 加载配置
    config_path = Path(CONFIG_PATH) if CONFIG_PATH else None
    cfg = load_config(config_path)

    # 应用配置
    apply_config(cfg)

    if AUTO_APPROVE:
        cfg.agent.auto_approve = True

    logger.info(f"DeepCoBot v{__version__} 调试模式启动")
    logger.info(f"日志级别: {LOG_LEVEL}")
    logger.info(f"自动批准: {AUTO_APPROVE}")
    logger.info(f"模型: {cfg.agent.model}")
    logger.info(f"工作空间: {cfg.agent.workspace}")

    # 运行会话
    asyncio.run(run_session(cfg))


async def run_session(cfg):
    """运行交互会话"""
    from deepcobot.agent import AgentSession
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.prompt import Prompt
    from loguru import logger

    console = Console()

    session = AgentSession(cfg)
    session.set_thread_id(THREAD_ID)

    console.print("\n[bold green]DeepCoBot 调试模式[/bold green]")
    console.print("[dim]输入消息与 Agent 交互，输入 'exit' 退出，输入 'reset' 重置会话[/dim]\n")

    while True:
        try:
            user_input = Prompt.ask("[bold blue]You[/bold blue]")

            if not user_input.strip():
                continue

            if user_input.lower() in ("exit", "quit"):
                console.print("[yellow]再见！[/yellow]")
                break

            if user_input.lower() == "reset":
                session.reset()
                console.print("[green]会话已重置[/green]")
                continue

            try:
                response = await session.invoke(user_input)

                if response:
                    console.print()
                    md = Markdown(response)
                    console.print(Panel(md, title="[bold green]Assistant[/bold green]"))
                    console.print()

            except Exception as e:
                logger.exception(f"Agent 错误: {e}")
                console.print(f"[red]错误: {e}[/red]")

        except KeyboardInterrupt:
            console.print("\n[yellow]按 Ctrl+C 再次退出，或输入 'exit' 退出[/yellow]")
        except EOFError:
            break


if __name__ == "__main__":
    main()