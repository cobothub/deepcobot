"""测试配置"""

import pytest


@pytest.fixture
def tmp_config_dir(tmp_path, monkeypatch):
    """临时配置目录"""
    config_dir = tmp_path / ".deepcobot"
    config_dir.mkdir()
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    return config_dir