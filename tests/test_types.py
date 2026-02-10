"""Unit tests for core data types."""

from agent_repl.constants import DEFAULT_CLAUDE_MODEL
from agent_repl.exceptions import (
    AgentError,
    ConfigError,
    FileContextError,
    PluginLoadError,
)
from agent_repl.types import (
    CommandContext,
    Config,
    ConversationTurn,
    FileContent,
    InputType,
    ParsedInput,
    SlashCommand,
    StreamEvent,
    StreamEventType,
    Theme,
    TokenStatistics,
    TokenUsage,
)

# --- Theme tests ---


class TestTheme:
    def test_defaults(self):
        theme = Theme()
        assert theme.prompt_color == "green"
        assert theme.cli_output_color == "dim"
        assert theme.agent_gutter_color == "blue"
        assert theme.agent_text_color == ""
        assert theme.tool_color == "cyan"
        assert theme.tool_error_color == "red"

    def test_all_fields_are_strings(self):
        theme = Theme()
        for field_name in ("prompt_color", "cli_output_color", "agent_gutter_color",
                           "agent_text_color", "tool_color", "tool_error_color"):
            value = getattr(theme, field_name)
            assert isinstance(value, str), f"{field_name} should be a string"

    def test_custom_values(self):
        theme = Theme(
            prompt_color="cyan",
            cli_output_color="yellow",
            agent_gutter_color="#5f87ff",
            agent_text_color="bright_white",
            tool_color="magenta",
            tool_error_color="bright_red",
        )
        assert theme.prompt_color == "cyan"
        assert theme.cli_output_color == "yellow"
        assert theme.agent_gutter_color == "#5f87ff"
        assert theme.agent_text_color == "bright_white"
        assert theme.tool_color == "magenta"
        assert theme.tool_error_color == "bright_red"

    def test_importable_from_package(self):
        from agent_repl import Theme as PublicTheme
        assert PublicTheme is Theme


# --- Config tests ---


class TestConfig:
    def test_required_fields(self):
        config = Config(
            app_name="test", app_version="1.0.0", default_model=DEFAULT_CLAUDE_MODEL
        )
        assert config.app_name == "test"
        assert config.app_version == "1.0.0"
        assert config.default_model == DEFAULT_CLAUDE_MODEL

    def test_defaults(self):
        config = Config(
            app_name="test", app_version="1.0.0", default_model=DEFAULT_CLAUDE_MODEL
        )
        assert config.agent_factory is None
        assert config.plugins == []

    def test_custom_agent_factory(self):
        def factory(c):
            return None

        config = Config(
            app_name="test",
            app_version="1.0.0",
            default_model=DEFAULT_CLAUDE_MODEL,
            agent_factory=factory,
        )
        assert config.agent_factory is factory

    def test_plugins_list(self):
        config = Config(
            app_name="test",
            app_version="1.0.0",
            default_model=DEFAULT_CLAUDE_MODEL,
            plugins=["plugin_a", "plugin_b"],
        )
        assert config.plugins == ["plugin_a", "plugin_b"]

    def test_plugins_default_not_shared(self):
        config1 = Config(app_name="a", app_version="1.0", default_model="m")
        config2 = Config(app_name="b", app_version="1.0", default_model="m")
        config1.plugins.append("x")
        assert config2.plugins == []

    def test_default_theme(self):
        config = Config(app_name="test", app_version="1.0", default_model="m")
        assert isinstance(config.theme, Theme)
        assert config.theme.prompt_color == "green"

    def test_custom_theme(self):
        custom = Theme(prompt_color="cyan", agent_gutter_color="red")
        config = Config(app_name="test", app_version="1.0", default_model="m", theme=custom)
        assert config.theme is custom
        assert config.theme.prompt_color == "cyan"
        assert config.theme.agent_gutter_color == "red"

    def test_theme_default_not_shared(self):
        c1 = Config(app_name="a", app_version="1.0", default_model="m")
        c2 = Config(app_name="b", app_version="1.0", default_model="m")
        c1.theme.prompt_color = "red"
        assert c2.theme.prompt_color == "green"

    def test_pinned_commands_defaults_to_none(self):
        config = Config(app_name="test", app_version="1.0", default_model="m")
        assert config.pinned_commands is None

    def test_pinned_commands_explicit_list(self):
        config = Config(
            app_name="test", app_version="1.0", default_model="m",
            pinned_commands=["help", "quit", "status"],
        )
        assert config.pinned_commands == ["help", "quit", "status"]

    def test_pinned_commands_empty_list(self):
        config = Config(
            app_name="test", app_version="1.0", default_model="m",
            pinned_commands=[],
        )
        assert config.pinned_commands == []


