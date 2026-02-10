"""Unit and property tests for built-in commands.

Property 14: Version Consistency
Property 3: Empty-Session Guard (copy_last_output)
Validates: Requirements 4.1, 4.2, 4.3, 4.4, copy_last_output 1.1-1.5
"""

import importlib.metadata
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from agent_repl.builtin_commands import get_builtin_commands
from agent_repl.command_registry import CommandRegistry
from agent_repl.exceptions import ClipboardError
from agent_repl.session import Session
from agent_repl.types import (
    AppContext,
    CommandContext,
    Config,
    ConversationTurn,
    TokenStatistics,
)


def _make_app_context():
    """Create a mock AppContext for testing."""
    config = Config(app_name="test-app", app_version="1.0.0", default_model="test-model")
    tui = MagicMock()
    session = MagicMock()
    cmd_reg = CommandRegistry()
    stats = TokenStatistics()

    for cmd in get_builtin_commands():
        cmd_reg.register(cmd)

    return AppContext(
        config=config,
        session=session,
        tui=tui,
        command_registry=cmd_reg,
        stats=stats,
    )


class TestBuiltinCommands:
    def test_get_builtin_commands_returns_all(self):
        cmds = get_builtin_commands()
        names = {c.name for c in cmds}
        assert names == {"help", "quit", "version", "copy"}

    def test_help_displays_commands(self):
        app_ctx = _make_app_context()
        cmd = app_ctx.command_registry.get("help")
        assert cmd is not None
        ctx = CommandContext(args="", app_context=app_ctx)
        cmd.handler(ctx)
        app_ctx.tui.display_text.assert_called_once()
        output = app_ctx.tui.display_text.call_args[0][0]
        assert "/help" in output
        assert "/quit" in output
        assert "/version" in output

    def test_quit_raises_system_exit(self):
        app_ctx = _make_app_context()
        cmd = app_ctx.command_registry.get("quit")
        assert cmd is not None
        ctx = CommandContext(args="", app_context=app_ctx)
        with pytest.raises(SystemExit):
            cmd.handler(ctx)

    def test_version_displays_version(self):
        app_ctx = _make_app_context()
        cmd = app_ctx.command_registry.get("version")
        assert cmd is not None
        ctx = CommandContext(args="", app_context=app_ctx)
        cmd.handler(ctx)
        app_ctx.tui.display_info.assert_called_once()
        output = app_ctx.tui.display_info.call_args[0][0]
        expected_version = importlib.metadata.version("agent_repl")
        assert expected_version in output


class TestCopyCommand:
    def _make_ctx_with_session(self, session):
        """Create a mock AppContext with a real Session."""
        config = Config(app_name="test-app", app_version="1.0.0", default_model="test-model")
        tui = MagicMock()
        cmd_reg = CommandRegistry()
        stats = TokenStatistics()
        for cmd in get_builtin_commands():
            cmd_reg.register(cmd)
        app_ctx = AppContext(
            config=config, session=session, tui=tui, command_registry=cmd_reg, stats=stats
        )
        return app_ctx

    @patch("agent_repl.clipboard.copy_to_clipboard")
    def test_copy_command_success(self, mock_clipboard):
        session = Session()
        session.add_turn(ConversationTurn(role="user", content="question"))
        session.add_turn(ConversationTurn(role="assistant", content="# Answer\nHello world"))
        app_ctx = self._make_ctx_with_session(session)
        cmd = app_ctx.command_registry.get("copy")
        ctx = CommandContext(args="", app_context=app_ctx)
        cmd.handler(ctx)
        mock_clipboard.assert_called_once_with("# Answer\nHello world")
        app_ctx.tui.display_info.assert_called_once_with("Copied to clipboard.")

    def test_copy_command_no_output(self):
        session = Session()
        app_ctx = self._make_ctx_with_session(session)
        cmd = app_ctx.command_registry.get("copy")
        ctx = CommandContext(args="", app_context=app_ctx)
        cmd.handler(ctx)
        app_ctx.tui.display_info.assert_called_once_with("No agent output to copy.")

    @patch(
        "agent_repl.clipboard.copy_to_clipboard",
        side_effect=ClipboardError("Clipboard utility not found: pbcopy"),
    )
    def test_copy_command_clipboard_error(self, mock_clipboard):
        session = Session()
        session.add_turn(ConversationTurn(role="assistant", content="text"))
        app_ctx = self._make_ctx_with_session(session)
        cmd = app_ctx.command_registry.get("copy")
        ctx = CommandContext(args="", app_context=app_ctx)
        cmd.handler(ctx)
        app_ctx.tui.display_error.assert_called_once_with(
            "Clipboard utility not found: pbcopy"
        )

    def test_copy_appears_in_help(self):
        app_ctx = _make_app_context()
        cmd = app_ctx.command_registry.get("help")
        ctx = CommandContext(args="", app_context=app_ctx)
        cmd.handler(ctx)
        output = app_ctx.tui.display_text.call_args[0][0]
        assert "/copy" in output

    def test_copy_command_user_only_history(self):
        session = Session()
        session.add_turn(ConversationTurn(role="user", content="hello"))
        app_ctx = self._make_ctx_with_session(session)
        cmd = app_ctx.command_registry.get("copy")
        ctx = CommandContext(args="", app_context=app_ctx)
        cmd.handler(ctx)
        app_ctx.tui.display_info.assert_called_once_with("No agent output to copy.")


class TestProperty3EmptySessionGuard:
    """Property 3: For sessions with no assistant turns, the copy handler
    shall not invoke the clipboard utility.

    Feature: copy_last_output, Property 3: Empty-Session Guard
    """

    _user_turn_strategy = st.builds(
        ConversationTurn,
        role=st.just("user"),
        content=st.text(min_size=1, max_size=50),
    )

    @settings(max_examples=50)
    @given(turns=st.lists(_user_turn_strategy, min_size=0, max_size=10))
    def test_clipboard_never_called_without_assistant_turns(self, turns):
        session = Session()
        for turn in turns:
            session.add_turn(turn)

        config = Config(app_name="t", app_version="1", default_model="m")
        tui = MagicMock()
        cmd_reg = CommandRegistry()
        stats = TokenStatistics()
        for cmd in get_builtin_commands():
            cmd_reg.register(cmd)
        app_ctx = AppContext(
            config=config, session=session, tui=tui, command_registry=cmd_reg, stats=stats
        )
        cmd = app_ctx.command_registry.get("copy")
        ctx = CommandContext(args="", app_context=app_ctx)

        with patch("agent_repl.clipboard.copy_to_clipboard") as mock_clip:
            cmd.handler(ctx)
            mock_clip.assert_not_called()


class TestProperty14VersionConsistency:
    """Property 14: /version output matches pyproject.toml version.

    Feature: agent_repl, Property 14: Version Consistency
    """

    def test_version_matches_package_metadata(self):
        app_ctx = _make_app_context()
        cmd = app_ctx.command_registry.get("version")
        ctx = CommandContext(args="", app_context=app_ctx)
        cmd.handler(ctx)
        output = app_ctx.tui.display_info.call_args[0][0]
        pkg_version = importlib.metadata.version("agent_repl")
        assert pkg_version in output
