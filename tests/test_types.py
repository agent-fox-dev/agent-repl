"""Tests for core data types, protocols, and enums."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from agent_repl.types import (
    AgentPlugin,
    CommandContext,
    Config,
    ConversationTurn,
    FileContext,
    MessageContext,
    Plugin,
    PluginContext,
    SlashCommand,
    SpawnConfig,
    StreamEvent,
    StreamEventType,
    Theme,
    TokenUsage,
    ToolUse,
)

# --- StreamEventType enum ---


class TestStreamEventType:
    def test_values(self):
        assert StreamEventType.TEXT_DELTA.value == "text_delta"
        assert StreamEventType.TOOL_USE_START.value == "tool_use_start"
        assert StreamEventType.TOOL_RESULT.value == "tool_result"
        assert StreamEventType.USAGE.value == "usage"
        assert StreamEventType.ERROR.value == "error"

    def test_all_members(self):
        assert len(StreamEventType) == 6

    def test_from_value(self):
        assert StreamEventType("text_delta") is StreamEventType.TEXT_DELTA


# --- Theme ---


class TestTheme:
    def test_defaults(self):
        t = Theme()
        assert t.prompt_color == "green"
        assert t.gutter_color == "blue"
        assert t.error_color == "red"
        assert t.info_color == "cyan"

    def test_custom(self):
        t = Theme(prompt_color="yellow", gutter_color="magenta")
        assert t.prompt_color == "yellow"
        assert t.gutter_color == "magenta"

    def test_frozen(self):
        t = Theme()
        with pytest.raises(AttributeError):
            t.prompt_color = "red"  # type: ignore[misc]


# --- StreamEvent ---


class TestStreamEvent:
    def test_creation(self):
        e = StreamEvent(type=StreamEventType.TEXT_DELTA, data={"text": "hi"})
        assert e.type is StreamEventType.TEXT_DELTA
        assert e.data == {"text": "hi"}

    def test_default_data(self):
        e = StreamEvent(type=StreamEventType.ERROR)
        assert e.data == {}

    def test_frozen(self):
        e = StreamEvent(type=StreamEventType.USAGE)
        with pytest.raises(AttributeError):
            e.type = StreamEventType.ERROR  # type: ignore[misc]


# --- TokenUsage ---


class TestTokenUsage:
    def test_defaults(self):
        u = TokenUsage()
        assert u.input_tokens == 0
        assert u.output_tokens == 0

    def test_custom(self):
        u = TokenUsage(input_tokens=100, output_tokens=50)
        assert u.input_tokens == 100
        assert u.output_tokens == 50

    def test_frozen(self):
        u = TokenUsage()
        with pytest.raises(AttributeError):
            u.input_tokens = 5  # type: ignore[misc]


# --- FileContext ---


class TestFileContext:
    def test_with_content(self):
        fc = FileContext(path="a.py", content="code")
        assert fc.path == "a.py"
        assert fc.content == "code"
        assert fc.error is None

    def test_with_error(self):
        fc = FileContext(path="b.py", error="File not found")
        assert fc.path == "b.py"
        assert fc.content is None
        assert fc.error == "File not found"

    def test_frozen(self):
        fc = FileContext(path="c.py")
        with pytest.raises(AttributeError):
            fc.path = "d.py"  # type: ignore[misc]


# --- ToolUse ---


class TestToolUse:
    def test_defaults(self):
        tu = ToolUse(name="bash")
        assert tu.name == "bash"
        assert tu.input == {}
        assert tu.result is None
        assert tu.is_error is False

    def test_with_result(self):
        tu = ToolUse(name="read", input={"path": "f"}, result="content", is_error=False)
        assert tu.result == "content"

    def test_with_error(self):
        tu = ToolUse(name="write", is_error=True, result="Permission denied")
        assert tu.is_error is True
        assert tu.result == "Permission denied"

    def test_frozen(self):
        tu = ToolUse(name="x")
        with pytest.raises(AttributeError):
            tu.name = "y"  # type: ignore[misc]


# --- ConversationTurn ---


class TestConversationTurn:
    def test_minimal(self):
        t = ConversationTurn(role="user", content="hello")
        assert t.role == "user"
        assert t.content == "hello"
        assert t.file_contexts == []
        assert t.tool_uses == []
        assert t.usage is None

    def test_full(self):
        fc = FileContext(path="a.py", content="code")
        tu = ToolUse(name="read")
        usage = TokenUsage(input_tokens=5, output_tokens=10)
        t = ConversationTurn(
            role="assistant",
            content="response",
            file_contexts=[fc],
            tool_uses=[tu],
            usage=usage,
        )
        assert len(t.file_contexts) == 1
        assert len(t.tool_uses) == 1
        assert t.usage is not None
        assert t.usage.input_tokens == 5

    def test_mutable(self):
        t = ConversationTurn(role="user", content="hi")
        t.content = "updated"
        assert t.content == "updated"


# --- SlashCommand ---


class TestSlashCommand:
    def test_creation(self):
        async def handler(ctx: CommandContext) -> None:
            pass

        cmd = SlashCommand(name="help", description="Show help", handler=handler)
        assert cmd.name == "help"
        assert cmd.description == "Show help"
        assert cmd.cli_exposed is False
        assert cmd.pinned is False

    def test_cli_exposed(self):
        async def handler(ctx: CommandContext) -> None:
            pass

        cmd = SlashCommand(
            name="compact", description="Compact", handler=handler, cli_exposed=True
        )
        assert cmd.cli_exposed is True

    def test_pinned(self):
        async def handler(ctx: CommandContext) -> None:
            pass

        cmd = SlashCommand(name="quit", description="Quit", handler=handler, pinned=True)
        assert cmd.pinned is True


# --- Config ---


class TestConfig:
    def test_defaults(self):
        c = Config()
        assert c.app_name == "agent_repl"
        assert c.app_version == "0.1.0"
        assert isinstance(c.theme, Theme)
        assert c.agent_factory is None
        assert c.plugins == []
        assert c.pinned_commands == ["help", "quit"]
        assert c.max_pinned_display == 6
        assert c.max_file_size == 512_000
        assert c.cli_commands == []
        assert c.audit is False

    def test_custom(self):
        c = Config(app_name="myapp", app_version="2.0.0", max_file_size=1_000_000)
        assert c.app_name == "myapp"
        assert c.max_file_size == 1_000_000

    def test_independent_default_lists(self):
        c1 = Config()
        c2 = Config()
        c1.plugins.append("some.plugin")
        assert c2.plugins == []


# --- SpawnConfig ---


class TestSpawnConfig:
    def test_minimal(self):
        sc = SpawnConfig(prompt="do something")
        assert sc.prompt == "do something"
        assert sc.pre_hook is None
        assert sc.post_hook is None

    def test_with_hooks(self):
        def pre():
            pass

        def post():
            pass

        sc = SpawnConfig(prompt="task", pre_hook=pre, post_hook=post)
        assert sc.pre_hook is pre
        assert sc.post_hook is post


# --- MessageContext ---


class TestMessageContext:
    def test_defaults(self):
        mc = MessageContext(message="hello")
        assert mc.message == "hello"
        assert mc.file_contexts == []
        assert mc.history == []

    def test_with_context(self):
        fc = FileContext(path="a.py", content="x")
        turn = ConversationTurn(role="user", content="hi")
        mc = MessageContext(message="msg", file_contexts=[fc], history=[turn])
        assert len(mc.file_contexts) == 1
        assert len(mc.history) == 1


# --- CommandContext ---


class TestCommandContext:
    def test_defaults(self):
        cc = CommandContext(args="")
        assert cc.args == ""
        assert cc.argv == []
        assert cc.session is None
        assert cc.tui is None
        assert isinstance(cc.config, Config)
        assert cc.registry is None
        assert cc.plugin_registry is None
        assert cc.audit_logger is None

    def test_with_argv(self):
        cc = CommandContext(args="foo bar", argv=["foo", "bar"])
        assert cc.args == "foo bar"
        assert cc.argv == ["foo", "bar"]


# --- PluginContext ---


class TestPluginContext:
    def test_defaults(self):
        pc = PluginContext()
        assert isinstance(pc.config, Config)
        assert pc.session is None
        assert pc.tui is None
        assert pc.registry is None


# --- Plugin protocol ---


class TestPluginProtocol:
    def test_runtime_checkable(self):
        class MyPlugin:
            name = "test"
            description = "A test plugin"

            def get_commands(self) -> list[SlashCommand]:
                return []

            async def on_load(self, context: PluginContext) -> None:
                pass

            async def on_unload(self) -> None:
                pass

            def get_status_hints(self) -> list[str]:
                return []

        p = MyPlugin()
        assert isinstance(p, Plugin)

    def test_non_conforming_not_plugin(self):
        class NotAPlugin:
            pass

        assert not isinstance(NotAPlugin(), Plugin)


# --- AgentPlugin protocol ---


class TestAgentPluginProtocol:
    def test_runtime_checkable(self):
        class MyAgent:
            name = "agent"
            description = "An agent"
            default_model = "test-model"

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
                yield StreamEvent(type=StreamEventType.TEXT_DELTA, data={"text": "hi"})

            async def compact_history(self, session: Any) -> str:
                return "summary"

        a = MyAgent()
        assert isinstance(a, AgentPlugin)
        assert isinstance(a, Plugin)

    def test_plugin_without_agent_methods(self):
        class JustAPlugin:
            name = "basic"
            description = "Basic"

            def get_commands(self) -> list[SlashCommand]:
                return []

            async def on_load(self, context: PluginContext) -> None:
                pass

            async def on_unload(self) -> None:
                pass

            def get_status_hints(self) -> list[str]:
                return []

        p = JustAPlugin()
        assert isinstance(p, Plugin)
        assert not isinstance(p, AgentPlugin)


# --- Public API imports ---


class TestPublicAPI:
    def test_top_level_imports(self):
        from agent_repl import (
            AgentPlugin,
            Config,
            Plugin,
            SlashCommand,
            StreamEvent,
            StreamEventType,
            Theme,
        )

        assert Config is not None
        assert Theme is not None
        assert Plugin is not None
        assert AgentPlugin is not None
        assert SlashCommand is not None
        assert StreamEvent is not None
        assert StreamEventType is not None
