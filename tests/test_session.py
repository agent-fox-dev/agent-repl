"""Unit and property tests for session manager and token statistics.

Property 4: History Accumulation
Property 5: Clear Resets History
Property 6: Compact Replaces History
Property 11: Token Statistics Monotonicity
Validates: Requirements 6.4, 6.6, 6.7, 7.1, 7.2, 11.1, 11.2
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from agent_repl.session import Session
from agent_repl.types import ConversationTurn, TokenUsage


class TestSession:
    def test_add_turn(self):
        session = Session()
        turn = ConversationTurn(role="user", content="hello")
        session.add_turn(turn)
        assert len(session.get_history()) == 1
        assert session.get_history()[0] is turn

    def test_get_history_returns_copy(self):
        session = Session()
        session.add_turn(ConversationTurn(role="user", content="a"))
        h1 = session.get_history()
        h2 = session.get_history()
        assert h1 is not h2
        assert h1 == h2

    def test_clear(self):
        session = Session()
        session.add_turn(ConversationTurn(role="user", content="a"))
        session.add_turn(ConversationTurn(role="assistant", content="b"))
        session.clear()
        assert session.get_history() == []

    def test_replace_with_summary(self):
        session = Session()
        session.add_turn(ConversationTurn(role="user", content="a"))
        session.add_turn(ConversationTurn(role="assistant", content="b"))
        session.replace_with_summary("summary text")
        history = session.get_history()
        assert len(history) == 1
        assert history[0].role == "assistant"
        assert history[0].content == "summary text"

    def test_token_accumulation(self):
        session = Session()
        session.add_turn(ConversationTurn(
            role="assistant", content="hi",
            token_usage=TokenUsage(input_tokens=100, output_tokens=50),
        ))
        assert session.stats.total_input_tokens == 100
        assert session.stats.total_output_tokens == 50

    def test_no_token_usage_skips_accumulation(self):
        session = Session()
        session.add_turn(ConversationTurn(role="user", content="hi"))
        assert session.stats.total_input_tokens == 0

    def test_not_persisted(self):
        """History is in-memory only (Req 7.2)."""
        session = Session()
        session.add_turn(ConversationTurn(role="user", content="a"))
        session2 = Session()
        assert session2.get_history() == []


# --- Property tests ---


_turn_strategy = st.builds(
    ConversationTurn,
    role=st.sampled_from(["user", "assistant"]),
    content=st.text(min_size=1, max_size=50),
)

_usage_strategy = st.builds(
    TokenUsage,
    input_tokens=st.integers(min_value=0, max_value=10000),
    output_tokens=st.integers(min_value=0, max_value=10000),
)


class TestGetLastAssistantContent:
    def test_empty_history(self):
        session = Session()
        assert session.get_last_assistant_content() is None

    def test_user_only_history(self):
        session = Session()
        session.add_turn(ConversationTurn(role="user", content="hello"))
        session.add_turn(ConversationTurn(role="user", content="world"))
        assert session.get_last_assistant_content() is None

    def test_single_assistant(self):
        session = Session()
        session.add_turn(ConversationTurn(role="user", content="q"))
        session.add_turn(ConversationTurn(role="assistant", content="answer"))
        assert session.get_last_assistant_content() == "answer"

    def test_multiple_assistants_returns_last(self):
        session = Session()
        session.add_turn(ConversationTurn(role="assistant", content="first"))
        session.add_turn(ConversationTurn(role="user", content="q"))
        session.add_turn(ConversationTurn(role="assistant", content="second"))
        assert session.get_last_assistant_content() == "second"

    def test_user_after_assistant(self):
        session = Session()
        session.add_turn(ConversationTurn(role="assistant", content="answer"))
        session.add_turn(ConversationTurn(role="user", content="follow-up"))
        assert session.get_last_assistant_content() == "answer"


class TestProperty4HistoryAccumulation:
    """Property 4: For N turns added, history contains exactly N turns.

    Feature: agent_repl, Property 4: History Accumulation
    """

    @settings(max_examples=100)
    @given(turns=st.lists(_turn_strategy, min_size=0, max_size=20))
    def test_history_length_matches_turns_added(self, turns):
        session = Session()
        for turn in turns:
            session.add_turn(turn)
        assert len(session.get_history()) == len(turns)


class TestProperty5ClearResetsHistory:
    """Property 5: After clear, history is empty.

    Feature: agent_repl, Property 5: Clear Resets History
    """

    @settings(max_examples=100)
    @given(turns=st.lists(_turn_strategy, min_size=0, max_size=20))
    def test_clear_empties_history(self, turns):
        session = Session()
        for turn in turns:
            session.add_turn(turn)
        session.clear()
        assert session.get_history() == []


class TestProperty6CompactReplacesHistory:
    """Property 6: After compact, history has exactly one summary turn.

    Feature: agent_repl, Property 6: Compact Replaces History
    """

    @settings(max_examples=100)
    @given(
        turns=st.lists(_turn_strategy, min_size=1, max_size=20),
        summary=st.text(min_size=1, max_size=100),
    )
    def test_compact_replaces_with_single_turn(self, turns, summary):
        session = Session()
        for turn in turns:
            session.add_turn(turn)
        session.replace_with_summary(summary)
        history = session.get_history()
        assert len(history) == 1
        assert history[0].role == "assistant"
        assert history[0].content == summary


class TestProperty11TokenStatisticsMonotonicity:
    """Property 11: Token counters monotonically increase.

    Feature: agent_repl, Property 11: Token Statistics Monotonicity
    """

    @settings(max_examples=100)
    @given(usages=st.lists(_usage_strategy, min_size=1, max_size=20))
    def test_token_counters_never_decrease(self, usages):
        session = Session()
        prev_input = 0
        prev_output = 0

        for usage in usages:
            session.add_turn(ConversationTurn(
                role="assistant",
                content="response",
                token_usage=usage,
            ))
            assert session.stats.total_input_tokens >= prev_input
            assert session.stats.total_output_tokens >= prev_output
            prev_input = session.stats.total_input_tokens
            prev_output = session.stats.total_output_tokens


class TestProperty2LastTurnSelection:
    """Property 2: get_last_assistant_content returns the last assistant turn's content.

    Feature: copy_last_output, Property 2: Last-Turn Selection
    """

    @settings(max_examples=100)
    @given(turns=st.lists(_turn_strategy, min_size=1, max_size=20))
    def test_returns_last_assistant_content(self, turns):
        session = Session()
        for turn in turns:
            session.add_turn(turn)

        expected = None
        for turn in turns:
            if turn.role == "assistant":
                expected = turn.content

        assert session.get_last_assistant_content() == expected
