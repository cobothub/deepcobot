"""
DeepCoBot CLI 入口点。

支持通过 python -m deepcobot 启动 CLI。
"""

from deepcobot.cli.commands import app

if __name__ == "__main__":
    app()