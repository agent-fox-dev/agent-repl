"""Tests for config_loader module.

Covers Requirements 10.10-10.13 and Property 20.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from agent_repl.config_loader import LoadedConfig, load_config


class TestValidToml:
    """Requirement 10.10: Load plugin paths from [plugins] section."""

    def test_load_with_plugins(self, tmp_path: Path):
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            '[plugins]\npaths = ["myapp.plugins.foo", "myapp.plugins.bar"]\n',
            encoding="utf-8",
        )
        result = load_config(str(config_file))
        assert result.plugin_paths == ["myapp.plugins.foo", "myapp.plugins.bar"]
        assert "plugins" in result.raw

    def test_load_empty_paths(self, tmp_path: Path):
        config_file = tmp_path / "config.toml"
        config_file.write_text("[plugins]\npaths = []\n", encoding="utf-8")
        result = load_config(str(config_file))
        assert result.plugin_paths == []

    def test_load_no_plugins_section(self, tmp_path: Path):
        config_file = tmp_path / "config.toml"
        config_file.write_text('[other]\nkey = "value"\n', encoding="utf-8")
        result = load_config(str(config_file))
        assert result.plugin_paths == []
        assert result.raw["other"]["key"] == "value"

    def test_load_no_paths_key(self, tmp_path: Path):
        config_file = tmp_path / "config.toml"
        config_file.write_text('[plugins]\nother_key = "value"\n', encoding="utf-8")
        result = load_config(str(config_file))
        assert result.plugin_paths == []


class TestPluginSpecificConfig:
    """Requirement 10.13: Plugin-specific configuration accessible via raw."""

    def test_plugin_config_accessible(self, tmp_path: Path):
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            '[plugins]\npaths = []\n\n[plugins.my_plugin]\napi_key = "secret"\n',
            encoding="utf-8",
        )
        result = load_config(str(config_file))
        assert result.raw["plugins"]["my_plugin"]["api_key"] == "secret"


class TestMissingFile:
    """Requirement 10.11: Missing file creates default template."""

    def test_creates_template(self, tmp_path: Path):
        config_file = tmp_path / "config.toml"
        result = load_config(str(config_file))
        assert isinstance(result, LoadedConfig)
        assert result.plugin_paths == []
        assert result.raw == {}
        assert config_file.exists()
        content = config_file.read_text(encoding="utf-8")
        assert "[plugins]" in content

    def test_creates_parent_dirs(self, tmp_path: Path):
        config_file = tmp_path / "subdir" / "nested" / "config.toml"
        result = load_config(str(config_file))
        assert isinstance(result, LoadedConfig)
        assert config_file.exists()


class TestMalformedToml:
    """Requirement 10.12: Malformed TOML logs warning, returns empty."""

    def test_invalid_toml(self, tmp_path: Path, caplog: pytest.LogCaptureFixture):
        config_file = tmp_path / "config.toml"
        config_file.write_text("this is not valid toml [[[", encoding="utf-8")
        with caplog.at_level(logging.WARNING):
            result = load_config(str(config_file))
        assert result.plugin_paths == []
        assert result.raw == {}
        assert "Malformed TOML" in caplog.text

    def test_empty_file(self, tmp_path: Path):
        config_file = tmp_path / "config.toml"
        config_file.write_text("", encoding="utf-8")
        result = load_config(str(config_file))
        assert result.plugin_paths == []
        assert result.raw == {}


class TestLoadedConfigDefaults:
    """LoadedConfig dataclass defaults."""

    def test_defaults(self):
        lc = LoadedConfig()
        assert lc.plugin_paths == []
        assert lc.raw == {}


# --- Property-based tests ---


@pytest.mark.property
class TestConfigLoaderProperties:
    @given(
        content=st.one_of(
            st.just(b""),
            st.just(b"invalid toml [[["),
            st.just(b'[plugins]\npaths = ["a", "b"]\n'),
            st.just(b"[other]\nkey = 1\n"),
            st.binary(min_size=0, max_size=100),
        ),
    )
    def test_property20_config_file_resilience(self, content: bytes):
        """Property 20: Never raises for any file state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.toml"
            config_file.write_bytes(content)
            # Must not raise
            result = load_config(str(config_file))
            assert isinstance(result, LoadedConfig)

    def test_property20_missing_file(self):
        """Property 20: Missing file does not raise."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "nonexistent.toml"
            result = load_config(str(config_file))
            assert isinstance(result, LoadedConfig)
