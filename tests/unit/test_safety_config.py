"""Tests for safety config parsing."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest import mock

import yaml

from anteroom.config import SafetyConfig, load_config


def _write_config(tmpdir: Path, config_dict: dict) -> Path:
    config_path = tmpdir / "config.yaml"
    config_path.write_text(yaml.dump(config_dict))
    return config_path


class TestSafetyConfig:
    def test_default_safety_config(self) -> None:
        cfg = SafetyConfig()
        assert cfg.enabled is True
        assert cfg.approval_timeout == 120
        assert cfg.bash.enabled is True
        assert cfg.write_file.enabled is True
        assert cfg.custom_patterns == []
        assert cfg.sensitive_paths == []

    def test_app_config_has_safety(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = _write_config(
                Path(tmpdir),
                {"ai": {"base_url": "http://localhost:1234", "api_key": "test"}},
            )
            cfg = load_config(config_path)
            assert isinstance(cfg.safety, SafetyConfig)
            assert cfg.safety.enabled is True

    def test_safety_section_parsed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = _write_config(
                Path(tmpdir),
                {
                    "ai": {"base_url": "http://localhost:1234", "api_key": "test"},
                    "safety": {
                        "enabled": True,
                        "approval_timeout": 60,
                        "bash": {"enabled": False},
                        "write_file": {"enabled": True},
                        "custom_patterns": ["docker system prune"],
                        "sensitive_paths": ["~/.my_secret"],
                    },
                },
            )
            cfg = load_config(config_path)
            assert cfg.safety.approval_timeout == 60
            assert cfg.safety.bash.enabled is False
            assert cfg.safety.write_file.enabled is True
            assert "docker system prune" in cfg.safety.custom_patterns
            assert "~/.my_secret" in cfg.safety.sensitive_paths

    def test_missing_safety_section_uses_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = _write_config(
                Path(tmpdir),
                {"ai": {"base_url": "http://localhost:1234", "api_key": "test"}},
            )
            cfg = load_config(config_path)
            assert cfg.safety.enabled is True
            assert cfg.safety.approval_timeout == 120

    def test_timeout_clamped_low(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = _write_config(
                Path(tmpdir),
                {
                    "ai": {"base_url": "http://localhost:1234", "api_key": "test"},
                    "safety": {"approval_timeout": 1},
                },
            )
            cfg = load_config(config_path)
            assert cfg.safety.approval_timeout == 10

    def test_timeout_clamped_high(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = _write_config(
                Path(tmpdir),
                {
                    "ai": {"base_url": "http://localhost:1234", "api_key": "test"},
                    "safety": {"approval_timeout": 9999},
                },
            )
            cfg = load_config(config_path)
            assert cfg.safety.approval_timeout == 600

    def test_env_var_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = _write_config(
                Path(tmpdir),
                {"ai": {"base_url": "http://localhost:1234", "api_key": "test"}},
            )
            with mock.patch.dict(os.environ, {"AI_CHAT_SAFETY_ENABLED": "false"}):
                cfg = load_config(config_path)
                assert cfg.safety.enabled is False

    def test_safety_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = _write_config(
                Path(tmpdir),
                {
                    "ai": {"base_url": "http://localhost:1234", "api_key": "test"},
                    "safety": {"enabled": False},
                },
            )
            cfg = load_config(config_path)
            assert cfg.safety.enabled is False
