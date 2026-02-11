"""Tests for the exception hierarchy."""

import pytest

from agent_repl.exceptions import (
    AgentError,
    AgentReplError,
    ClipboardError,
    ConfigError,
    FileContextError,
    PluginError,
)


class TestExceptionHierarchy:
    def test_base_exception(self):
        e = AgentReplError("base error")
        assert str(e) == "base error"
        assert isinstance(e, Exception)

    def test_agent_error_inherits(self):
        e = AgentError("agent failed")
        assert isinstance(e, AgentReplError)
        assert isinstance(e, Exception)
        assert str(e) == "agent failed"

    def test_plugin_error_inherits(self):
        e = PluginError("plugin failed")
        assert isinstance(e, AgentReplError)

    def test_config_error_inherits(self):
        e = ConfigError("config bad")
        assert isinstance(e, AgentReplError)

    def test_clipboard_error_inherits(self):
        e = ClipboardError("no clipboard")
        assert isinstance(e, AgentReplError)

    def test_file_context_error_inherits(self):
        e = FileContextError("file not found")
        assert isinstance(e, AgentReplError)


class TestExceptionCatching:
    def test_catch_all_with_base(self):
        exceptions = [
            AgentError("a"),
            PluginError("p"),
            ConfigError("c"),
            ClipboardError("cb"),
            FileContextError("fc"),
        ]
        for exc in exceptions:
            with pytest.raises(AgentReplError):
                raise exc

    def test_catch_specific(self):
        with pytest.raises(AgentError):
            raise AgentError("specific")

    def test_does_not_catch_wrong_type(self):
        with pytest.raises(AgentError):
            try:
                raise AgentError("agent")
            except PluginError:
                pytest.fail("Should not catch AgentError as PluginError")


class TestExceptionMessages:
    def test_empty_message(self):
        e = AgentReplError()
        assert str(e) == ""

    def test_multiline_message(self):
        msg = "Line 1\nLine 2"
        e = AgentError(msg)
        assert str(e) == msg

    def test_with_cause(self):
        cause = ValueError("root cause")
        e = PluginError("plugin failed")
        e.__cause__ = cause
        assert e.__cause__ is cause
