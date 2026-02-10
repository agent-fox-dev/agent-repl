"""Unit and property tests for the command registry module.

Property 2: Command Registration Completeness
Property 3: Built-in Command Availability
Property 5 (02_slash_command_menu): Pinned Merge and Deduplication
Property 8 (02_slash_command_menu): Backward Compatibility Default
Validates: Requirements 4.1, 4.2, 4.6, 5.4, 2.2, 2.3, 2.5, 2.6, 5.1, 5.3
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from agent_repl.command_registry import CommandRegistry
from agent_repl.types import Config, SlashCommand


def _noop(ctx):
    pass


def _make_cmd(name: str, *, pinned: bool = False) -> SlashCommand:
    return SlashCommand(
        name=name, description=f"Desc {name}", help_text="",
        handler=_noop, pinned=pinned,
    )


class TestCommandRegistry:
    def test_register_and_get(self):
        reg = CommandRegistry()
        cmd = _make_cmd("help")
        reg.register(cmd)
        assert reg.get("help") is cmd

    def test_get_nonexistent(self):
        reg = CommandRegistry()
        assert reg.get("missing") is None

    def test_all_commands_sorted(self):
        reg = CommandRegistry()
        reg.register(_make_cmd("zebra"))
        reg.register(_make_cmd("alpha"))
        reg.register(_make_cmd("middle"))
        names = [c.name for c in reg.all_commands()]
        assert names == ["alpha", "middle", "zebra"]

    def test_completions_matching_prefix(self):
        reg = CommandRegistry()
        reg.register(_make_cmd("help"))
        reg.register(_make_cmd("history"))
        reg.register(_make_cmd("quit"))
        assert reg.completions("h") == ["help", "history"]
        assert reg.completions("q") == ["quit"]
        assert reg.completions("z") == []

    def test_completions_empty_prefix(self):
        reg = CommandRegistry()
        reg.register(_make_cmd("help"))
        reg.register(_make_cmd("quit"))
        assert reg.completions("") == ["help", "quit"]

    def test_register_overwrites(self):
        reg = CommandRegistry()
        cmd1 = _make_cmd("help")
        cmd2 = SlashCommand(
            name="help", description="New desc", help_text="", handler=_noop
        )
        reg.register(cmd1)
        reg.register(cmd2)
        assert reg.get("help") is cmd2
        assert len(reg.all_commands()) == 1


# Generate command names for property tests
_cmd_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
    min_size=1,
    max_size=15,
)


class TestProperty2CommandRegistrationCompleteness:
    """Property 2: For any set of commands registered, all appear in all_commands().

    Feature: agent_repl, Property 2: Command Registration Completeness
    """

    @settings(max_examples=100)
    @given(names=st.lists(_cmd_name_strategy, min_size=1, max_size=10, unique=True))
    def test_all_registered_commands_present(self, names):
        reg = CommandRegistry()
        for name in names:
            reg.register(_make_cmd(name))
        all_names = {c.name for c in reg.all_commands()}
        assert all_names == set(names)

    @settings(max_examples=100)
    @given(
        names=st.lists(_cmd_name_strategy, min_size=1, max_size=10, unique=True),
        prefix=st.text(
            alphabet=st.characters(whitelist_categories=("L",)),
            min_size=1,
            max_size=3,
        ),
    )
    def test_completions_are_subset(self, names, prefix):
        reg = CommandRegistry()
        for name in names:
            reg.register(_make_cmd(name))
        completions = reg.completions(prefix)
        for c in completions:
            assert c.startswith(prefix)
            assert reg.get(c) is not None


class TestProperty3BuiltinCommandAvailability:
    """Property 3: /help, /quit, /version always present after registration.

    Feature: agent_repl, Property 3: Built-in Command Availability
    """

    @settings(max_examples=100)
    @given(
        extra_names=st.lists(_cmd_name_strategy, min_size=0, max_size=5, unique=True)
    )
    def test_builtins_always_present(self, extra_names):
        reg = CommandRegistry()
        # Register builtins
        for name in ["help", "quit", "version"]:
            reg.register(_make_cmd(name))
        # Register extras
        for name in extra_names:
            if name not in ("help", "quit", "version"):
                reg.register(_make_cmd(name))

        assert reg.get("help") is not None
        assert reg.get("quit") is not None
        assert reg.get("version") is not None


# --- Pinned commands tests (02_slash_command_menu) ---


class TestPinnedCommands:
    """Unit tests for CommandRegistry.pinned_commands()."""

    def test_pinned_names_order_preserved(self):
        reg = CommandRegistry()
        reg.register(_make_cmd("alpha"))
        reg.register(_make_cmd("beta"))
        reg.register(_make_cmd("gamma"))
        result = reg.pinned_commands(["gamma", "alpha"])
        assert [c.name for c in result] == ["gamma", "alpha"]

    def test_declaratively_pinned_appended(self):
        reg = CommandRegistry()
        reg.register(_make_cmd("help", pinned=True))
        reg.register(_make_cmd("quit", pinned=True))
        reg.register(_make_cmd("version"))
        result = reg.pinned_commands([])
        assert [c.name for c in result] == ["help", "quit"]

    def test_config_list_plus_declarative_merge(self):
        reg = CommandRegistry()
        reg.register(_make_cmd("help", pinned=True))
        reg.register(_make_cmd("quit", pinned=True))
        reg.register(_make_cmd("status"))
        # Config list has "status" and "quit"; "help" is declaratively pinned
        result = reg.pinned_commands(["status", "quit"])
        names = [c.name for c in result]
        # "status" and "quit" from config list first, then "help" from declarative
        assert names == ["status", "quit", "help"]

    def test_deduplication(self):
        reg = CommandRegistry()
        reg.register(_make_cmd("help", pinned=True))
        reg.register(_make_cmd("quit"))
        # "help" in config list AND declaratively pinned -> appears once
        result = reg.pinned_commands(["help", "quit"])
        names = [c.name for c in result]
        assert names == ["help", "quit"]

    def test_missing_names_skipped(self):
        reg = CommandRegistry()
        reg.register(_make_cmd("help"))
        result = reg.pinned_commands(["help", "nonexistent", "also_missing"])
        assert [c.name for c in result] == ["help"]

    def test_duplicate_names_in_list(self):
        reg = CommandRegistry()
        reg.register(_make_cmd("help"))
        result = reg.pinned_commands(["help", "help", "help"])
        assert [c.name for c in result] == ["help"]

    def test_empty_registry(self):
        reg = CommandRegistry()
        result = reg.pinned_commands(["help", "quit"])
        assert result == []

    def test_empty_pinned_names_no_declarative(self):
        reg = CommandRegistry()
        reg.register(_make_cmd("help"))
        reg.register(_make_cmd("quit"))
        result = reg.pinned_commands([])
        assert result == []


class TestProperty5PinnedMergeAndDeduplication:
    """Property 5: For any combination of Config.pinned_commands and
    SlashCommand instances with pinned=True, the resolved pinned set
    contains no duplicates, and configured names appear before
    declaratively-pinned names.

    Feature: 02_slash_command_menu, Property 5
    """

    @settings(max_examples=100)
    @given(
        config_names=st.lists(_cmd_name_strategy, min_size=0, max_size=5),
        declarative_names=st.lists(_cmd_name_strategy, min_size=0, max_size=5),
        other_names=st.lists(_cmd_name_strategy, min_size=0, max_size=5),
    )
    def test_no_duplicates_and_config_first(self, config_names, declarative_names, other_names):
        reg = CommandRegistry()
        all_registered = set()

        for name in declarative_names:
            reg.register(_make_cmd(name, pinned=True))
            all_registered.add(name)

        for name in other_names:
            if name not in all_registered:
                reg.register(_make_cmd(name))
                all_registered.add(name)

        result = reg.pinned_commands(config_names)
        result_names = [c.name for c in result]

        # No duplicates
        assert len(result_names) == len(set(result_names))

        # Config names that exist come first, in order
        config_present = [n for n in dict.fromkeys(config_names) if n in all_registered]
        assert result_names[:len(config_present)] == config_present

        # Every result is either in config_names or declaratively pinned
        for name in result_names:
            cmd = reg.get(name)
            assert name in config_names or (cmd is not None and cmd.pinned)


class TestProperty8BackwardCompatibilityDefault:
    """Property 8: For any Config instance where pinned_commands is None,
    the resolved pinned set is ['help', 'quit'].

    Feature: 02_slash_command_menu, Property 8
    """

    def test_default_pinned_commands(self):
        from agent_repl.constants import DEFAULT_PINNED_COMMANDS

        config = Config(app_name="test", app_version="1.0", default_model="m")
        assert config.pinned_commands is None

        # When resolved through the registry with defaults
        reg = CommandRegistry()
        reg.register(_make_cmd("help", pinned=True))
        reg.register(_make_cmd("quit", pinned=True))
        reg.register(_make_cmd("version"))
        reg.register(_make_cmd("copy"))

        pinned_names = (
            config.pinned_commands
            if config.pinned_commands is not None
            else DEFAULT_PINNED_COMMANDS
        )
        result = reg.pinned_commands(pinned_names)
        assert [c.name for c in result] == ["help", "quit"]

    @settings(max_examples=50)
    @given(
        extra_names=st.lists(_cmd_name_strategy, min_size=0, max_size=5, unique=True)
    )
    def test_default_always_resolves_help_quit(self, extra_names):
        from agent_repl.constants import DEFAULT_PINNED_COMMANDS

        reg = CommandRegistry()
        reg.register(_make_cmd("help", pinned=True))
        reg.register(_make_cmd("quit", pinned=True))
        for name in extra_names:
            if name not in ("help", "quit"):
                reg.register(_make_cmd(name))

        result = reg.pinned_commands(DEFAULT_PINNED_COMMANDS)
        result_names = [c.name for c in result]
        assert "help" in result_names
        assert "quit" in result_names
        # help and quit come first (from the default list)
        assert result_names[0] == "help"
        assert result_names[1] == "quit"
