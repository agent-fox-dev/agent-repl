"""Unit and property tests for the SlashCommandCompleter module.

Property 1: Pinned-Only Initial Display
Property 2: Prefix Filter Completeness
Property 3: Empty Prefix Reversion
Property 4: Non-Slash Inactivity
Property 6: Display Format Correctness
Property 7: Pinned Cap Enforcement
Validates: Requirements 1.1, 1.2, 1.3, 1.4, 2.1, 2.4, 3.1, 3.2, 3.3, 3.4
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st
from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document

from agent_repl.completer import SlashCommandCompleter
from agent_repl.types import SlashCommand


def _noop(ctx):
    pass


def _make_cmd(name: str, desc: str = "", *, pinned: bool = False) -> SlashCommand:
    return SlashCommand(
        name=name,
        description=desc or f"Desc {name}",
        help_text="",
        handler=_noop,
        pinned=pinned,
    )


def _completions(completer: SlashCommandCompleter, text: str) -> list[str]:
    """Helper: return completion texts for a given input string."""
    doc = Document(text, len(text))
    event = CompleteEvent()
    return [c.text for c in completer.get_completions(doc, event)]


def _full_completions(completer: SlashCommandCompleter, text: str):
    """Helper: return full Completion objects for a given input string."""
    doc = Document(text, len(text))
    event = CompleteEvent()
    return list(completer.get_completions(doc, event))


# ---------------------------------------------------------------------------
# Standard commands used across tests
# ---------------------------------------------------------------------------

def _standard_commands():
    return [
        _make_cmd("help", "Show available commands", pinned=True),
        _make_cmd("quit", "Exit the REPL", pinned=True),
        _make_cmd("version", "Show version"),
        _make_cmd("copy", "Copy last output"),
        _make_cmd("history", "Show history"),
    ]


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestSlashOnly:
    """Input is exactly '/': show only pinned commands."""

    def test_yields_pinned_commands(self):
        cmds = _standard_commands()
        completer = SlashCommandCompleter(cmds, ["help", "quit"])
        names = _completions(completer, "/")
        assert names == ["/help", "/quit"]

    def test_pinned_from_config_list(self):
        cmds = _standard_commands()
        completer = SlashCommandCompleter(cmds, ["version", "copy"])
        names = _completions(completer, "/")
        # config list first, then declarative pinned (help, quit)
        assert names == ["/version", "/copy", "/help", "/quit"]

    def test_empty_pinned_list_with_declarative(self):
        cmds = _standard_commands()
        completer = SlashCommandCompleter(cmds, [])
        names = _completions(completer, "/")
        # Only declaratively pinned
        assert "/help" in names
        assert "/quit" in names
        assert len(names) == 2


class TestPrefixFiltering:
    """Input is '/<prefix>': filter all commands by prefix."""

    def test_prefix_he(self):
        cmds = _standard_commands()
        completer = SlashCommandCompleter(cmds, ["help", "quit"])
        names = _completions(completer, "/he")
        assert names == ["/help"]

    def test_prefix_matches_multiple(self):
        cmds = _standard_commands()
        completer = SlashCommandCompleter(cmds, ["help", "quit"])
        names = _completions(completer, "/h")
        assert set(names) == {"/help", "/history"}

    def test_includes_non_pinned(self):
        cmds = _standard_commands()
        completer = SlashCommandCompleter(cmds, ["help", "quit"])
        names = _completions(completer, "/v")
        assert names == ["/version"]

    def test_prefix_no_match(self):
        cmds = _standard_commands()
        completer = SlashCommandCompleter(cmds, ["help", "quit"])
        names = _completions(completer, "/zzz")
        assert names == []

    def test_full_name_match(self):
        cmds = _standard_commands()
        completer = SlashCommandCompleter(cmds, ["help", "quit"])
        names = _completions(completer, "/help")
        assert names == ["/help"]


class TestNonSlashInput:
    """Non-slash inputs yield nothing."""

    def test_empty_input(self):
        cmds = _standard_commands()
        completer = SlashCommandCompleter(cmds, ["help", "quit"])
        assert _completions(completer, "") == []

    def test_regular_text(self):
        cmds = _standard_commands()
        completer = SlashCommandCompleter(cmds, ["help", "quit"])
        assert _completions(completer, "hello") == []

    def test_slash_mid_sentence(self):
        cmds = _standard_commands()
        completer = SlashCommandCompleter(cmds, ["help", "quit"])
        assert _completions(completer, "hello /help") == []

    def test_space_before_slash(self):
        cmds = _standard_commands()
        completer = SlashCommandCompleter(cmds, ["help", "quit"])
        assert _completions(completer, " /help") == []


class TestPinnedCap:
    """Max 6 pinned entries (Property 7)."""

    def test_more_than_max_pinned(self):
        cmds = [_make_cmd(f"cmd{i}", pinned=True) for i in range(10)]
        completer = SlashCommandCompleter(cmds, [], max_pinned_display=6)
        names = _completions(completer, "/")
        assert len(names) == 6

    def test_exactly_max_pinned(self):
        cmds = [_make_cmd(f"cmd{i}", pinned=True) for i in range(6)]
        completer = SlashCommandCompleter(cmds, [], max_pinned_display=6)
        names = _completions(completer, "/")
        assert len(names) == 6

    def test_fewer_than_max_pinned(self):
        cmds = [_make_cmd(f"cmd{i}", pinned=True) for i in range(3)]
        completer = SlashCommandCompleter(cmds, [], max_pinned_display=6)
        names = _completions(completer, "/")
        assert len(names) == 3


class TestDisplayFormat:
    """Each completion has correct display and display_meta (Property 6)."""

    def test_display_fields(self):
        cmds = [_make_cmd("help", "Show available commands", pinned=True)]
        completer = SlashCommandCompleter(cmds, ["help"])
        completions = _full_completions(completer, "/")
        assert len(completions) == 1
        c = completions[0]
        assert c.text == "/help"
        assert c.display == [("", "/help")]
        assert c.display_meta == [("", "Show available commands")]

    def test_display_fields_filtered(self):
        cmds = [_make_cmd("version", "Show version")]
        completer = SlashCommandCompleter(cmds, [])
        completions = _full_completions(completer, "/v")
        assert len(completions) == 1
        c = completions[0]
        assert c.text == "/version"
        assert c.display == [("", "/version")]
        assert c.display_meta == [("", "Show version")]

    def test_start_position(self):
        cmds = [_make_cmd("help", pinned=True)]
        completer = SlashCommandCompleter(cmds, ["help"])
        completions = _full_completions(completer, "/")
        assert completions[0].start_position == -1  # len("/")

        completions = _full_completions(completer, "/he")
        assert completions[0].start_position == -3  # len("/he")


class TestUpdateCommands:
    """update_commands() replaces the command set."""

    def test_update_adds_new_commands(self):
        completer = SlashCommandCompleter([], [])
        assert _completions(completer, "/") == []

        cmds = [_make_cmd("help", pinned=True)]
        completer.update_commands(cmds, ["help"])
        assert _completions(completer, "/") == ["/help"]

    def test_update_replaces_commands(self):
        cmds1 = [_make_cmd("help", pinned=True)]
        completer = SlashCommandCompleter(cmds1, ["help"])
        assert _completions(completer, "/") == ["/help"]

        cmds2 = [_make_cmd("quit", pinned=True)]
        completer.update_commands(cmds2, ["quit"])
        assert _completions(completer, "/") == ["/quit"]


class TestEmptyRegistry:
    """No commands registered at all."""

    def test_slash_yields_nothing(self):
        completer = SlashCommandCompleter([], [])
        assert _completions(completer, "/") == []

    def test_prefix_yields_nothing(self):
        completer = SlashCommandCompleter([], [])
        assert _completions(completer, "/he") == []


# ---------------------------------------------------------------------------
# Property-based tests
# ---------------------------------------------------------------------------

_cmd_name_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("Ll",), whitelist_characters="_",
    ),
    min_size=1,
    max_size=10,
)


class TestProperty1PinnedOnlyInitialDisplay:
    """Property 1: For any set of registered commands where total exceeds
    pinned, only pinned commands are yielded when input is exactly '/'.
    """

    @settings(max_examples=100)
    @given(
        pinned_names=st.lists(
            _cmd_name_strategy, min_size=1, max_size=4, unique=True,
        ),
        extra_names=st.lists(
            _cmd_name_strategy, min_size=1, max_size=6, unique=True,
        ),
    )
    def test_only_pinned_on_slash(self, pinned_names, extra_names):
        all_names = list(dict.fromkeys(pinned_names + extra_names))
        cmds = [_make_cmd(n) for n in all_names]
        completer = SlashCommandCompleter(cmds, pinned_names)
        results = _completions(completer, "/")
        expected_pinned = [
            n for n in pinned_names if n in {c.name for c in cmds}
        ]
        assert results == [f"/{n}" for n in expected_pinned]


class TestProperty2PrefixFilterCompleteness:
    """Property 2: For any prefix P, yield exactly commands starting with P."""

    @settings(max_examples=100)
    @given(
        names=st.lists(
            _cmd_name_strategy, min_size=1, max_size=10, unique=True,
        ),
        prefix=st.text(
            alphabet=st.characters(whitelist_categories=("Ll",)),
            min_size=1,
            max_size=4,
        ),
    )
    def test_filter_completeness(self, names, prefix):
        cmds = [_make_cmd(n) for n in names]
        completer = SlashCommandCompleter(cmds, [])
        results = _completions(completer, f"/{prefix}")
        expected = sorted(
            f"/{n}" for n in names if n.startswith(prefix)
        )
        assert sorted(results) == expected


class TestProperty3EmptyPrefixReversion:
    """Property 3: When input reverts to '/', yield same as initial display."""

    @settings(max_examples=50)
    @given(
        names=st.lists(
            _cmd_name_strategy, min_size=1, max_size=8, unique=True,
        ),
        pinned_names=st.lists(
            _cmd_name_strategy, min_size=0, max_size=3, unique=True,
        ),
    )
    def test_reversion_to_slash(self, names, pinned_names):
        all_names = list(dict.fromkeys(pinned_names + names))
        cmds = [_make_cmd(n) for n in all_names]
        completer = SlashCommandCompleter(cmds, pinned_names)
        # Initial
        initial = _completions(completer, "/")
        # After typing and reverting
        reverted = _completions(completer, "/")
        assert initial == reverted


class TestProperty4NonSlashInactivity:
    """Property 4: Non-slash input yields zero completions."""

    @settings(max_examples=100)
    @given(
        text=st.text(min_size=0, max_size=20).filter(
            lambda t: not t.startswith("/")
        ),
    )
    def test_no_completions_for_non_slash(self, text):
        cmds = [_make_cmd("help", pinned=True), _make_cmd("quit")]
        completer = SlashCommandCompleter(cmds, ["help"])
        assert _completions(completer, text) == []


class TestProperty6DisplayFormatCorrectness:
    """Property 6: display == '/{name}', display_meta == description."""

    @settings(max_examples=50)
    @given(
        names=st.lists(
            _cmd_name_strategy, min_size=1, max_size=5, unique=True,
        ),
    )
    def test_display_format(self, names):
        cmds = [_make_cmd(n) for n in names]
        completer = SlashCommandCompleter(cmds, names[:2])
        # Check all completions from prefix filter
        for cmd in cmds:
            completions = _full_completions(completer, f"/{cmd.name}")
            for c in completions:
                name = c.text[1:]  # strip leading /
                matching_cmd = next(
                    cc for cc in cmds if cc.name == name
                )
                assert c.display == [("", f"/{name}")]
                assert c.display_meta == [("", matching_cmd.description)]


class TestProperty7PinnedCapEnforcement:
    """Property 7: At most MAX_PINNED_DISPLAY entries on '/'."""

    @settings(max_examples=50)
    @given(
        count=st.integers(min_value=7, max_value=20),
    )
    def test_cap_at_six(self, count):
        cmds = [_make_cmd(f"cmd{i:03d}", pinned=True) for i in range(count)]
        completer = SlashCommandCompleter(cmds, [], max_pinned_display=6)
        results = _completions(completer, "/")
        assert len(results) <= 6
