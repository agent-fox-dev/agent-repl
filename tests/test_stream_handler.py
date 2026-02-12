"""Tests for stream_handler module.

Covers Requirements 6.1-6.9, 6.E1, 6.E2, Property 19,
and Spec 02 integration tests (Requirements 1.1, 1.6, 3.1-3.4).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import MagicMock

import pytest
from hypothesis import given
from hypothesis import strategies as st

from agent_repl.session import Session
from agent_repl.stream_handler import StreamHandler
from agent_repl.types import StreamEvent, StreamEventType, TokenUsage

# --- Helpers ---


async def _events_from_list(events: list[StreamEvent]) -> AsyncIterator[StreamEvent]:
    """Create an async iterator from a list of StreamEvents."""
    for event in events:
        yield event


def _make_tui_mock() -> MagicMock:
    """Create a mock TUIShell with all needed methods."""
    tui = MagicMock()
    tui.start_spinner = MagicMock()
    tui.stop_spinner = MagicMock()
    tui.start_live_text = MagicMock()
    tui.append_live_text = MagicMock()
    tui.finalize_live_text = MagicMock()
    tui.show_info = MagicMock()
    tui.show_error = MagicMock()
    tui.show_tool_use = MagicMock()
    tui.show_tool_result = MagicMock()
    tui.set_last_response = MagicMock()
    return tui


# --- Unit tests ---


class TestTextDelta:
    """Requirement 6.2: TEXT_DELTA → live display."""

    @pytest.mark.asyncio
    async def test_text_delta_accumulation(self):
        tui = _make_tui_mock()
        session = Session()
        handler = StreamHandler(tui, session)

        events = [
            StreamEvent(type=StreamEventType.TEXT_DELTA, data={"text": "Hello "}),
            StreamEvent(type=StreamEventType.TEXT_DELTA, data={"text": "world"}),
        ]
        turn = await handler.handle_stream(_events_from_list(events))
        assert turn.content == "Hello world"

    @pytest.mark.asyncio
    async def test_text_delta_appends_live(self):
        tui = _make_tui_mock()
        session = Session()
        handler = StreamHandler(tui, session)

        events = [
            StreamEvent(type=StreamEventType.TEXT_DELTA, data={"text": "hi"}),
        ]
        await handler.handle_stream(_events_from_list(events))
        tui.start_live_text.assert_called_once()
        tui.append_live_text.assert_called_once_with("hi")
        tui.finalize_live_text.assert_called_once()


class TestToolUseStart:
    """Requirement 6.3: TOOL_USE_START → info display."""

    @pytest.mark.asyncio
    async def test_tool_use_start_shows_tool_use(self):
        tui = _make_tui_mock()
        session = Session()
        handler = StreamHandler(tui, session)

        events = [
            StreamEvent(
                type=StreamEventType.TOOL_USE_START,
                data={"name": "search", "id": "t1", "input": {"query": "test"}},
            ),
        ]
        await handler.handle_stream(_events_from_list(events))
        tui.show_tool_use.assert_called_once_with("search", {"query": "test"})

    @pytest.mark.asyncio
    async def test_tool_use_start_defaults_empty_input(self):
        tui = _make_tui_mock()
        session = Session()
        handler = StreamHandler(tui, session)

        events = [
            StreamEvent(
                type=StreamEventType.TOOL_USE_START,
                data={"name": "search", "id": "t1"},
            ),
        ]
        await handler.handle_stream(_events_from_list(events))
        tui.show_tool_use.assert_called_once_with("search", {})


class TestToolResult:
    """Requirement 6.4: TOOL_RESULT → panel and recording."""

    @pytest.mark.asyncio
    async def test_tool_result_renders_panel(self):
        tui = _make_tui_mock()
        session = Session()
        handler = StreamHandler(tui, session)

        events = [
            StreamEvent(
                type=StreamEventType.TOOL_RESULT,
                data={"name": "search", "result": "found 3", "is_error": False},
            ),
        ]
        turn = await handler.handle_stream(_events_from_list(events))
        tui.show_tool_result.assert_called_once_with("search", "found 3", False)
        assert len(turn.tool_uses) == 1
        assert turn.tool_uses[0].name == "search"
        assert turn.tool_uses[0].result == "found 3"
        assert turn.tool_uses[0].is_error is False

    @pytest.mark.asyncio
    async def test_tool_result_error(self):
        tui = _make_tui_mock()
        session = Session()
        handler = StreamHandler(tui, session)

        events = [
            StreamEvent(
                type=StreamEventType.TOOL_RESULT,
                data={"name": "exec", "result": "permission denied", "is_error": True},
            ),
        ]
        turn = await handler.handle_stream(_events_from_list(events))
        tui.show_tool_result.assert_called_once_with("exec", "permission denied", True)
        assert turn.tool_uses[0].is_error is True


class TestUsage:
    """Requirement 6.5: USAGE → token accumulation."""

    @pytest.mark.asyncio
    async def test_usage_accumulated(self):
        tui = _make_tui_mock()
        session = Session()
        handler = StreamHandler(tui, session)

        events = [
            StreamEvent(
                type=StreamEventType.USAGE,
                data={"input_tokens": 100, "output_tokens": 50},
            ),
        ]
        turn = await handler.handle_stream(_events_from_list(events))
        assert turn.usage is not None
        assert turn.usage.input_tokens == 100
        assert turn.usage.output_tokens == 50

    @pytest.mark.asyncio
    async def test_usage_accumulated_multiple(self):
        tui = _make_tui_mock()
        session = Session()
        handler = StreamHandler(tui, session)

        events = [
            StreamEvent(
                type=StreamEventType.USAGE,
                data={"input_tokens": 100, "output_tokens": 50},
            ),
            StreamEvent(
                type=StreamEventType.USAGE,
                data={"input_tokens": 200, "output_tokens": 30},
            ),
        ]
        turn = await handler.handle_stream(_events_from_list(events))
        assert turn.usage.input_tokens == 300
        assert turn.usage.output_tokens == 80

    @pytest.mark.asyncio
    async def test_usage_added_to_session(self):
        tui = _make_tui_mock()
        session = Session()
        handler = StreamHandler(tui, session)

        events = [
            StreamEvent(
                type=StreamEventType.USAGE,
                data={"input_tokens": 100, "output_tokens": 50},
            ),
        ]
        await handler.handle_stream(_events_from_list(events))
        assert session.stats.total_input == 100
        assert session.stats.total_output == 50


class TestErrorEvents:
    """Requirements 6.6, 6.7: Non-fatal and fatal errors."""

    @pytest.mark.asyncio
    async def test_nonfatal_error_continues(self):
        """6.6: Non-fatal error displays and continues stream."""
        tui = _make_tui_mock()
        session = Session()
        handler = StreamHandler(tui, session)

        events = [
            StreamEvent(
                type=StreamEventType.ERROR,
                data={"message": "rate limit", "fatal": False},
            ),
            StreamEvent(type=StreamEventType.TEXT_DELTA, data={"text": "continued"}),
        ]
        turn = await handler.handle_stream(_events_from_list(events))
        assert turn.content == "continued"
        tui.show_error.assert_called_once()
        assert "rate limit" in tui.show_error.call_args[0][0]

    @pytest.mark.asyncio
    async def test_fatal_error_terminates(self):
        """6.7: Fatal error terminates stream."""
        tui = _make_tui_mock()
        session = Session()
        handler = StreamHandler(tui, session)

        events = [
            StreamEvent(
                type=StreamEventType.ERROR,
                data={"message": "connection lost", "fatal": True},
            ),
            StreamEvent(type=StreamEventType.TEXT_DELTA, data={"text": "should not see"}),
        ]
        turn = await handler.handle_stream(_events_from_list(events))
        assert turn.content == ""  # No text accumulated after fatal error
        tui.show_error.assert_called_once()
        assert "connection lost" in tui.show_error.call_args[0][0]


class TestSpinnerDismissal:
    """Requirement 6.8: Spinner dismissed on first content."""

    @pytest.mark.asyncio
    async def test_spinner_dismissed_on_text_delta(self):
        tui = _make_tui_mock()
        session = Session()
        handler = StreamHandler(tui, session)

        events = [
            StreamEvent(type=StreamEventType.TEXT_DELTA, data={"text": "hi"}),
        ]
        await handler.handle_stream(_events_from_list(events))
        # Spinner started, then stopped on first content
        tui.start_spinner.assert_called_once()
        # stop_spinner called at least once (on first content + finalize)
        assert tui.stop_spinner.call_count >= 1

    @pytest.mark.asyncio
    async def test_spinner_dismissed_on_tool_use_start(self):
        tui = _make_tui_mock()
        session = Session()
        handler = StreamHandler(tui, session)

        events = [
            StreamEvent(
                type=StreamEventType.TOOL_USE_START,
                data={"name": "tool1", "id": "t1"},
            ),
        ]
        await handler.handle_stream(_events_from_list(events))
        tui.start_spinner.assert_called_once()
        assert tui.stop_spinner.call_count >= 1


class TestEmptyStream:
    """Requirement 6.E1: Empty stream → empty turn."""

    @pytest.mark.asyncio
    async def test_empty_stream(self):
        tui = _make_tui_mock()
        session = Session()
        handler = StreamHandler(tui, session)

        turn = await handler.handle_stream(_events_from_list([]))
        assert turn.role == "assistant"
        assert turn.content == ""
        assert turn.tool_uses == []
        assert turn.usage is None
        # Spinner should still be stopped
        tui.stop_spinner.assert_called()


class TestStreamFinalization:
    """Requirement 6.9: Stream finalization builds ConversationTurn."""

    @pytest.mark.asyncio
    async def test_full_stream(self):
        tui = _make_tui_mock()
        session = Session()
        handler = StreamHandler(tui, session)

        events = [
            StreamEvent(type=StreamEventType.TEXT_DELTA, data={"text": "Hello"}),
            StreamEvent(
                type=StreamEventType.TOOL_USE_START,
                data={"name": "search", "id": "t1"},
            ),
            StreamEvent(
                type=StreamEventType.TOOL_RESULT,
                data={"name": "search", "result": "ok", "is_error": False},
            ),
            StreamEvent(
                type=StreamEventType.USAGE,
                data={"input_tokens": 10, "output_tokens": 20},
            ),
        ]
        turn = await handler.handle_stream(_events_from_list(events))
        assert turn.role == "assistant"
        assert turn.content == "Hello"
        assert len(turn.tool_uses) == 1
        assert turn.usage == TokenUsage(input_tokens=10, output_tokens=20)

    @pytest.mark.asyncio
    async def test_turn_added_to_session(self):
        tui = _make_tui_mock()
        session = Session()
        handler = StreamHandler(tui, session)

        events = [
            StreamEvent(type=StreamEventType.TEXT_DELTA, data={"text": "hi"}),
        ]
        await handler.handle_stream(_events_from_list(events))
        history = session.get_history()
        assert len(history) == 1
        assert history[0].role == "assistant"
        assert history[0].content == "hi"

    @pytest.mark.asyncio
    async def test_last_response_set(self):
        tui = _make_tui_mock()
        session = Session()
        handler = StreamHandler(tui, session)

        events = [
            StreamEvent(type=StreamEventType.TEXT_DELTA, data={"text": "response"}),
        ]
        await handler.handle_stream(_events_from_list(events))
        tui.set_last_response.assert_called_once_with("response")

    @pytest.mark.asyncio
    async def test_empty_response_no_last_response(self):
        tui = _make_tui_mock()
        session = Session()
        handler = StreamHandler(tui, session)

        await handler.handle_stream(_events_from_list([]))
        tui.set_last_response.assert_not_called()


# --- Property-based tests ---


def _event_strategy() -> st.SearchStrategy[StreamEvent]:
    """Strategy for generating random StreamEvents."""
    return st.one_of(
        st.builds(
            StreamEvent,
            type=st.just(StreamEventType.TEXT_DELTA),
            data=st.fixed_dictionaries({"text": st.text(min_size=0, max_size=20)}),
        ),
        st.builds(
            StreamEvent,
            type=st.just(StreamEventType.TOOL_USE_START),
            data=st.fixed_dictionaries(
                {"name": st.text(min_size=1, max_size=10), "id": st.text(min_size=1, max_size=5)}
            ),
        ),
        st.builds(
            StreamEvent,
            type=st.just(StreamEventType.TOOL_RESULT),
            data=st.fixed_dictionaries(
                {
                    "name": st.text(min_size=1, max_size=10),
                    "result": st.text(min_size=0, max_size=20),
                    "is_error": st.booleans(),
                }
            ),
        ),
        st.builds(
            StreamEvent,
            type=st.just(StreamEventType.USAGE),
            data=st.fixed_dictionaries(
                {
                    "input_tokens": st.integers(min_value=0, max_value=10000),
                    "output_tokens": st.integers(min_value=0, max_value=10000),
                }
            ),
        ),
        st.builds(
            StreamEvent,
            type=st.just(StreamEventType.ERROR),
            data=st.fixed_dictionaries(
                {"message": st.text(min_size=1, max_size=20), "fatal": st.just(False)}
            ),
        ),
    )


@pytest.mark.property
class TestStreamHandlerProperties:
    @given(
        events=st.lists(_event_strategy(), min_size=0, max_size=15),
    )
    @pytest.mark.asyncio
    async def test_property19_stream_finalization(self, events: list[StreamEvent]):
        """Property 19: Any stream produces exactly one ConversationTurn."""
        tui = _make_tui_mock()
        session = Session()
        handler = StreamHandler(tui, session)

        turn = await handler.handle_stream(_events_from_list(events))

        # Exactly one turn produced
        assert turn is not None
        assert turn.role == "assistant"

        # Turn was added to session
        history = session.get_history()
        assert len(history) == 1
        assert history[0] is turn

        # Text content is concatenation of all TEXT_DELTA texts
        expected_text = "".join(
            e.data.get("text", "")
            for e in events
            if e.type == StreamEventType.TEXT_DELTA
        )
        assert turn.content == expected_text

        # Tool uses count matches TOOL_RESULT count
        tool_result_count = sum(
            1 for e in events if e.type == StreamEventType.TOOL_RESULT
        )
        assert len(turn.tool_uses) == tool_result_count


# --- Integration tests: Spec 02 Tool Display Enhancement ---


class TestToolInputIntegration:
    """Integration: TOOL_USE_START with input flows through stream_handler.

    Validates: Requirements 1.1, 1.6. Property 1: Tool Input Inclusion.
    """

    @pytest.mark.asyncio
    async def test_tool_input_passed_to_tui(self):
        """Full flow: event with input → stream_handler → tui.show_tool_use."""
        tui = _make_tui_mock()
        session = Session()
        handler = StreamHandler(tui, session)

        tool_input = {"command": "ls -la", "timeout": 30}
        events = [
            StreamEvent(
                type=StreamEventType.TOOL_USE_START,
                data={"name": "bash", "id": "t1", "input": tool_input},
            ),
        ]
        await handler.handle_stream(_events_from_list(events))
        tui.show_tool_use.assert_called_once_with("bash", tool_input)

    @pytest.mark.asyncio
    async def test_tool_input_with_nested_objects(self):
        """Nested input dict flows through unchanged."""
        tui = _make_tui_mock()
        session = Session()
        handler = StreamHandler(tui, session)

        tool_input = {"data": {"nested": {"deep": True}}, "mode": "verbose"}
        events = [
            StreamEvent(
                type=StreamEventType.TOOL_USE_START,
                data={"name": "api", "id": "t2", "input": tool_input},
            ),
        ]
        await handler.handle_stream(_events_from_list(events))
        tui.show_tool_use.assert_called_once_with("api", tool_input)

    @pytest.mark.asyncio
    async def test_tool_input_empty_dict(self):
        """Empty input dict passed as-is."""
        tui = _make_tui_mock()
        session = Session()
        handler = StreamHandler(tui, session)

        events = [
            StreamEvent(
                type=StreamEventType.TOOL_USE_START,
                data={"name": "ping", "id": "t3", "input": {}},
            ),
        ]
        await handler.handle_stream(_events_from_list(events))
        tui.show_tool_use.assert_called_once_with("ping", {})

    @pytest.mark.property
    @given(
        tool_input=st.dictionaries(
            st.text(min_size=1, max_size=10),
            st.text(min_size=0, max_size=50),
            min_size=0,
            max_size=5,
        ),
    )
    @pytest.mark.asyncio
    async def test_property1_tool_input_inclusion(
        self, tool_input: dict[str, str],
    ):
        """Property 1: TOOL_USE_START event input is passed to TUI."""
        tui = _make_tui_mock()
        session = Session()
        handler = StreamHandler(tui, session)

        events = [
            StreamEvent(
                type=StreamEventType.TOOL_USE_START,
                data={"name": "tool", "id": "t1", "input": tool_input},
            ),
        ]
        await handler.handle_stream(_events_from_list(events))
        tui.show_tool_use.assert_called_once_with("tool", tool_input)


class TestCollapsibleOutputIntegration:
    """Integration: TOOL_RESULT with >3 lines flows through stream_handler.

    Validates: Requirements 3.1-3.4.
    """

    @pytest.mark.asyncio
    async def test_long_result_collapse_end_to_end(self):
        """Full flow: multi-line result → stream_handler → tui.show_tool_result."""
        tui = _make_tui_mock()
        session = Session()
        handler = StreamHandler(tui, session)

        long_result = "\n".join(f"line{i}" for i in range(10))
        events = [
            StreamEvent(
                type=StreamEventType.TOOL_RESULT,
                data={
                    "name": "search",
                    "result": long_result,
                    "is_error": False,
                },
            ),
        ]
        turn = await handler.handle_stream(_events_from_list(events))

        tui.show_tool_result.assert_called_once_with(
            "search", long_result, False,
        )
        assert len(turn.tool_uses) == 1
        assert turn.tool_uses[0].result == long_result

    @pytest.mark.asyncio
    async def test_error_result_full_end_to_end(self):
        """Error results pass through with is_error=True."""
        tui = _make_tui_mock()
        session = Session()
        handler = StreamHandler(tui, session)

        error_result = "\n".join(f"err{i}" for i in range(10))
        events = [
            StreamEvent(
                type=StreamEventType.TOOL_RESULT,
                data={
                    "name": "exec",
                    "result": error_result,
                    "is_error": True,
                },
            ),
        ]
        turn = await handler.handle_stream(_events_from_list(events))

        tui.show_tool_result.assert_called_once_with(
            "exec", error_result, True,
        )
        assert turn.tool_uses[0].is_error is True

    @pytest.mark.asyncio
    async def test_mixed_stream_tool_input_and_result(self):
        """Full stream: text + tool use with input + tool result."""
        tui = _make_tui_mock()
        session = Session()
        handler = StreamHandler(tui, session)

        long_result = "\n".join(f"out{i}" for i in range(5))
        events = [
            StreamEvent(
                type=StreamEventType.TEXT_DELTA,
                data={"text": "Let me search."},
            ),
            StreamEvent(
                type=StreamEventType.TOOL_USE_START,
                data={
                    "name": "search",
                    "id": "t1",
                    "input": {"query": "test"},
                },
            ),
            StreamEvent(
                type=StreamEventType.TOOL_RESULT,
                data={
                    "name": "search",
                    "result": long_result,
                    "is_error": False,
                },
            ),
            StreamEvent(
                type=StreamEventType.USAGE,
                data={"input_tokens": 50, "output_tokens": 25},
            ),
        ]
        turn = await handler.handle_stream(_events_from_list(events))

        assert turn.content == "Let me search."
        tui.show_tool_use.assert_called_once_with("search", {"query": "test"})
        tui.show_tool_result.assert_called_once_with(
            "search", long_result, False,
        )
        assert len(turn.tool_uses) == 1
        assert turn.usage.input_tokens == 50
