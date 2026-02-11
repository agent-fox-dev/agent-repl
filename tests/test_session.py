"""Tests for session module.

Covers Requirements 8.1-8.7, 8.E1, 8.E2, 5.6 and Properties 7-11.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from agent_repl.session import Session, TokenStatistics
from agent_repl.types import ConversationTurn, TokenUsage

# --- TokenStatistics unit tests ---


class TestTokenStatistics:
    def test_initial_values(self):
        ts = TokenStatistics()
        assert ts.total_input == 0
        assert ts.total_output == 0

    def test_accumulate(self):
        ts = TokenStatistics()
        ts.accumulate(TokenUsage(input_tokens=10, output_tokens=20))
        assert ts.total_input == 10
        assert ts.total_output == 20

    def test_accumulate_multiple(self):
        ts = TokenStatistics()
        ts.accumulate(TokenUsage(input_tokens=10, output_tokens=5))
        ts.accumulate(TokenUsage(input_tokens=30, output_tokens=15))
        assert ts.total_input == 40
        assert ts.total_output == 20

    def test_format_below_1000(self):
        assert TokenStatistics.format_tokens(0) == "0 tokens"
        assert TokenStatistics.format_tokens(1) == "1 tokens"
        assert TokenStatistics.format_tokens(999) == "999 tokens"

    def test_format_at_1000(self):
        assert TokenStatistics.format_tokens(1000) == "1.00 k tokens"

    def test_format_above_1000(self):
        assert TokenStatistics.format_tokens(1500) == "1.50 k tokens"
        assert TokenStatistics.format_tokens(10000) == "10.00 k tokens"
        assert TokenStatistics.format_tokens(3210) == "3.21 k tokens"

    def test_format_input_output(self):
        ts = TokenStatistics()
        ts.accumulate(TokenUsage(input_tokens=500, output_tokens=2000))
        assert ts.format_input() == "500 tokens"
        assert ts.format_output() == "2.00 k tokens"


# --- Session unit tests ---


class TestSession:
    def test_initial_state(self):
        s = Session()
        assert s.get_history() == []
        assert s.last_assistant_response() is None
        assert s.stats.total_input == 0
        assert s.stats.total_output == 0

    def test_add_turn(self):
        """8.3: Adding turns."""
        s = Session()
        turn = ConversationTurn(role="user", content="hello")
        s.add_turn(turn)
        assert len(s.get_history()) == 1
        assert s.get_history()[0].content == "hello"

    def test_add_turn_with_usage(self):
        """8.2: Token accumulation."""
        s = Session()
        turn = ConversationTurn(
            role="assistant", content="hi", usage=TokenUsage(input_tokens=10, output_tokens=20)
        )
        s.add_turn(turn)
        assert s.stats.total_input == 10
        assert s.stats.total_output == 20

    def test_add_turn_without_usage(self):
        s = Session()
        turn = ConversationTurn(role="user", content="hello")
        s.add_turn(turn)
        assert s.stats.total_input == 0
        assert s.stats.total_output == 0

    def test_get_history_returns_copy(self):
        """8.4: Returns copy, not internal list."""
        s = Session()
        s.add_turn(ConversationTurn(role="user", content="hello"))
        history = s.get_history()
        history.append(ConversationTurn(role="user", content="injected"))
        assert len(s.get_history()) == 1

    def test_clear(self):
        """8.5: Clear history and stats."""
        s = Session()
        s.add_turn(
            ConversationTurn(
                role="assistant",
                content="hi",
                usage=TokenUsage(input_tokens=10, output_tokens=20),
            )
        )
        s.clear()
        assert s.get_history() == []
        assert s.stats.total_input == 0
        assert s.stats.total_output == 0

    def test_last_assistant_response(self):
        """8.6: Last assistant response."""
        s = Session()
        s.add_turn(ConversationTurn(role="user", content="q"))
        s.add_turn(ConversationTurn(role="assistant", content="a1"))
        s.add_turn(ConversationTurn(role="user", content="q2"))
        s.add_turn(ConversationTurn(role="assistant", content="a2"))
        assert s.last_assistant_response() == "a2"

    def test_last_assistant_response_empty(self):
        """8.E2: Empty session → None."""
        s = Session()
        assert s.last_assistant_response() is None

    def test_last_assistant_response_no_assistant(self):
        s = Session()
        s.add_turn(ConversationTurn(role="user", content="hello"))
        assert s.last_assistant_response() is None

    def test_replace_with_summary(self):
        """8.7: Replace history with summary."""
        s = Session()
        s.add_turn(ConversationTurn(role="user", content="q"))
        s.add_turn(ConversationTurn(role="assistant", content="a"))
        s.replace_with_summary("This is a summary.")
        history = s.get_history()
        assert len(history) == 1
        assert history[0].role == "system"
        assert history[0].content == "This is a summary."

    def test_replace_with_summary_resets_stats(self):
        s = Session()
        s.add_turn(
            ConversationTurn(
                role="assistant",
                content="hi",
                usage=TokenUsage(input_tokens=100, output_tokens=200),
            )
        )
        s.replace_with_summary("summary")
        assert s.stats.total_input == 0
        assert s.stats.total_output == 0

    def test_replace_with_summary_empty_session(self):
        """8.E1: Replace on empty session."""
        s = Session()
        s.replace_with_summary("summary of nothing")
        history = s.get_history()
        assert len(history) == 1
        assert history[0].role == "system"
        assert history[0].content == "summary of nothing"


# --- Property-based tests ---


@pytest.mark.property
class TestSessionProperties:
    @given(
        turns=st.lists(
            st.tuples(
                st.sampled_from(["user", "assistant", "system"]),
                st.text(min_size=1),
            ),
            min_size=0,
            max_size=20,
        )
    )
    def test_property7_history_ordering(self, turns: list[tuple[str, str]]):
        """Property 7: Turns returned in insertion order."""
        s = Session()
        for role, content in turns:
            s.add_turn(ConversationTurn(role=role, content=content))
        history = s.get_history()
        assert len(history) == len(turns)
        for i, (role, content) in enumerate(turns):
            assert history[i].role == role
            assert history[i].content == content

    @given(
        usages=st.lists(
            st.tuples(
                st.integers(min_value=0, max_value=100000),
                st.integers(min_value=0, max_value=100000),
            ),
            min_size=0,
            max_size=20,
        )
    )
    def test_property8_token_accumulation(self, usages: list[tuple[int, int]]):
        """Property 8: Totals equal sum of individual usages."""
        s = Session()
        for inp, out in usages:
            s.add_turn(
                ConversationTurn(
                    role="assistant",
                    content="r",
                    usage=TokenUsage(input_tokens=inp, output_tokens=out),
                )
            )
        assert s.stats.total_input == sum(u[0] for u in usages)
        assert s.stats.total_output == sum(u[1] for u in usages)

    @given(n=st.integers(min_value=0, max_value=10_000_000))
    def test_property9_token_formatting(self, n: int):
        """Property 9: Correct format for any non-negative int."""
        result = TokenStatistics.format_tokens(n)
        if n < 1000:
            assert result == f"{n} tokens"
        else:
            assert result == f"{n / 1000:.2f} k tokens"

    @given(summary=st.text(min_size=1))
    def test_property10_replace_with_summary(self, summary: str):
        """Property 10: Exactly one system turn after replace."""
        s = Session()
        # Add some turns first
        s.add_turn(ConversationTurn(role="user", content="q"))
        s.add_turn(ConversationTurn(role="assistant", content="a"))
        s.replace_with_summary(summary)
        history = s.get_history()
        assert len(history) == 1
        assert history[0].role == "system"
        assert history[0].content == summary

    @given(
        turns=st.lists(
            st.tuples(
                st.sampled_from(["user", "assistant", "system"]),
                st.text(min_size=1),
            ),
            min_size=0,
            max_size=10,
        )
    )
    def test_property11_last_assistant_response(self, turns: list[tuple[str, str]]):
        """Property 11: Returns last assistant content or None."""
        s = Session()
        for role, content in turns:
            s.add_turn(ConversationTurn(role=role, content=content))
        result = s.last_assistant_response()
        assistant_turns = [(r, c) for r, c in turns if r == "assistant"]
        if assistant_turns:
            assert result == assistant_turns[-1][1]
        else:
            assert result is None
