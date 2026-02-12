"""Integration tests for agent_repl.

End-to-end tests verifying the full REPL loop, command dispatch,
plugin loading, error recovery, and CLI invocation.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_repl.app import App
from agent_repl.command_registry import CommandRegistry
from agent_repl.plugin_registry import PluginRegistry
from agent_repl.repl import REPL
from agent_repl.session import Session
from agent_repl.types import (
    CommandContext,
    Config,
    ConversationTurn,
    MessageContext,
    PluginContext,
    SlashCommand,
    StreamEvent,
    StreamEventType,
)

# --- Echo Agent for Integration Tests ---


class IntegrationEchoAgent:
    """Minimal echo agent for integration tests."""

    name = "Echo"
    description = "Integration test echo agent"
    default_model = "echo-test"

    def get_commands(self) -> list[SlashCommand]:
        return []

    async def on_load(self, context: PluginContext) -> None:
        pass

    async def on_unload(self) -> None:
        pass

    def get_status_hints(self) -> list[str]:
        return []

    async def send_message(
        self, context: MessageContext
    ) -> AsyncIterator[StreamEvent]:
        return self._stream(context)

    async def _stream(
        self, context: MessageContext
    ) -> AsyncIterator[StreamEvent]:
        yield StreamEvent(
            type=StreamEventType.TEXT_DELTA,
            data={"text": f"Echo: {context.message}"},
        )
        yield StreamEvent(
            type=StreamEventType.USAGE,
            data={"input_tokens": 10, "output_tokens": 5},
        )

    async def compact_history(self, session: object) -> str:
        return "Summary"


def _make_tui(*inputs: str | BaseException) -> MagicMock:
    """Create a mock TUI that returns inputs then raises EOFError."""
    tui = MagicMock()
    effects: list[str | BaseException] = list(inputs) + [EOFError()]
    tui.prompt_input = AsyncMock(side_effect=effects)
    tui.show_error = MagicMock()
    tui.show_info = MagicMock()
    tui.show_markdown = MagicMock()
    tui.start_spinner = MagicMock()
    tui.stop_spinner = MagicMock()
    tui.start_live_text = MagicMock()
    tui.append_live_text = MagicMock()
    tui.finalize_live_text = MagicMock()
    tui.set_last_response = MagicMock()
    tui.show_tool_use = MagicMock()
    tui.show_tool_result = MagicMock()
    tui.clear_collapsed_results = MagicMock()
    tui.prompt_approval = AsyncMock(return_value="approve")
    tui.prompt_choice = AsyncMock(return_value={"index": 0, "value": "opt"})
    tui.prompt_text_input = AsyncMock(return_value="text")
    return tui


class TestFullREPLLoop:
    """Test full REPL loop with echo agent."""

    @pytest.mark.asyncio
    async def test_send_message_receive_echo_quit(self):
        """Start → send message → receive echo → /quit."""
        from agent_repl.builtin_commands import BuiltinCommandsPlugin
        session = Session()
        tui = _make_tui("hello world", "/quit")
        reg = CommandRegistry()
        pr = PluginRegistry()
        config = Config()

        # Register builtins
        builtin = BuiltinCommandsPlugin()
        pr.register(builtin, reg)

        # Register echo agent
        agent = IntegrationEchoAgent()
        pr.register(agent, reg)

        repl = REPL(
            session=session,
            tui=tui,
            command_registry=reg,
            plugin_registry=pr,
            config=config,
        )
        await repl.run()

        # User turn + assistant turn recorded
        history = session.get_history()
        assert len(history) == 2
        assert history[0].role == "user"
        assert history[0].content == "hello world"
        assert history[1].role == "assistant"
        assert "Echo: hello world" in history[1].content

        # Token stats accumulated
        assert session.stats.total_input == 10
        assert session.stats.total_output == 5


class TestBuiltinCommandsIntegration:
    """Test built-in commands in context."""

    @pytest.mark.asyncio
    async def test_help_command(self):
        session = Session()
        tui = _make_tui("/help")
        reg = CommandRegistry()
        pr = PluginRegistry()

        from agent_repl.builtin_commands import BuiltinCommandsPlugin

        builtin = BuiltinCommandsPlugin()
        pr.register(builtin, reg)

        repl = REPL(session=session, tui=tui, command_registry=reg,
                     plugin_registry=pr, config=Config())
        await repl.run()

        # show_info called for each command (7 builtins)
        assert tui.show_info.call_count == 7

    @pytest.mark.asyncio
    async def test_version_command(self):
        session = Session()
        tui = _make_tui("/version")
        reg = CommandRegistry()
        pr = PluginRegistry()

        from agent_repl.builtin_commands import BuiltinCommandsPlugin

        builtin = BuiltinCommandsPlugin()
        pr.register(builtin, reg)
        config = Config(app_name="testapp", app_version="1.2.3")

        repl = REPL(session=session, tui=tui, command_registry=reg,
                     plugin_registry=pr, config=config)
        await repl.run()

        output = tui.show_info.call_args[0][0]
        assert "testapp" in output
        assert "1.2.3" in output

    @pytest.mark.asyncio
    async def test_stats_command(self):
        session = Session()
        session.add_turn(ConversationTurn(
            role="assistant", content="hi",
            usage=__import__("agent_repl.types", fromlist=["TokenUsage"]).TokenUsage(
                input_tokens=100, output_tokens=200
            ),
        ))
        tui = _make_tui("/stats")
        reg = CommandRegistry()
        pr = PluginRegistry()

        from agent_repl.builtin_commands import BuiltinCommandsPlugin

        builtin = BuiltinCommandsPlugin()
        pr.register(builtin, reg)

        repl = REPL(session=session, tui=tui, command_registry=reg,
                     plugin_registry=pr, config=Config())
        await repl.run()

        assert tui.show_info.call_count == 2

    @pytest.mark.asyncio
    async def test_agent_command(self):
        session = Session()
        tui = _make_tui("/agent")
        reg = CommandRegistry()
        pr = PluginRegistry()
        agent = IntegrationEchoAgent()
        pr.register(agent, reg)

        from agent_repl.builtin_commands import BuiltinCommandsPlugin

        builtin = BuiltinCommandsPlugin()
        pr.register(builtin, reg)

        repl = REPL(session=session, tui=tui, command_registry=reg,
                     plugin_registry=pr, config=Config())
        await repl.run()

        output = tui.show_info.call_args[0][0]
        assert "Echo" in output
        assert "echo-test" in output


class TestUnknownCommandRecovery:
    """Test error recovery for unknown commands."""

    @pytest.mark.asyncio
    async def test_unknown_command_then_valid(self):
        session = Session()
        tui = _make_tui("/unknown", "/version")
        reg = CommandRegistry()
        pr = PluginRegistry()

        from agent_repl.builtin_commands import BuiltinCommandsPlugin

        builtin = BuiltinCommandsPlugin()
        pr.register(builtin, reg)

        repl = REPL(session=session, tui=tui, command_registry=reg,
                     plugin_registry=pr, config=Config())
        await repl.run()

        # First call: error for unknown, second: version info
        tui.show_error.assert_called_once()
        assert "Unknown command" in tui.show_error.call_args[0][0]
        tui.show_info.assert_called()


class TestFileContextIntegration:
    """Test @path file context injection."""

    @pytest.mark.asyncio
    async def test_file_mention_resolved(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as f:
            f.write("file content here")
            f.flush()
            tmp_path = f.name

        try:
            agent = IntegrationEchoAgent()
            session = Session()
            tui = _make_tui(f"check @{tmp_path}")
            reg = CommandRegistry()
            pr = PluginRegistry()
            pr.set_agent(agent)

            repl = REPL(session=session, tui=tui, command_registry=reg,
                         plugin_registry=pr, config=Config())
            await repl.run()

            # User turn should have file contexts
            history = session.get_history()
            user_turn = history[0]
            assert len(user_turn.file_contexts) > 0
            assert user_turn.file_contexts[0].path == tmp_path
        finally:
            os.unlink(tmp_path)


class TestCLIInvocation:
    """Test CLI command invocation flow."""

    @pytest.mark.asyncio
    async def test_cli_version(self):
        config = Config(app_name="testcli", app_version="3.0.0")
        app = App(config=config)
        with patch("agent_repl.app.load_config") as mock_lc:
            mock_lc.return_value = MagicMock(plugin_paths=[])
            result = await app.run_cli_command("version", [])
        assert result == 0

    @pytest.mark.asyncio
    async def test_cli_unknown_command(self):
        app = App()
        with patch("agent_repl.app.load_config") as mock_lc:
            mock_lc.return_value = MagicMock(plugin_paths=[])
            result = await app.run_cli_command("--nonexistent", [])
        assert result == 1


class TestErrorRecovery:
    """Test error recovery scenarios."""

    @pytest.mark.asyncio
    async def test_agent_exception_recovery(self):
        """Agent failure should not crash the REPL."""

        class FailingAgent:
            name = "Failing"
            description = "Always fails"
            default_model = "fail-1.0"

            def get_commands(self):
                return []

            async def on_load(self, ctx):
                pass

            async def on_unload(self):
                pass

            def get_status_hints(self):
                return []

            async def send_message(self, ctx):
                raise RuntimeError("agent exploded")

            async def compact_history(self, session):
                return ""

        session = Session()
        tui = _make_tui("hello", "world")
        reg = CommandRegistry()
        pr = PluginRegistry()
        pr.set_agent(FailingAgent())

        repl = REPL(session=session, tui=tui, command_registry=reg,
                     plugin_registry=pr, config=Config())
        await repl.run()

        # Both inputs processed (agent error didn't crash loop)
        assert tui.prompt_input.call_count == 3  # hello, world, EOFError
        assert tui.show_error.call_count == 2  # Two agent errors

    @pytest.mark.asyncio
    async def test_command_exception_recovery(self):
        """Command handler failure should not crash the REPL."""

        async def bad_handler(ctx: CommandContext) -> None:
            raise ValueError("bad command")

        session = Session()
        tui = _make_tui("/bad", "/bad")
        reg = CommandRegistry()
        reg.register(SlashCommand(name="bad", description="Bad", handler=bad_handler))
        pr = PluginRegistry()

        repl = REPL(session=session, tui=tui, command_registry=reg,
                     plugin_registry=pr, config=Config())
        await repl.run()

        assert tui.show_error.call_count == 2


# --- Audit Trail Integration Tests ---


class TestAuditFullSession:
    """Integration test: full session with audit enabled.

    Property 5: Start/Stop Bookends.
    Validates: Requirements 1.2, 4.1-4.6, 6.5, 6.6.
    """

    @pytest.mark.asyncio
    async def test_full_session_audit_file(self):
        """Banner → user input → agent echo → /version → /quit."""
        import re

        from agent_repl.audit_logger import AuditLogger
        from agent_repl.builtin_commands import BuiltinCommandsPlugin

        with tempfile.TemporaryDirectory() as tmpdir:
            audit = AuditLogger(directory=tmpdir)
            audit.start()

            session = Session()
            tui = _make_tui("hello world", "/version", "/quit")
            reg = CommandRegistry()
            pr = PluginRegistry()

            builtin = BuiltinCommandsPlugin()
            pr.register(builtin, reg)

            agent = IntegrationEchoAgent()
            pr.register(agent, reg)

            # Wire audit to TUI mock
            tui.show_info = MagicMock(
                side_effect=lambda text: audit.log("INFO", text)
            )
            tui.show_error = MagicMock(
                side_effect=lambda text: audit.log("ERROR", text)
            )
            tui.finalize_live_text = MagicMock()

            repl = REPL(
                session=session,
                tui=tui,
                command_registry=reg,
                plugin_registry=pr,
                config=Config(),
                audit_logger=audit,
            )
            await repl.run()
            audit.stop()

            # Read the audit file
            with open(audit.file_path) as f:
                content = f.read()
                lines = content.strip().split("\n")

            # Property 5: first entry is SYSTEM Audit started
            assert "[SYSTEM] Audit started" in lines[0]

            # Property 5: last entry is SYSTEM Audit stopped
            assert "[SYSTEM] Audit stopped" in lines[-1]

            # Verify user input was logged
            input_lines = [ln for ln in lines if "[INPUT]" in ln]
            assert len(input_lines) == 1
            assert "hello world" in input_lines[0]

            # Verify commands were logged
            cmd_lines = [ln for ln in lines if "[COMMAND]" in ln]
            assert len(cmd_lines) == 2  # /version and /quit
            assert "/version" in cmd_lines[0]
            assert "/quit" in cmd_lines[1]

            # Verify INFO entries present (from /version handler)
            info_lines = [ln for ln in lines if "[INFO]" in ln]
            assert len(info_lines) >= 1

            # Verify all entries match the format
            pattern = re.compile(
                r"^\[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}\] \[\w+\] .*"
            )
            for line in lines:
                assert pattern.match(line), f"Line didn't match: {line!r}"


class TestAuditToggleMidSession:
    """Integration test: /audit toggle mid-session.

    Validates: Requirements 2.2-2.5.
    """

    @pytest.mark.asyncio
    async def test_toggle_on_off(self):
        from agent_repl.audit_logger import AuditLogger
        from agent_repl.builtin_commands import BuiltinCommandsPlugin

        with tempfile.TemporaryDirectory() as tmpdir:
            audit = AuditLogger(directory=tmpdir)

            session = Session()
            # /audit (enable) → "hello" → /audit (disable)
            tui = _make_tui("/audit", "hello", "/audit")
            reg = CommandRegistry()
            pr = PluginRegistry()

            builtin = BuiltinCommandsPlugin()
            pr.register(builtin, reg)

            agent = IntegrationEchoAgent()
            pr.register(agent, reg)

            # Wire show_info to capture messages
            info_messages: list[str] = []
            tui.show_info = MagicMock(
                side_effect=lambda text: info_messages.append(text)
            )

            repl = REPL(
                session=session,
                tui=tui,
                command_registry=reg,
                plugin_registry=pr,
                config=Config(),
                audit_logger=audit,
            )
            await repl.run()

            # Verify file was created and then closed
            assert audit.active is False
            assert audit.file_path is not None
            assert os.path.exists(audit.file_path)

            # Verify the messages
            assert any("Audit started" in m for m in info_messages)
            assert any("Audit stopped" in m for m in info_messages)

            # Verify file contents: started, INPUT hello, stopped
            with open(audit.file_path) as f:
                content = f.read()
            assert "[SYSTEM] Audit started" in content
            assert "[INPUT] hello" in content
            assert "[SYSTEM] Audit stopped" in content


class TestAuditCrashSurvival:
    """Integration test: audit file survives crash.

    Property 3: Flush Per Entry.
    Validates: Requirement 6.4.
    """

    def test_entries_flushed_without_stop(self):
        from agent_repl.audit_logger import AuditLogger

        with tempfile.TemporaryDirectory() as tmpdir:
            audit = AuditLogger(directory=tmpdir)
            path = audit.start()
            audit.log("INPUT", "before crash")
            audit.log("INFO", "more data")

            # Simulate crash: DON'T call stop()
            # Read the file - entries should be flushed
            with open(path) as f:
                content = f.read()

            assert "[SYSTEM] Audit started" in content
            assert "[INPUT] before crash" in content
            assert "[INFO] more data" in content
            # No [SYSTEM] Audit stopped entry
            assert "[SYSTEM] Audit stopped" not in content

            # Clean up manually
            audit._file.close()
