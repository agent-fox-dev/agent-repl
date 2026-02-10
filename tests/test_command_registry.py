"""Unit and property tests for the command registry module.

Property 2: Command Registration Completeness
Property 3: Built-in Command Availability
Validates: Requirements 4.1, 4.2, 4.6, 5.4
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from agent_repl.command_registry import CommandRegistry
from agent_repl.types import SlashCommand


def _noop(ctx):
    pass


def _make_cmd(name: str) -> SlashCommand:
    return SlashCommand(name=name, description=f"Desc {name}", help_text="", handler=_noop)


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
