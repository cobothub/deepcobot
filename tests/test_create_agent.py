# !/usr/bin/env python3
# -*- coding:utf-8 -*-

# @Time    : 2026/03/19 10:08
# @Author  : geminrong
# @FileName: test_create_agent.py
"""
测试创建 Agent 并将 graph 转换为图片

说明:
- create_deep_agent 默认包含的中间件:
  1. TodoListMiddleware - 任务列表管理 (有 after_model 节点)
  2. MemoryMiddleware - 记忆系统 (有 before_agent 节点)，需要 enable_memory=True
  3. SkillsMiddleware - 技能系统 (有 before_agent 节点)，需要 enable_skills=True
  4. FilesystemMiddleware - 文件系统操作
  5. SubAgentMiddleware - 子 Agent 管理 (通过 wrap_model_call 工作，不在 graph 中显示)
  6. SummarizationMiddleware - 摘要中间件 (通过 wrap_model_call 工作，不在 graph 中显示)
  7. AnthropicPromptCachingMiddleware - Anthropic 缓存优化
  8. PatchToolCallsMiddleware - 工具调用补丁 (有 before_agent 节点)

注意: SubAgentMiddleware 和 SummarizationMiddleware 通过 wrap_model_call 方法工作，
不会在 graph 可视化中显示为独立节点。
"""

import tempfile
from pathlib import Path

import pytest

from deepcobot.config import Config, AgentDefaults, ProviderConfig
from deepcobot.agent.factory import create_agent


def test_create_agent_and_save_graph_image():
    """
    测试创建 Agent 并将 graph 转换为图片保存

    测试步骤:
    1. 创建测试配置（启用 memory 和 skills）
    2. 调用 create_agent 创建 agent
    3. 获取 graph 并转换为图片
    4. 保存图片到临时目录
    """
    # 使用临时目录作为工作空间
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)

        # 创建测试配置 - 启用所有功能以展示完整的 graph
        config = Config(
            agent=AgentDefaults(
                workspace=workspace,
                model="anthropic:claude-sonnet-4-6",
                enable_memory=True,   # 启用记忆系统
                enable_skills=True,   # 启用技能系统
                auto_approve=True,
            ),
            providers={
                "anthropic": ProviderConfig(
                    api_key="test-api-key",
                    api_base=None,
                )
            },
        )

        # 创建 Agent
        result = create_agent(config)
        graph = result["graph"]

        # 验证 graph 创建成功
        assert graph is not None
        print(f"Agent created successfully!")
        print(f"Workspace: {result['workspace']}")

        # 获取graph的可视化表示
        graph_obj = graph.get_graph()

        # 打印所有节点
        print("\n=== Graph 节点 ===")
        for node in graph_obj.nodes:
            print(f"  - {node}")

        # 方法1: 使用 mermaid 生成图
        mermaid_code = graph_obj.draw_mermaid()
        print("\n=== Mermaid 代码 ===")
        print(mermaid_code)

        # 保存 Mermaid 代码到文件
        mermaid_file = workspace / "agent_graph.mmd"
        mermaid_file.write_text(mermaid_code, encoding="utf-8")
        print(f"\nMermaid 代码已保存到: {mermaid_file}")

        # 方法2: 使用 grandalf 生成 ASCII 艺术图（需要安装 grandalf）
        ascii_file = None
        try:
            ascii_art = graph_obj.draw_ascii()
            print("\n=== ASCII Art ===")
            print(ascii_art)

            # 保存 ASCII 艺术
            ascii_file = workspace / "agent_graph.txt"
            ascii_file.write_text(ascii_art, encoding="utf-8")
            print(f"ASCII 图已保存到: {ascii_file}")
        except Exception as e:
            print(f"生成 ASCII 图失败: {e}")

        # 方法3: 尝试使用 draw_png 方法（需要 pygraphviz/graphviz）
        try:
            png_path = workspace / "agent_graph.png"
            png_data = graph_obj.draw_png()
            if png_data:
                png_path.write_bytes(png_data)
                print(f"PNG 图片已保存到: {png_path}")
        except Exception as e:
            print(f"生成 PNG 图片失败（可能需要安装 pygraphviz）: {e}")

        # 验证 Mermaid 文件创建（必须成功）
        assert mermaid_file.exists(), "Mermaid 文件应该存在"
        # ASCII 文件可选，如果生成成功则验证
        if ascii_file:
            assert ascii_file.exists(), "ASCII 艺术文件应该存在"

        # 验证关键节点存在
        nodes = list(graph_obj.nodes)
        assert "model" in nodes, "model 节点应该存在"
        assert "tools" in nodes, "tools 节点应该存在"
        # 当 enable_memory=True 时，MemoryMiddleware 节点应该存在
        assert "MemoryMiddleware.before_agent" in nodes, "MemoryMiddleware 节点应该存在"
        # 当 enable_skills=True 时，SkillsMiddleware 节点应该存在
        assert "SkillsMiddleware.before_agent" in nodes, "SkillsMiddleware 节点应该存在"


