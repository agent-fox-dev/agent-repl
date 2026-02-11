import pytest

from agent_repl.types import (
    CommandContext,
    Config,
    ConversationTurn,
    FileContext,
    MessageContext,
    PluginContext,
    StreamEvent,
    StreamEventType,
    Theme,
    TokenUsage,
    ToolUse,
)


@pytest.fixture
def default_config():
    return Config()


@pytest.fixture
def default_theme():
    return Theme()


@pytest.fixture
def sample_turn():
    return ConversationTurn(
        role="assistant",
        content="Hello, how can I help?",
        usage=TokenUsage(input_tokens=10, output_tokens=20),
    )


@pytest.fixture
def sample_file_context():
    return FileContext(path="test.py", content="print('hello')")


@pytest.fixture
def sample_tool_use():
    return ToolUse(name="read_file", input={"path": "test.py"}, result="contents", is_error=False)


@pytest.fixture
def sample_stream_event():
    return StreamEvent(type=StreamEventType.TEXT_DELTA, data={"text": "Hello"})


@pytest.fixture
def sample_message_context():
    return MessageContext(message="Hello agent")


@pytest.fixture
def sample_command_context():
    return CommandContext(args="")


@pytest.fixture
def sample_plugin_context():
    return PluginContext()
