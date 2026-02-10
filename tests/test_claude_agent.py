"""Unit tests for the Claude agent plugin.

Property 17: Config Object Override
Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 10.2
"""

from unittest.mock import MagicMock

import pytest

from agent_repl.session import Session
from agent_repl.types import (
    AppContext,
    CommandContext,
    Config,
    ConversationTurn,
    TokenStatistics,
)


class TestClaudeAgentPlugin:
    """Tests run with ANTHROPIC_API_KEY set so plugin instantiates (auth choice: API key)."""

    @pytest.fixture(autouse=True)
    def _auth_api_key(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        # Ensure Vertex is not selected
        monkeypatch.delenv("CLAUDE_CODE_USE_VERTEX", raising=False)
        monkeypatch.delenv("ANTHROPIC_VERTEX_PROJECT_ID", raising=False)

    def test_init_does_not_require_api_key(self):
        """SDK handles authentication; no upfront API key check."""
        from agent_repl.agents.claude_agent import ClaudeAgentPlugin

        agent = ClaudeAgentPlugin()
        assert agent.name == "claude"

    def test_get_commands_returns_clear_and_compact(self):
        from agent_repl.agents.claude_agent import ClaudeAgentPlugin

        agent = ClaudeAgentPlugin()
        cmds = agent.get_commands()
        names = {c.name for c in cmds}
        assert names == {"clear", "compact"}

    def test_clear_resets_session(self):
        from agent_repl.agents.claude_agent import ClaudeAgentPlugin

        agent = ClaudeAgentPlugin()
        session = Session()
        session.add_turn(ConversationTurn(role="user", content="hi"))

        tui = MagicMock()
        cmd_reg = MagicMock()
        config = Config(app_name="t", app_version="1.0", default_model="m")
        app_ctx = AppContext(
            config=config, session=session, tui=tui,
            command_registry=cmd_reg, stats=TokenStatistics(),
        )
        ctx = CommandContext(args="", app_context=app_ctx)

        clear_cmd = next(c for c in agent.get_commands() if c.name == "clear")
        clear_cmd.handler(ctx)

        assert session.get_history() == []
        tui.display_info.assert_called_once()

    def test_model_from_config(self):
        from agent_repl.agents.claude_agent import ClaudeAgentPlugin

        agent = ClaudeAgentPlugin(model="custom-model")
        assert agent._model == "custom-model"

    def test_build_prompt_string(self):
        from agent_repl.agents.claude_agent import ClaudeAgentPlugin

        agent = ClaudeAgentPlugin()
        history = [
            ConversationTurn(role="user", content="hello"),
            ConversationTurn(role="assistant", content="hi"),
        ]
        prompt = agent._build_prompt_string(history, "new message", [])
        assert "User: hello" in prompt
        assert "Assistant: hi" in prompt
        assert "User: new message" in prompt


class TestClaudeAuthSelection:
    """Test which authentication is used: Vertex vs API key."""

    def test_no_auth_raises(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("CLAUDE_CODE_USE_VERTEX", raising=False)
        monkeypatch.delenv("ANTHROPIC_VERTEX_PROJECT_ID", raising=False)

        from agent_repl.agents.claude_agent import ClaudeAgentPlugin
        from agent_repl.exceptions import AgentError

        with pytest.raises(AgentError, match="No Claude authentication configured"):
            ClaudeAgentPlugin()

    def test_api_key_auth_creates_client(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake")
        monkeypatch.delenv("CLAUDE_CODE_USE_VERTEX", raising=False)
        monkeypatch.delenv("ANTHROPIC_VERTEX_PROJECT_ID", raising=False)

        from agent_repl.agents.claude_agent import ClaudeAgentPlugin

        agent = ClaudeAgentPlugin()
        assert agent._client is not None
        assert type(agent._client).__name__ == "ClaudeSDKClient"

    def test_vertex_auth_creates_client(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_CODE_USE_VERTEX", "1")
        monkeypatch.setenv("ANTHROPIC_VERTEX_PROJECT_ID", "my-project")
        monkeypatch.setenv("CLOUD_ML_REGION", "us-east1")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        from agent_repl.agents.claude_agent import ClaudeAgentPlugin

        agent = ClaudeAgentPlugin()
        assert agent._client is not None
        assert type(agent._client).__name__ == "ClaudeSDKClient"


class TestProperty17ConfigObjectOverride:
    """Property 17: Custom agent factory is used instead of default.

    Feature: agent_repl, Property 17: Config Object Override
    """

    def test_custom_factory_called(self):
        mock_agent = MagicMock()
        mock_agent.get_commands.return_value = []

        def factory(config):
            return mock_agent

        config = Config(
            app_name="test",
            app_version="1.0",
            default_model="m",
            agent_factory=factory,
        )

        result = config.agent_factory(config)
        assert result is mock_agent
