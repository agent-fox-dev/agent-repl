"""Unit and property tests for the input parser module.

Property 1: Input Routing
Validates: Requirements 1.1, 4.1
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from agent_repl.input_parser import parse_input
from agent_repl.types import InputType

# --- Unit tests ---


class TestParseInputSlashCommands:
    def test_simple_command(self):
        result = parse_input("/help")
        assert result.input_type == InputType.SLASH_COMMAND
        assert result.command_name == "help"
        assert result.command_args == ""

    def test_command_with_args(self):
        result = parse_input("/model claude-sonnet")
        assert result.input_type == InputType.SLASH_COMMAND
        assert result.command_name == "model"
        assert result.command_args == "claude-sonnet"

    def test_command_with_multiple_args(self):
        result = parse_input("/search foo bar baz")
        assert result.input_type == InputType.SLASH_COMMAND
        assert result.command_name == "search"
        assert result.command_args == "foo bar baz"

    def test_command_preserves_raw(self):
        raw = "  /help  "
        result = parse_input(raw)
        assert result.raw == raw

    def test_command_with_leading_whitespace(self):
        result = parse_input("  /quit")
        assert result.input_type == InputType.SLASH_COMMAND
        assert result.command_name == "quit"

    def test_command_with_trailing_whitespace(self):
        result = parse_input("/version  ")
        assert result.input_type == InputType.SLASH_COMMAND
        assert result.command_name == "version"
        assert result.command_args == ""


class TestParseInputFreeText:
    def test_simple_text(self):
        result = parse_input("hello world")
        assert result.input_type == InputType.FREE_TEXT
        assert result.at_mentions == []

    def test_text_with_file_mention(self):
        result = parse_input("check @src/main.py")
        assert result.input_type == InputType.FREE_TEXT
        assert result.at_mentions == ["src/main.py"]

    def test_text_with_directory_mention(self):
        result = parse_input("review @src/")
        assert result.input_type == InputType.FREE_TEXT
        assert result.at_mentions == ["src/"]

    def test_text_with_multiple_mentions(self):
        result = parse_input("compare @file1.py and @file2.py")
        assert result.input_type == InputType.FREE_TEXT
        assert result.at_mentions == ["file1.py", "file2.py"]

    def test_text_preserves_raw(self):
        raw = "hello world"
        result = parse_input(raw)
        assert result.raw == raw

    def test_mention_with_nested_path(self):
        result = parse_input("look at @src/agent_repl/types.py")
        assert result.at_mentions == ["src/agent_repl/types.py"]


class TestParseInputEdgeCases:
    def test_empty_input(self):
        result = parse_input("")
        assert result.input_type == InputType.FREE_TEXT
        assert result.at_mentions == []

    def test_whitespace_only(self):
        result = parse_input("   ")
        assert result.input_type == InputType.FREE_TEXT
        assert result.at_mentions == []

    def test_slash_alone(self):
        result = parse_input("/")
        assert result.input_type == InputType.FREE_TEXT

    def test_slash_with_space(self):
        result = parse_input("/ something")
        assert result.input_type == InputType.FREE_TEXT

    def test_at_alone(self):
        result = parse_input("@")
        assert result.input_type == InputType.FREE_TEXT
        # @ alone is not a valid path reference (no non-whitespace after it...
        # actually @ itself is non-whitespace so regex matches empty string after @)
        # The regex @(\S+) requires at least one char after @, so @ alone yields nothing
        assert result.at_mentions == []

    def test_at_with_space_after(self):
        result = parse_input("@ something")
        assert result.input_type == InputType.FREE_TEXT
        assert result.at_mentions == []

    def test_slash_in_middle_of_text(self):
        result = parse_input("use /help for info")
        assert result.input_type == InputType.FREE_TEXT

    def test_at_mention_at_start(self):
        result = parse_input("@README.md explain this")
        assert result.input_type == InputType.FREE_TEXT
        assert result.at_mentions == ["README.md"]

    def test_double_slash_command(self):
        result = parse_input("//something")
        assert result.input_type == InputType.SLASH_COMMAND
        assert result.command_name == "/something"


# --- Property tests ---


# Strategy: generate valid slash-command names (non-whitespace after /)
_command_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
    min_size=1,
    max_size=20,
)

_args_strategy = st.text(min_size=0, max_size=50)


class TestProperty1InputRouting:
    """Property 1: Input Routing

    For any user input string, the Input Parser SHALL classify it as
    SLASH_COMMAND if and only if it begins with `/` followed by one or
    more non-whitespace characters, and as FREE_TEXT otherwise.

    Feature: agent_repl, Property 1: Input Routing
    """

    @settings(max_examples=200)
    @given(command_name=_command_name_strategy)
    def test_slash_prefix_classified_as_command(self, command_name):
        """Any string starting with / + non-whitespace is a SLASH_COMMAND."""
        raw = f"/{command_name}"
        result = parse_input(raw)
        assert result.input_type == InputType.SLASH_COMMAND
        assert result.command_name == command_name

    @settings(max_examples=200)
    @given(command_name=_command_name_strategy, args=_args_strategy)
    def test_slash_command_args_preserved(self, command_name, args):
        """Command args are everything after the command name."""
        raw = f"/{command_name} {args}"
        result = parse_input(raw)
        assert result.input_type == InputType.SLASH_COMMAND
        assert result.command_name == command_name
        expected_args = args.strip() if args.strip() else ""
        assert result.command_args == expected_args

    @settings(max_examples=200)
    @given(text=st.text(min_size=0, max_size=100))
    def test_no_slash_prefix_classified_as_free_text(self, text):
        """Any string NOT starting with / + non-whitespace is FREE_TEXT."""
        # Ensure text doesn't start with /non-whitespace after stripping
        stripped = text.strip()
        if len(stripped) >= 2 and stripped[0] == "/" and not stripped[1].isspace():
            return  # Skip inputs that are valid slash commands
        result = parse_input(text)
        assert result.input_type == InputType.FREE_TEXT

    @settings(max_examples=200)
    @given(text=st.text(min_size=0, max_size=100))
    def test_classification_is_exhaustive(self, text):
        """Every input is classified as either SLASH_COMMAND or FREE_TEXT."""
        result = parse_input(text)
        assert result.input_type in (InputType.SLASH_COMMAND, InputType.FREE_TEXT)

    @settings(max_examples=200)
    @given(text=st.text(min_size=0, max_size=100))
    def test_raw_always_preserved(self, text):
        """The raw field always matches the original input."""
        result = parse_input(text)
        assert result.raw == text


class TestPropertyAtMentionExtraction:
    """Additional property tests for @-mention extraction.

    Feature: agent_repl, Property: AT_MENTION Extraction
    """

    @settings(max_examples=200)
    @given(
        paths=st.lists(
            st.from_regex(r"[a-zA-Z0-9_./\-]+", fullmatch=True),
            min_size=1,
            max_size=5,
        )
    )
    def test_at_mentions_extracted_from_free_text(self, paths):
        """All @path references in free text are extracted."""
        text = " ".join(f"@{p}" for p in paths)
        result = parse_input(text)
        assert result.input_type == InputType.FREE_TEXT
        assert result.at_mentions == paths

    @settings(max_examples=100)
    @given(text=st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=0, max_size=50))
    def test_no_at_symbol_means_no_mentions(self, text):
        """Text without @ has no at_mentions."""
        result = parse_input(text)
        assert result.at_mentions == []
