"""Tests for command_registry module.

Covers Requirements 4.1-4.5, 4.E1-4.E3 and Properties 4-6.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from agent_repl.command_registry import CommandRegistry
from agent_repl.types import SlashCommand


async def _noop(ctx: object) -> None:
    pass


def _cmd(name: str, description: str = "") -> SlashCommand:
    return SlashCommand(name=name, description=description or f"Desc for {name}", handler=_noop)


# --- Unit tests ---


class TestRegister:
    """Requirement 4.1: Registration of SlashCommand objects."""

    def test_register_single(self):
        reg = CommandRegistry()
        reg.register(_cmd("help"))
        assert reg.get("help") is not None

    def test_register_multiple(self):
        reg = CommandRegistry()
        reg.register(_cmd("help"))
        reg.register(_cmd("quit"))
        assert reg.get("help") is not None
        assert reg.get("quit") is not None


class TestGet:
    """Requirement 4.2: Exact lookup by command name."""

    def test_existing_command(self):
        reg = CommandRegistry()
        cmd = _cmd("version")
        reg.register(cmd)
        assert reg.get("version") is cmd

    def test_missing_command(self):
        reg = CommandRegistry()
        assert reg.get("nonexistent") is None

    def test_empty_registry(self):
        reg = CommandRegistry()
        assert reg.get("anything") is None


class TestListAll:
    """Requirement 4.3: Alphabetically sorted listing."""

    def test_sorted_order(self):
        reg = CommandRegistry()
        reg.register(_cmd("quit"))
        reg.register(_cmd("help"))
        reg.register(_cmd("agent"))
        result = reg.list_all()
        names = [c.name for c in result]
        assert names == ["agent", "help", "quit"]

    def test_empty_registry(self):
        reg = CommandRegistry()
        assert reg.list_all() == []


class TestComplete:
    """Requirement 4.4: Prefix-based completion."""

    def test_prefix_match(self):
        reg = CommandRegistry()
        reg.register(_cmd("help"))
        reg.register(_cmd("history"))
        reg.register(_cmd("quit"))
        result = reg.complete("h")
        names = [c.name for c in result]
        assert names == ["help", "history"]

    def test_exact_match(self):
        reg = CommandRegistry()
        reg.register(_cmd("help"))
        result = reg.complete("help")
        assert len(result) == 1
        assert result[0].name == "help"

    def test_no_match(self):
        """4.E1: No commands match prefix."""
        reg = CommandRegistry()
        reg.register(_cmd("help"))
        assert reg.complete("z") == []

    def test_empty_prefix(self):
        reg = CommandRegistry()
        reg.register(_cmd("help"))
        reg.register(_cmd("quit"))
        result = reg.complete("")
        assert len(result) == 2

    def test_empty_registry(self):
        reg = CommandRegistry()
        assert reg.complete("h") == []


class TestGetPinned:
    """Requirement 4.5: Pinned commands in order, capped at max_count."""

    def test_basic_pinned(self):
        reg = CommandRegistry()
        reg.register(_cmd("help"))
        reg.register(_cmd("quit"))
        reg.register(_cmd("agent"))
        result = reg.get_pinned(["help", "quit"], max_count=6)
        names = [c.name for c in result]
        assert names == ["help", "quit"]

    def test_pinned_order_preserved(self):
        reg = CommandRegistry()
        reg.register(_cmd("help"))
        reg.register(_cmd("quit"))
        reg.register(_cmd("agent"))
        result = reg.get_pinned(["quit", "help"], max_count=6)
        names = [c.name for c in result]
        assert names == ["quit", "help"]

    def test_pinned_unregistered_skipped(self):
        reg = CommandRegistry()
        reg.register(_cmd("help"))
        result = reg.get_pinned(["help", "nonexistent", "quit"], max_count=6)
        names = [c.name for c in result]
        assert names == ["help"]

    def test_pinned_max_count_cap(self):
        reg = CommandRegistry()
        reg.register(_cmd("a"))
        reg.register(_cmd("b"))
        reg.register(_cmd("c"))
        result = reg.get_pinned(["a", "b", "c"], max_count=2)
        assert len(result) == 2
        assert result[0].name == "a"
        assert result[1].name == "b"

    def test_empty_pinned_list(self):
        """4.E2: Empty pinned list returns nothing."""
        reg = CommandRegistry()
        reg.register(_cmd("help"))
        assert reg.get_pinned([], max_count=6) == []

    def test_zero_max_count(self):
        reg = CommandRegistry()
        reg.register(_cmd("help"))
        assert reg.get_pinned(["help"], max_count=0) == []


class TestOverride:
    """Requirement 4.E3: Name override (last-write-wins)."""

    def test_override_replaces(self):
        reg = CommandRegistry()
        cmd1 = _cmd("help", "original")
        cmd2 = _cmd("help", "replacement")
        reg.register(cmd1)
        reg.register(cmd2)
        result = reg.get("help")
        assert result is cmd2
        assert result.description == "replacement"

    def test_override_no_duplicates_in_list_all(self):
        reg = CommandRegistry()
        reg.register(_cmd("help", "original"))
        reg.register(_cmd("help", "replacement"))
        result = reg.list_all()
        assert len(result) == 1
        assert result[0].description == "replacement"


# --- Property-based tests ---


@pytest.mark.property
class TestCommandRegistryProperties:
    @given(
        names=st.lists(st.text(min_size=1, max_size=20), min_size=0, max_size=30),
    )
    def test_property4_lookup_consistency(self, names: list[str]):
        """Property 4: Last registered handler wins; list_all alphabetical."""
        reg = CommandRegistry()
        for i, name in enumerate(names):
            reg.register(_cmd(name, f"desc-{i}"))

        # The last registered description for each name should be returned
        last_desc: dict[str, str] = {}
        for i, name in enumerate(names):
            last_desc[name] = f"desc-{i}"

        for name, desc in last_desc.items():
            cmd = reg.get(name)
            assert cmd is not None
            assert cmd.description == desc

        # list_all is alphabetically sorted
        all_cmds = reg.list_all()
        all_names = [c.name for c in all_cmds]
        assert all_names == sorted(set(names))

    @given(
        names=st.lists(
            st.text(
                alphabet=st.characters(categories=("L", "N")),
                min_size=1,
                max_size=10,
            ),
            min_size=0,
            max_size=20,
        ),
        prefix=st.text(
            alphabet=st.characters(categories=("L", "N")),
            min_size=0,
            max_size=5,
        ),
    )
    def test_property5_prefix_completion(self, names: list[str], prefix: str):
        """Property 5: Exact subset matching prefix, sorted."""
        reg = CommandRegistry()
        for name in names:
            reg.register(_cmd(name))

        result = reg.complete(prefix)
        result_names = [c.name for c in result]

        # Should be exactly the unique names that start with prefix, sorted
        expected = sorted(set(n for n in names if n.startswith(prefix)))
        assert result_names == expected

    @given(
        registered=st.lists(
            st.text(min_size=1, max_size=10),
            min_size=0,
            max_size=10,
        ),
        pinned=st.lists(
            st.text(min_size=1, max_size=10),
            min_size=0,
            max_size=10,
        ),
        max_count=st.integers(min_value=0, max_value=20),
    )
    def test_property6_pinned_subset(
        self, registered: list[str], pinned: list[str], max_count: int
    ):
        """Property 6: Only registered + pinned, in pinned order, capped."""
        reg = CommandRegistry()
        for name in registered:
            reg.register(_cmd(name))

        result = reg.get_pinned(pinned, max_count)

        # Each result must be both pinned and registered
        registered_set = set(registered)
        for cmd in result:
            assert cmd.name in registered_set

        # Results must be in pinned order (subset of pinned that are registered)
        expected_names: list[str] = []
        seen: set[str] = set()
        for name in pinned:
            if len(expected_names) >= max_count:
                break
            if name in registered_set and name not in seen:
                expected_names.append(name)
                seen.add(name)

        result_names = [c.name for c in result]
        assert result_names == expected_names
        assert len(result) <= max_count