def test_create_agent_minimal_graph():
    """
    测试创建最小化 Agent（禁用 memory 和 skills），展示简化的 graph
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)

        # 创建最小化配置
        config = Config(
            agent=AgentDefaults(
                workspace=workspace,
                model="anthropic:claude-sonnet-4-6",
                enable_memory=False,
                enable_skills=False,
                auto_approve=True,
            ),
            providers={
                "anthropic": ProviderConfig(
                    api_key="test-api-key",
                )
            },
        )

        result = create_agent(config)
        graph = result["graph"]

        # 获取 graph 结构
        graph_obj = graph.get_graph()

        print("\n=== 最小化 Graph 节点 ===")
        for node in graph_obj.nodes:
            print(f"  - {node}")

        mermaid_code = graph_obj.draw_mermaid()
        print("\n=== 最小化 Mermaid 代码 ===")
        print(mermaid_code)

        # 验证最小化节点
        nodes = list(graph_obj.nodes)
        assert "model" in nodes
        assert "tools" in nodes
        # 禁用时不应存在这些节点
        assert "MemoryMiddleware.before_agent" not in nodes
        assert "SkillsMiddleware.before_agent" not in nodes


def test_create_agent_async_and_save_graph():
    """
    测试异步创建 Agent 并保存 graph 图片
    """
    import asyncio

    async def _test():
        from deepcobot.agent.factory import create_agent_async

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)

            config = Config(
                agent=AgentDefaults(
                    workspace=workspace,
                    model="anthropic:claude-sonnet-4-6",
                    enable_memory=True,
                    enable_skills=True,
                    auto_approve=True,
                ),
                providers={
                    "anthropic": ProviderConfig(
                        api_key="test-api-key",
                    )
                },
            )

            result = await create_agent_async(config)
            graph = result["graph"]

            assert graph is not None
            print(f"Async Agent created successfully!")

            # 获取 graph 可视化
            graph_obj = graph.get_graph()
            mermaid_code = graph_obj.draw_mermaid()

            # 保存
            mermaid_file = workspace / "agent_graph_async.mmd"
            mermaid_file.write_text(mermaid_code, encoding="utf-8")
            print(f"异步创建的 Graph 已保存到: {mermaid_file}")

            return True

    result = asyncio.run(_test())
    assert result


if __name__ == "__main__":
    # 直接运行测试
    print("=" * 60)
    print("测试 1: 完整 Agent (启用 memory 和 skills)")
    print("=" * 60)
    test_create_agent_and_save_graph_image()

    print("\n" + "=" * 60)
    print("测试 2: 最小化 Agent (禁用 memory 和 skills)")
    print("=" * 60)
    test_create_agent_minimal_graph()

    print("\n" + "=" * 60)
    print("测试 3: 异步创建 Agent")
    print("=" * 60)
    test_create_agent_async_and_save_graph()