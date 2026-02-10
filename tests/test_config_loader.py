"""Unit tests for the config loader module.

Validates: Requirements 1.1-1.4, 2.1-2.4, 3.1-3.3, 4.1-4.3
Correctness Properties: P1-P6
"""

import os
from pathlib import Path

from agent_repl.config_loader import DEFAULT_CONFIG_TEMPLATE, load_config


class TestLoadConfig:
    def test_valid_toml(self, tmp_path: Path):
        af_dir = tmp_path / ".af"
        af_dir.mkdir()
        (af_dir / "plugins.toml").write_text(
            '[plugins]\nmodules = ["my_plugin"]\n'
        )
        result = load_config(tmp_path)
        assert result == {"plugins": {"modules": ["my_plugin"]}}

    def test_missing_file_creates_default(self, tmp_path: Path):
        """Property 1: Default File Creation.
        Validates: Requirements 1.1, 1.2, 1.3.
        """
        result = load_config(tmp_path)

        config_path = tmp_path / ".af" / "plugins.toml"
        assert result == {"plugins": {"modules": []}}
        assert config_path.exists()
        assert config_path.read_text() == DEFAULT_CONFIG_TEMPLATE

    def test_missing_dir_creates_default(self, tmp_path: Path):
        """Validates: Requirement 1.2 — CONFIG_DIR created when missing."""
        af_dir = tmp_path / ".af"
        assert not af_dir.exists()

        load_config(tmp_path)

        assert af_dir.is_dir()
        assert (af_dir / "plugins.toml").exists()

    def test_malformed_toml_returns_empty(self, tmp_path: Path):
        af_dir = tmp_path / ".af"
        af_dir.mkdir()
        (af_dir / "plugins.toml").write_text("this is not valid toml [[[")
        result = load_config(tmp_path)
        assert result == {}

    def test_empty_file_returns_empty(self, tmp_path: Path):
        af_dir = tmp_path / ".af"
        af_dir.mkdir()
        (af_dir / "plugins.toml").write_text("")
        result = load_config(tmp_path)
        assert result == {}

    def test_toml_with_multiple_sections(self, tmp_path: Path):
        af_dir = tmp_path / ".af"
        af_dir.mkdir()
        (af_dir / "plugins.toml").write_text(
            '[plugins]\nmodules = ["a", "b"]\n\n[settings]\nkey = "value"\n'
        )
        result = load_config(tmp_path)
        assert result["plugins"]["modules"] == ["a", "b"]
        assert result["settings"]["key"] == "value"


class TestDefaultConfigCreation:
    """Tests for default config file creation and error handling.

    Validates correctness properties P1-P6.
    """

    def test_default_template_is_valid_toml(self):
        """Property 3: Template Validity.
        Validates: Requirements 2.2, 2.3, 2.4.
        """
        import io
        import tomllib

        result = tomllib.load(io.BytesIO(DEFAULT_CONFIG_TEMPLATE.encode()))
        assert "plugins" in result
        assert result["plugins"]["modules"] == []

    def test_existing_file_not_overwritten(self, tmp_path: Path):
        """Property 4: Existing File Preservation.
        Validates: Requirements 4.1, 4.3.
        """
        af_dir = tmp_path / ".af"
        af_dir.mkdir()
        custom_content = '[plugins]\nmodules = ["custom"]\n'
        (af_dir / "plugins.toml").write_text(custom_content)

        result = load_config(tmp_path)

        assert (af_dir / "plugins.toml").read_text() == custom_content
        assert result == {"plugins": {"modules": ["custom"]}}

    def test_write_permission_denied(self, tmp_path: Path):
        """Property 5: Write Error Graceful Degradation.
        Validates: Requirements 3.1, 3.2, 3.3.
        """
        af_dir = tmp_path / ".af"
        af_dir.mkdir()
        os.chmod(af_dir, 0o444)

        try:
            result = load_config(tmp_path)
            assert result == {"plugins": {"modules": []}}
        finally:
            os.chmod(af_dir, 0o755)

    def test_idempotency(self, tmp_path: Path):
        """Property 6: Idempotency.
        Validates: Requirements 1.1, 4.3.
        """
        result1 = load_config(tmp_path)
        config_path = tmp_path / ".af" / "plugins.toml"
        content_after_first = config_path.read_text()

        result2 = load_config(tmp_path)
        content_after_second = config_path.read_text()

        assert result1 == result2
        assert content_after_first == content_after_second
        assert content_after_second == DEFAULT_CONFIG_TEMPLATE

    def test_created_file_is_readable(self, tmp_path: Path):
        """Property 2: Default Return Value Consistency (round-trip).
        Create default, then read it back via load_config.
        """
        result1 = load_config(tmp_path)
        result2 = load_config(tmp_path)

        assert result1 == {"plugins": {"modules": []}}
        assert result1 == result2

    def test_creation_logs_info(self, tmp_path: Path, caplog):
        """Validates: Requirement 1.4 — info log on creation."""
        import logging

        with caplog.at_level(logging.INFO, logger="agent_repl.config_loader"):
            load_config(tmp_path)

        assert any("Created default config at" in msg for msg in caplog.messages)

    def test_write_error_logs_warning(self, tmp_path: Path, caplog):
        """Validates: Requirements 3.1, 3.2 — warning log on write error."""
        import logging

        af_dir = tmp_path / ".af"
        af_dir.mkdir()
        os.chmod(af_dir, 0o444)

        try:
            with caplog.at_level(logging.WARNING, logger="agent_repl.config_loader"):
                load_config(tmp_path)
            assert any(
                "Could not create config" in msg for msg in caplog.messages
            )
        finally:
            os.chmod(af_dir, 0o755)
