"""Agent 工具函数和常量"""

# HEARTBEAT 文件名常量
HEARTBEAT_FILE = "HEARTBEAT.md"

# 默认 HEARTBEAT.md 内容
DEFAULT_HEARTBEAT_CONTENT = """# Heartbeat Tasks

This file is read periodically by the Heartbeat service.
Write your tasks here, and the agent will execute them on schedule.

## Example Tasks

<!-- Uncomment and modify the following lines to use: -->

<!-- - Check the status of my daily backup -->
<!-- - Generate a summary of today's calendar events -->
<!-- - Review and clean up temporary files in the workspace -->

## Notes

- Tasks are executed according to the heartbeat interval configured in config.toml
- Results can be dispatched to configured channels (Telegram, Discord, etc.)
- Use clear, specific instructions for best results
"""


def sanitize_string(s: str) -> str:
    """
    清理字符串中的无效 UTF-8 代理字符。

    某些 API 返回的数据可能包含损坏的 Unicode 代理字符（如 \udce5），
    这些字符无法被正常编码为 UTF-8。此函数将其替换为 Unicode 替换字符。

    Args:
        s: 输入字符串

    Returns:
        清理后的字符串
    """
    if not isinstance(s, str):
        return str(s) if s is not None else ""

    # 使用 surrogatepass 错误处理来编码再解码，
    # 这样可以将无效的代理字符转换为 Unicode 替换字符
    try:
        return s.encode('utf-8', errors='surrogatepass').decode('utf-8', errors='replace')
    except Exception:
        # 如果仍然失败，逐字符处理
        return ''.join(
            c if ord(c) < 0xD800 or ord(c) > 0xDFFF else '\ufffd'
            for c in s
        )