# --- TokenUsage tests ---


class TestTokenUsage:
    def test_defaults(self):
        usage = TokenUsage()
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0

    def test_custom_values(self):
        usage = TokenUsage(input_tokens=100, output_tokens=50)
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50


# --- TokenStatistics tests ---


class TestTokenStatistics:
    def test_defaults(self):
        stats = TokenStatistics()
        assert stats.total_input_tokens == 0
        assert stats.total_output_tokens == 0

    def test_accumulate_single(self):
        stats = TokenStatistics()
        stats.accumulate(TokenUsage(input_tokens=100, output_tokens=50))
        assert stats.total_input_tokens == 100
        assert stats.total_output_tokens == 50

    def test_accumulate_multiple(self):
        stats = TokenStatistics()
        stats.accumulate(TokenUsage(input_tokens=100, output_tokens=50))
        stats.accumulate(TokenUsage(input_tokens=200, output_tokens=75))
        assert stats.total_input_tokens == 300
        assert stats.total_output_tokens == 125

    def test_accumulate_zero(self):
        stats = TokenStatistics()
        stats.accumulate(TokenUsage(input_tokens=0, output_tokens=0))
        assert stats.total_input_tokens == 0
        assert stats.total_output_tokens == 0

    def test_accumulate_preserves_existing(self):
        stats = TokenStatistics(total_input_tokens=50, total_output_tokens=25)
        stats.accumulate(TokenUsage(input_tokens=10, output_tokens=5))
        assert stats.total_input_tokens == 60
        assert stats.total_output_tokens == 30


# --- SlashCommand tests ---


class TestSlashCommand:
    def test_construction(self):
        def handler(ctx):
            return None

        cmd = SlashCommand(
            name="help",
            description="Show help",
            help_text="Displays all available commands",
            handler=handler,
        )
        assert cmd.name == "help"
        assert cmd.description == "Show help"
        assert cmd.help_text == "Displays all available commands"
        assert cmd.handler is handler

    def test_pinned_defaults_to_false(self):
        cmd = SlashCommand(
            name="test", description="d", help_text="", handler=lambda ctx: None
        )
        assert cmd.pinned is False

    def test_pinned_explicit_true(self):
        cmd = SlashCommand(
            name="test", description="d", help_text="", handler=lambda ctx: None,
            pinned=True,
        )
        assert cmd.pinned is True

    def test_backward_compat_without_pinned(self):
        """Existing code that creates SlashCommand without pinned still works."""
        cmd = SlashCommand(
            name="x", description="y", help_text="z", handler=lambda ctx: None
        )
        assert cmd.pinned is False


# --- StreamEvent tests ---


class TestStreamEvent:
    def test_text_delta(self):
        event = StreamEvent(type=StreamEventType.TEXT_DELTA, content="hello")
        assert event.type == StreamEventType.TEXT_DELTA
        assert event.content == "hello"
        assert event.metadata == {}

    def test_usage_with_metadata(self):
        event = StreamEvent(
            type=StreamEventType.USAGE,
            metadata={"input_tokens": 100, "output_tokens": 50},
        )
        assert event.type == StreamEventType.USAGE
        assert event.content == ""
        assert event.metadata["input_tokens"] == 100

    def test_tool_result(self):
        event = StreamEvent(
            type=StreamEventType.TOOL_RESULT,
            content="result data",
            metadata={"tool_id": "t1", "is_error": False},
        )
        assert event.type == StreamEventType.TOOL_RESULT
        assert event.content == "result data"
        assert event.metadata["is_error"] is False

    def test_metadata_default_not_shared(self):
        e1 = StreamEvent(type=StreamEventType.TEXT_DELTA)
        e2 = StreamEvent(type=StreamEventType.TEXT_DELTA)
        e1.metadata["key"] = "val"
        assert "key" not in e2.metadata


