"""Tests for agents/claude_agent module.

Covers Requirements 11.1-11.7, 11.E1-11.E3.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from agent_repl.agents.claude_agent import (
    ClaudeAgentPlugin,
    _build_prompt,
    _check_auth,
    create_plugin,
)
from agent_repl.exceptions import AgentError
from agent_repl.session import Session
from agent_repl.types import (
    CommandContext,
    Config,
    ConversationTurn,
    FileContext,
    MessageContext,
    PluginContext,
    StreamEventType,
)


def _make_plugin_ctx() -> PluginContext:
    return PluginContext(
        config=Config(),
        session=Session(),
        tui=MagicMock(),
        registry=MagicMock(),
    )


def _make_cmd_ctx(session: Session | None = None) -> CommandContext:
    session = session or Session()
    return CommandContext(
        args="",
        session=session,
        tui=MagicMock(),
        config=Config(),
        registry=MagicMock(),
        plugin_registry=MagicMock(),
    )


class TestPluginProtocol:
    """Requirement 11.1: Plugin protocol compliance."""

    def test_has_name(self):
        plugin = ClaudeAgentPlugin()
        assert plugin.name == "Claude"

    def test_has_description(self):
        plugin = ClaudeAgentPlugin()
        assert plugin.description == "Anthropic Claude agent via claude-agent-sdk"

    def test_has_default_model(self):
        plugin = ClaudeAgentPlugin()
        assert plugin.default_model is not None
        assert isinstance(plugin.default_model, str)

    def test_custom_model(self):
        plugin = ClaudeAgentPlugin(model="claude-opus-4-20250514")
        assert plugin.default_model == "claude-opus-4-20250514"

    def test_get_commands(self):
        plugin = ClaudeAgentPlugin()
        commands = plugin.get_commands()
        assert len(commands) == 2
        names = {cmd.name for cmd in commands}
        assert names == {"clear", "compact"}


class TestAuthentication:
    """Requirements 11.5, 11.6: Authentication detection."""

    def test_api_key_auth(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=False):
            # Should not raise
            _check_auth()

    def test_vertex_auth(self):
        with patch.dict(
            os.environ,
            {"CLAUDE_CODE_USE_VERTEX": "1"},
            clear=False,
        ):
            _check_auth()

    def test_bedrock_auth(self):
        with patch.dict(
            os.environ,
            {"CLAUDE_CODE_USE_BEDROCK": "1"},
            clear=False,
        ):
            _check_auth()

    def test_no_auth_raises(self):
        env = {
            "ANTHROPIC_API_KEY": "",
            "CLAUDE_CODE_USE_VERTEX": "",
            "CLAUDE_CODE_USE_BEDROCK": "",
        }
        with patch.dict(os.environ, env, clear=False):
            with pytest.raises(AgentError) as exc_info:
                _check_auth()
            msg = str(exc_info.value)
            assert "ANTHROPIC_API_KEY" in msg
            assert "CLAUDE_CODE_USE_VERTEX" in msg
            assert "CLAUDE_CODE_USE_BEDROCK" in msg

    @pytest.mark.asyncio
    async def test_on_load_checks_auth(self):
        plugin = ClaudeAgentPlugin()
        env = {
            "ANTHROPIC_API_KEY": "",
            "CLAUDE_CODE_USE_VERTEX": "",
            "CLAUDE_CODE_USE_BEDROCK": "",
        }
        with patch.dict(os.environ, env, clear=False):
            with pytest.raises(AgentError):
                await plugin.on_load(_make_plugin_ctx())


class TestOnLoad:
    """Requirement 11.E1: SDK availability check."""

    @pytest.mark.asyncio
    async def test_on_load_success(self):
        plugin = ClaudeAgentPlugin()
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=False):
            await plugin.on_load(_make_plugin_ctx())
        # Should not raise

    @pytest.mark.asyncio
    async def test_on_load_no_sdk(self):
        plugin = ClaudeAgentPlugin()
        with (
            patch("agent_repl.agents.claude_agent._SDK_AVAILABLE", False),
            pytest.raises(AgentError, match="claude-agent-sdk is not installed"),
        ):
            await plugin.on_load(_make_plugin_ctx())


class TestOnUnload:
    """Test cleanup on unload."""

    @pytest.mark.asyncio
    async def test_on_unload_resets_state(self):
        plugin = ClaudeAgentPlugin()
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=False):
            await plugin.on_load(_make_plugin_ctx())
        await plugin.on_unload()
        assert plugin._session_started is False
        assert plugin._plugin_ctx is None


class TestBuildPrompt:
    """Requirement 11.2: Prompt building."""

    def test_message_only(self):
        ctx = MessageContext(message="Hello")
        assert _build_prompt(ctx) == "Hello"

    def test_with_file_context(self):
        ctx = MessageContext(
            message="Check this file",
            file_contexts=[FileContext(path="test.py", content="print('hi')")],
        )
        result = _build_prompt(ctx)
        assert "<file path=\"test.py\">" in result
        assert "print('hi')" in result
        assert "Check this file" in result

    def test_with_file_error(self):
        ctx = MessageContext(
            message="Check this",
            file_contexts=[FileContext(path="missing.py", error="Not found")],
        )
        result = _build_prompt(ctx)
        assert "[File missing.py: Not found]" in result

    def test_multiple_files(self):
        ctx = MessageContext(
            message="Review",
            file_contexts=[
                FileContext(path="a.py", content="# a"),
                FileContext(path="b.py", content="# b"),
            ],
        )
        result = _build_prompt(ctx)
        assert "<file path=\"a.py\">" in result
        assert "<file path=\"b.py\">" in result


class TestSendMessage:
    """Requirement 11.2: Stream translation."""

    @pytest.mark.asyncio
    async def test_text_delta(self):
        """TextBlock → TEXT_DELTA."""
        import claude_agent_sdk as real_sdk

        assistant_msg = real_sdk.AssistantMessage(
            content=[real_sdk.TextBlock(text="Hello world")],
            model="claude-sonnet-4-20250514",
        )

        async def mock_query(**kwargs):
            yield assistant_msg

        plugin = ClaudeAgentPlugin()
        with patch("agent_repl.agents.claude_agent.sdk") as mock_sdk:
            mock_sdk.query = mock_query
            mock_sdk.AssistantMessage = real_sdk.AssistantMessage
            mock_sdk.TextBlock = real_sdk.TextBlock
            mock_sdk.ToolUseBlock = real_sdk.ToolUseBlock
            mock_sdk.ToolResultBlock = real_sdk.ToolResultBlock
            mock_sdk.UserMessage = real_sdk.UserMessage
            mock_sdk.ResultMessage = real_sdk.ResultMessage
            mock_sdk.ClaudeAgentOptions = real_sdk.ClaudeAgentOptions
            mock_sdk.ClaudeSDKError = real_sdk.ClaudeSDKError

            ctx = MessageContext(message="hi")
            stream = await plugin.send_message(ctx)
            events = [e async for e in stream]

        assert len(events) == 1
        assert events[0].type == StreamEventType.TEXT_DELTA
        assert events[0].data["text"] == "Hello world"

    @pytest.mark.asyncio
    async def test_tool_use_start(self):
        """ToolUseBlock → TOOL_USE_START."""
        import claude_agent_sdk as real_sdk

        assistant_msg = real_sdk.AssistantMessage(
            content=[
                real_sdk.ToolUseBlock(id="tu_1", name="read_file", input={"path": "x"})
            ],
            model="claude-sonnet-4-20250514",
        )

        async def mock_query(**kwargs):
            yield assistant_msg

        plugin = ClaudeAgentPlugin()
        with patch("agent_repl.agents.claude_agent.sdk") as mock_sdk:
            mock_sdk.query = mock_query
            mock_sdk.AssistantMessage = real_sdk.AssistantMessage
            mock_sdk.TextBlock = real_sdk.TextBlock
            mock_sdk.ToolUseBlock = real_sdk.ToolUseBlock
            mock_sdk.ToolResultBlock = real_sdk.ToolResultBlock
            mock_sdk.UserMessage = real_sdk.UserMessage
            mock_sdk.ResultMessage = real_sdk.ResultMessage
            mock_sdk.ClaudeAgentOptions = real_sdk.ClaudeAgentOptions
            mock_sdk.ClaudeSDKError = real_sdk.ClaudeSDKError

            ctx = MessageContext(message="read a file")
            stream = await plugin.send_message(ctx)
            events = [e async for e in stream]

        assert len(events) == 1
        assert events[0].type == StreamEventType.TOOL_USE_START
        assert events[0].data["name"] == "read_file"
        assert events[0].data["id"] == "tu_1"

    @pytest.mark.asyncio
    async def test_tool_result(self):
        """ToolResultBlock in UserMessage → TOOL_RESULT."""
        import claude_agent_sdk as real_sdk

        assistant_msg = real_sdk.AssistantMessage(
            content=[
                real_sdk.ToolUseBlock(id="tu_1", name="read_file", input={})
            ],
            model="claude-sonnet-4-20250514",
        )
        user_msg = real_sdk.UserMessage(
            content=[
                real_sdk.ToolResultBlock(
                    tool_use_id="tu_1", content="file contents", is_error=False
                )
            ],
        )

        async def mock_query(**kwargs):
            yield assistant_msg
            yield user_msg

        plugin = ClaudeAgentPlugin()
        with patch("agent_repl.agents.claude_agent.sdk") as mock_sdk:
            mock_sdk.query = mock_query
            mock_sdk.AssistantMessage = real_sdk.AssistantMessage
            mock_sdk.TextBlock = real_sdk.TextBlock
            mock_sdk.ToolUseBlock = real_sdk.ToolUseBlock
            mock_sdk.ToolResultBlock = real_sdk.ToolResultBlock
            mock_sdk.UserMessage = real_sdk.UserMessage
            mock_sdk.ResultMessage = real_sdk.ResultMessage
            mock_sdk.ClaudeAgentOptions = real_sdk.ClaudeAgentOptions
            mock_sdk.ClaudeSDKError = real_sdk.ClaudeSDKError

            ctx = MessageContext(message="read a file")
            stream = await plugin.send_message(ctx)
            events = [e async for e in stream]

        # TOOL_USE_START + TOOL_RESULT
        assert len(events) == 2
        assert events[1].type == StreamEventType.TOOL_RESULT
        assert events[1].data["name"] == "read_file"
        assert events[1].data["result"] == "file contents"
        assert events[1].data["is_error"] is False

    @pytest.mark.asyncio
    async def test_usage(self):
        """ResultMessage with usage → USAGE."""
        import claude_agent_sdk as real_sdk

        result_msg = real_sdk.ResultMessage(
            subtype="result",
            duration_ms=100,
            duration_api_ms=80,
            is_error=False,
            num_turns=1,
            session_id="sess_1",
            total_cost_usd=0.01,
            usage={"input_tokens": 100, "output_tokens": 200},
            result="done",
        )

        async def mock_query(**kwargs):
            yield result_msg

        plugin = ClaudeAgentPlugin()
        with patch("agent_repl.agents.claude_agent.sdk") as mock_sdk:
            mock_sdk.query = mock_query
            mock_sdk.AssistantMessage = real_sdk.AssistantMessage
            mock_sdk.TextBlock = real_sdk.TextBlock
            mock_sdk.ToolUseBlock = real_sdk.ToolUseBlock
            mock_sdk.ToolResultBlock = real_sdk.ToolResultBlock
            mock_sdk.UserMessage = real_sdk.UserMessage
            mock_sdk.ResultMessage = real_sdk.ResultMessage
            mock_sdk.ClaudeAgentOptions = real_sdk.ClaudeAgentOptions
            mock_sdk.ClaudeSDKError = real_sdk.ClaudeSDKError

            ctx = MessageContext(message="hi")
            stream = await plugin.send_message(ctx)
            events = [e async for e in stream]

        assert len(events) == 1
        assert events[0].type == StreamEventType.USAGE
        assert events[0].data["input_tokens"] == 100
        assert events[0].data["output_tokens"] == 200

    @pytest.mark.asyncio
    async def test_error_auth_fatal(self):
        """AssistantMessage with auth error → ERROR (fatal)."""
        import claude_agent_sdk as real_sdk

        assistant_msg = real_sdk.AssistantMessage(
            content=[],
            model="claude-sonnet-4-20250514",
            error="authentication_failed",
        )

        async def mock_query(**kwargs):
            yield assistant_msg

        plugin = ClaudeAgentPlugin()
        with patch("agent_repl.agents.claude_agent.sdk") as mock_sdk:
            mock_sdk.query = mock_query
            mock_sdk.AssistantMessage = real_sdk.AssistantMessage
            mock_sdk.TextBlock = real_sdk.TextBlock
            mock_sdk.ToolUseBlock = real_sdk.ToolUseBlock
            mock_sdk.ToolResultBlock = real_sdk.ToolResultBlock
            mock_sdk.UserMessage = real_sdk.UserMessage
            mock_sdk.ResultMessage = real_sdk.ResultMessage
            mock_sdk.ClaudeAgentOptions = real_sdk.ClaudeAgentOptions
            mock_sdk.ClaudeSDKError = real_sdk.ClaudeSDKError

            ctx = MessageContext(message="hi")
            stream = await plugin.send_message(ctx)
            events = [e async for e in stream]

        assert len(events) == 1
        assert events[0].type == StreamEventType.ERROR
        assert events[0].data["message"] == "authentication_failed"
        assert events[0].data["fatal"] is True

    @pytest.mark.asyncio
    async def test_error_rate_limit_non_fatal(self):
        """AssistantMessage with rate_limit error → ERROR (non-fatal)."""
        import claude_agent_sdk as real_sdk

        assistant_msg = real_sdk.AssistantMessage(
            content=[],
            model="claude-sonnet-4-20250514",
            error="rate_limit",
        )

        async def mock_query(**kwargs):
            yield assistant_msg

        plugin = ClaudeAgentPlugin()
        with patch("agent_repl.agents.claude_agent.sdk") as mock_sdk:
            mock_sdk.query = mock_query
            mock_sdk.AssistantMessage = real_sdk.AssistantMessage
            mock_sdk.TextBlock = real_sdk.TextBlock
            mock_sdk.ToolUseBlock = real_sdk.ToolUseBlock
            mock_sdk.ToolResultBlock = real_sdk.ToolResultBlock
            mock_sdk.UserMessage = real_sdk.UserMessage
            mock_sdk.ResultMessage = real_sdk.ResultMessage
            mock_sdk.ClaudeAgentOptions = real_sdk.ClaudeAgentOptions
            mock_sdk.ClaudeSDKError = real_sdk.ClaudeSDKError

            ctx = MessageContext(message="hi")
            stream = await plugin.send_message(ctx)
            events = [e async for e in stream]

        assert events[0].type == StreamEventType.ERROR
        assert events[0].data["fatal"] is False

    @pytest.mark.asyncio
    async def test_sdk_error_yields_fatal(self):
        """SDK exception during streaming → ERROR (fatal)."""
        import claude_agent_sdk as real_sdk

        async def mock_query(**kwargs):
            raise real_sdk.ClaudeSDKError("connection lost")
            yield  # noqa: F401 - makes this an async generator

        plugin = ClaudeAgentPlugin()
        with patch("agent_repl.agents.claude_agent.sdk") as mock_sdk:
            mock_sdk.query = mock_query
            mock_sdk.AssistantMessage = real_sdk.AssistantMessage
            mock_sdk.TextBlock = real_sdk.TextBlock
            mock_sdk.ToolUseBlock = real_sdk.ToolUseBlock
            mock_sdk.ToolResultBlock = real_sdk.ToolResultBlock
            mock_sdk.UserMessage = real_sdk.UserMessage
            mock_sdk.ResultMessage = real_sdk.ResultMessage
            mock_sdk.ClaudeAgentOptions = real_sdk.ClaudeAgentOptions
            mock_sdk.ClaudeSDKError = real_sdk.ClaudeSDKError

            ctx = MessageContext(message="hi")
            stream = await plugin.send_message(ctx)
            events = [e async for e in stream]

        assert len(events) == 1
        assert events[0].type == StreamEventType.ERROR
        assert "connection lost" in events[0].data["message"]
        assert events[0].data["fatal"] is True


class TestClearCommand:
    """Requirement 11.3: /clear clears session."""

    @pytest.mark.asyncio
    async def test_clear_clears_session(self):
        from agent_repl.agents.claude_agent import _handle_clear

        session = Session()
        session.add_turn(ConversationTurn(role="user", content="hi"))
        session.add_turn(ConversationTurn(role="assistant", content="hello"))

        ctx = _make_cmd_ctx(session)
        await _handle_clear(ctx)

        assert len(session.get_history()) == 0
        ctx.tui.show_info.assert_called_once()
        assert "cleared" in ctx.tui.show_info.call_args[0][0].lower()


class TestCompactCommand:
    """Requirement 11.4: /compact summarizes history."""

    @pytest.mark.asyncio
    async def test_compact_replaces_history(self):
        from agent_repl.agents.claude_agent import _handle_compact

        session = Session()
        session.add_turn(ConversationTurn(role="user", content="hello"))
        session.add_turn(ConversationTurn(role="assistant", content="world"))

        plugin = ClaudeAgentPlugin()
        ctx = _make_cmd_ctx(session)
        ctx.plugin_registry.active_agent = plugin

        # Mock compact_history
        async def mock_compact(sess):
            return "Summary: user said hello, agent said world"

        with patch.object(plugin, "compact_history", side_effect=mock_compact):
            await _handle_compact(ctx)

        history = session.get_history()
        assert len(history) == 1
        assert history[0].role == "system"
        assert "Summary" in history[0].content

    @pytest.mark.asyncio
    async def test_compact_no_agent(self):
        from agent_repl.agents.claude_agent import _handle_compact

        ctx = _make_cmd_ctx()
        ctx.plugin_registry.active_agent = None
        await _handle_compact(ctx)
        ctx.tui.show_info.assert_called_once()
        assert "No agent" in ctx.tui.show_info.call_args[0][0]

    @pytest.mark.asyncio
    async def test_compact_error_handled(self):
        from agent_repl.agents.claude_agent import _handle_compact

        plugin = ClaudeAgentPlugin()
        ctx = _make_cmd_ctx()
        ctx.plugin_registry.active_agent = plugin

        with patch.object(
            plugin, "compact_history", side_effect=RuntimeError("fail")
        ):
            await _handle_compact(ctx)

        ctx.tui.show_error.assert_called_once()
        assert "Compact failed" in ctx.tui.show_error.call_args[0][0]


class TestStatusHints:
    """Requirement 11.7: Status hints expose model."""

    def test_status_hints_include_model(self):
        plugin = ClaudeAgentPlugin(model="claude-opus-4-20250514")
        hints = plugin.get_status_hints()
        assert len(hints) == 1
        assert "claude-opus-4-20250514" in hints[0]


class TestModelDetection:
    """Requirement 11.7: Model detection from response."""

    @pytest.mark.asyncio
    async def test_model_updated_from_response(self):
        import claude_agent_sdk as real_sdk

        assistant_msg = real_sdk.AssistantMessage(
            content=[real_sdk.TextBlock(text="hi")],
            model="claude-opus-4-20250514",
        )

        async def mock_query(**kwargs):
            yield assistant_msg

        plugin = ClaudeAgentPlugin()
        with patch("agent_repl.agents.claude_agent.sdk") as mock_sdk:
            mock_sdk.query = mock_query
            mock_sdk.AssistantMessage = real_sdk.AssistantMessage
            mock_sdk.TextBlock = real_sdk.TextBlock
            mock_sdk.ToolUseBlock = real_sdk.ToolUseBlock
            mock_sdk.ToolResultBlock = real_sdk.ToolResultBlock
            mock_sdk.UserMessage = real_sdk.UserMessage
            mock_sdk.ResultMessage = real_sdk.ResultMessage
            mock_sdk.ClaudeAgentOptions = real_sdk.ClaudeAgentOptions
            mock_sdk.ClaudeSDKError = real_sdk.ClaudeSDKError

            ctx = MessageContext(message="hi")
            stream = await plugin.send_message(ctx)
            _ = [e async for e in stream]

        assert plugin.default_model == "claude-opus-4-20250514"


class TestContinueConversation:
    """Test that continue_conversation is set after first message."""

    @pytest.mark.asyncio
    async def test_first_message_not_continued(self):
        import claude_agent_sdk as real_sdk

        captured_options = []

        async def mock_query(**kwargs):
            captured_options.append(kwargs.get("options"))
            yield real_sdk.ResultMessage(
                subtype="result",
                duration_ms=0,
                duration_api_ms=0,
                is_error=False,
                num_turns=0,
                session_id="s1",
            )

        plugin = ClaudeAgentPlugin()
        assert plugin._session_started is False

        with patch("agent_repl.agents.claude_agent.sdk") as mock_sdk:
            mock_sdk.query = mock_query
            mock_sdk.AssistantMessage = real_sdk.AssistantMessage
            mock_sdk.TextBlock = real_sdk.TextBlock
            mock_sdk.ToolUseBlock = real_sdk.ToolUseBlock
            mock_sdk.ToolResultBlock = real_sdk.ToolResultBlock
            mock_sdk.UserMessage = real_sdk.UserMessage
            mock_sdk.ResultMessage = real_sdk.ResultMessage
            mock_sdk.ClaudeAgentOptions = real_sdk.ClaudeAgentOptions
            mock_sdk.ClaudeSDKError = real_sdk.ClaudeSDKError

            ctx = MessageContext(message="hi")
            stream = await plugin.send_message(ctx)
            _ = [e async for e in stream]

        assert captured_options[0].continue_conversation is False
        assert plugin._session_started is True


class TestFactory:
    """Test create_plugin factory."""

    def test_create_plugin_default(self):
        plugin = create_plugin()
        assert isinstance(plugin, ClaudeAgentPlugin)

    def test_create_plugin_with_model(self):
        plugin = create_plugin(model="claude-opus-4-20250514")
        assert plugin.default_model == "claude-opus-4-20250514"