# --- StreamEventType tests ---


class TestStreamEventType:
    def test_all_values(self):
        assert StreamEventType.TEXT_DELTA.value == "text_delta"
        assert StreamEventType.TOOL_USE_START.value == "tool_use_start"
        assert StreamEventType.TOOL_INPUT_DELTA.value == "tool_input_delta"
        assert StreamEventType.TOOL_RESULT.value == "tool_result"
        assert StreamEventType.USAGE.value == "usage"
        assert StreamEventType.ERROR.value == "error"


# --- FileContent tests ---


class TestFileContent:
    def test_construction(self):
        fc = FileContent(path="/tmp/test.py", content="print('hi')")
        assert fc.path == "/tmp/test.py"
        assert fc.content == "print('hi')"


# --- ConversationTurn tests ---


class TestConversationTurn:
    def test_user_turn(self):
        turn = ConversationTurn(role="user", content="Hello")
        assert turn.role == "user"
        assert turn.content == "Hello"
        assert turn.file_context == []
        assert turn.tool_uses == []
        assert turn.token_usage is None

    def test_assistant_turn_with_usage(self):
        usage = TokenUsage(input_tokens=100, output_tokens=50)
        turn = ConversationTurn(
            role="assistant",
            content="Hi there",
            token_usage=usage,
        )
        assert turn.role == "assistant"
        assert turn.token_usage is usage

    def test_turn_with_file_context(self):
        fc = FileContent(path="test.py", content="code")
        turn = ConversationTurn(role="user", content="Check this", file_context=[fc])
        assert len(turn.file_context) == 1
        assert turn.file_context[0].path == "test.py"

    def test_defaults_not_shared(self):
        t1 = ConversationTurn(role="user", content="a")
        t2 = ConversationTurn(role="user", content="b")
        t1.file_context.append(FileContent(path="x", content="y"))
        assert t2.file_context == []


# --- InputType tests ---


class TestInputType:
    def test_values(self):
        assert InputType.SLASH_COMMAND.value == "slash_command"
        assert InputType.FREE_TEXT.value == "free_text"


# --- ParsedInput tests ---


class TestParsedInput:
    def test_slash_command(self):
        parsed = ParsedInput(
            input_type=InputType.SLASH_COMMAND,
            raw="/help",
            command_name="help",
            command_args="",
        )
        assert parsed.input_type == InputType.SLASH_COMMAND
        assert parsed.command_name == "help"

    def test_free_text(self):
        parsed = ParsedInput(
            input_type=InputType.FREE_TEXT,
            raw="hello world",
            at_mentions=["@file.py"],
        )
        assert parsed.input_type == InputType.FREE_TEXT
        assert parsed.at_mentions == ["@file.py"]

    def test_defaults(self):
        parsed = ParsedInput(input_type=InputType.FREE_TEXT, raw="hi")
        assert parsed.command_name is None
        assert parsed.command_args is None
        assert parsed.at_mentions == []


# --- CommandContext tests ---


class TestCommandContext:
    def test_construction(self):
        ctx = CommandContext(args="some args", app_context=None)  # type: ignore[arg-type]
        assert ctx.args == "some args"


# --- Exception tests ---


class TestExceptions:
    def test_file_context_error(self):
        err = FileContextError("file not found: /tmp/x")
        assert str(err) == "file not found: /tmp/x"
        assert isinstance(err, Exception)

    def test_plugin_load_error(self):
        err = PluginLoadError("bad plugin")
        assert str(err) == "bad plugin"
        assert isinstance(err, Exception)

    def test_agent_error(self):
        err = AgentError("connection failed")
        assert str(err) == "connection failed"
        assert isinstance(err, Exception)

    def test_config_error(self):
        err = ConfigError("invalid config")
        assert str(err) == "invalid config"
        assert isinstance(err, Exception)
