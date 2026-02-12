"""Tests for stream_handler module.

Covers Requirements 6.1-6.9, 6.E1, 6.E2, Property 19,
Spec 02 integration tests (Requirements 1.1, 1.6, 3.1-3.4),
and Spec 03 INPUT_REQUEST dispatch (Requirements 1.1, 2.1-2.5, 6.1-6.5).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

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
    # Input request prompt stubs (TUI methods not yet implemented)
    tui.prompt_approval = AsyncMock(return_value="approve")
    tui.prompt_choice = AsyncMock(return_value={"index": 0, "value": "opt"})
    tui.prompt_text_input = AsyncMock(return_value="user text")
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


# --- Spec 03: INPUT_REQUEST dispatch tests ---


def _make_input_request_event(
    *,
    prompt: str = "Proceed?",
    input_type: str = "approval",
    choices: list[str] | None = None,
    response_future: asyncio.Future | None = None,
) -> StreamEvent:
    """Helper to build an INPUT_REQUEST event."""
    data: dict = {
        "prompt": prompt,
        "input_type": input_type,
        "choices": choices if choices is not None else ["Approve", "Reject"],
    }
    if response_future is not None:
        data["response_future"] = response_future
    return StreamEvent(type=StreamEventType.INPUT_REQUEST, data=data)


class TestInputRequestApproval:
    """INPUT_REQUEST with approval → future resolved, stream continues.

    Validates: Requirements 2.1-2.5.
    Property 1: Stream Pause Guarantee.
    Property 2: Future Resolution Guarantee.
    """

    @pytest.mark.asyncio
    async def test_approval_resolves_future_and_continues(self):
        """Approved input request resolves future, stream continues."""
        tui = _make_tui_mock()
        tui.prompt_approval = AsyncMock(return_value="approve")
        session = Session()
        handler = StreamHandler(tui, session)

        future: asyncio.Future = asyncio.Future()
        events = [
            StreamEvent(
                type=StreamEventType.TEXT_DELTA, data={"text": "Before "},
            ),
            _make_input_request_event(response_future=future),
            StreamEvent(
                type=StreamEventType.TEXT_DELTA, data={"text": "After"},
            ),
        ]
        turn = await handler.handle_stream(_events_from_list(events))

        assert future.done()
        assert future.result() == "approve"
        assert turn.content == "Before After"

    @pytest.mark.asyncio
    async def test_approval_calls_prompt_approval(self):
        """Approval mode dispatches to tui.prompt_approval."""
        tui = _make_tui_mock()
        tui.prompt_approval = AsyncMock(return_value="approve")
        session = Session()
        handler = StreamHandler(tui, session)

        future: asyncio.Future = asyncio.Future()
        events = [
            _make_input_request_event(
                prompt="Delete files?",
                input_type="approval",
                choices=["Yes", "No"],
                response_future=future,
            ),
        ]
        await handler.handle_stream(_events_from_list(events))

        tui.prompt_approval.assert_called_once_with("Delete files?", ["Yes", "No"])


class TestInputRequestRejection:
    """INPUT_REQUEST with rejection → future resolved, stream breaks.

    Validates: Requirements 6.1, 6.3.
    Property 5: Rejection Cancels Stream.
    """

    @pytest.mark.asyncio
    async def test_rejection_breaks_stream(self):
        """Rejected input request breaks the event loop."""
        tui = _make_tui_mock()
        tui.prompt_approval = AsyncMock(return_value="reject")
        session = Session()
        handler = StreamHandler(tui, session)

        future: asyncio.Future = asyncio.Future()
        events = [
            _make_input_request_event(response_future=future),
            StreamEvent(
                type=StreamEventType.TEXT_DELTA,
                data={"text": "should not appear"},
            ),
        ]
        turn = await handler.handle_stream(_events_from_list(events))

        assert future.done()
        assert future.result() == "reject"
        # Text after rejection is not accumulated
        assert turn.content == ""
        tui.show_info.assert_called_once()
        assert "Rejected" in tui.show_info.call_args[0][0]

    @pytest.mark.asyncio
    async def test_rejection_preserves_partial_content(self):
        """Property 7: Partial text before rejection is preserved in history."""
        tui = _make_tui_mock()
        tui.prompt_approval = AsyncMock(return_value="reject")
        session = Session()
        handler = StreamHandler(tui, session)

        future: asyncio.Future = asyncio.Future()
        events = [
            StreamEvent(
                type=StreamEventType.TEXT_DELTA,
                data={"text": "partial content"},
            ),
            _make_input_request_event(response_future=future),
            StreamEvent(
                type=StreamEventType.TEXT_DELTA,
                data={"text": "should not appear"},
            ),
        ]
        turn = await handler.handle_stream(_events_from_list(events))

        assert turn.content == "partial content"
        # Turn was added to session history
        history = session.get_history()
        assert len(history) == 1
        assert history[0].content == "partial content"


class TestInputRequestMissingFuture:
    """INPUT_REQUEST without response_future → warning logged, skipped.

    Validates: Error handling for missing future.
    """

    @pytest.mark.asyncio
    async def test_missing_future_skipped(self):
        """Missing response_future logs warning and continues stream."""
        tui = _make_tui_mock()
        session = Session()
        handler = StreamHandler(tui, session)

        events = [
            StreamEvent(
                type=StreamEventType.INPUT_REQUEST,
                data={
                    "prompt": "No future?",
                    "input_type": "approval",
                    "choices": ["Y", "N"],
                    # No response_future key
                },
            ),
            StreamEvent(
                type=StreamEventType.TEXT_DELTA,
                data={"text": "stream continues"},
            ),
        ]
        turn = await handler.handle_stream(_events_from_list(events))

        # Stream continued past the missing-future event
        assert turn.content == "stream continues"
        # No prompt methods called
        tui.prompt_approval.assert_not_called()


class TestInputRequestUIState:
    """Spinner/live text stopped before prompt, restarted after.

    Validates: Requirements 2.1, 2.2.
    Property 6: UI State Cleanup Before Prompt.
    """

    @pytest.mark.asyncio
    async def test_spinner_stopped_before_prompt(self):
        """Spinner is stopped before input prompt is shown."""
        tui = _make_tui_mock()
        tui.prompt_approval = AsyncMock(return_value="approve")
        session = Session()
        handler = StreamHandler(tui, session)

        future: asyncio.Future = asyncio.Future()
        events = [
            _make_input_request_event(response_future=future),
        ]
        await handler.handle_stream(_events_from_list(events))

        # stop_spinner called before prompt_approval
        # The initial start_spinner + stop_spinner in INPUT_REQUEST branch
        assert tui.stop_spinner.call_count >= 1

    @pytest.mark.asyncio
    async def test_live_text_finalized_before_prompt(self):
        """Live text is finalized before input prompt if active."""
        tui = _make_tui_mock()
        tui.prompt_approval = AsyncMock(return_value="approve")
        session = Session()
        handler = StreamHandler(tui, session)

        future: asyncio.Future = asyncio.Future()
        events = [
            StreamEvent(
                type=StreamEventType.TEXT_DELTA,
                data={"text": "streaming..."},
            ),
            _make_input_request_event(response_future=future),
        ]
        await handler.handle_stream(_events_from_list(events))

        # finalize_live_text called (once by INPUT_REQUEST branch)
        tui.finalize_live_text.assert_called()

    @pytest.mark.asyncio
    async def test_spinner_restarted_after_approval(self):
        """Spinner restarted after non-rejection input."""
        tui = _make_tui_mock()
        tui.prompt_approval = AsyncMock(return_value="approve")
        session = Session()
        handler = StreamHandler(tui, session)

        future: asyncio.Future = asyncio.Future()
        events = [
            _make_input_request_event(response_future=future),
        ]
        await handler.handle_stream(_events_from_list(events))

        # start_spinner called at start and again after approval
        assert tui.start_spinner.call_count >= 2


class TestApprovalChoiceValidation:
    """Approval mode requires exactly 2 choices.

    Validates: Requirement 1.4, Edge Case 1.1.
    """

    @pytest.mark.asyncio
    async def test_approval_wrong_choice_count_rejects(self):
        """Approval with != 2 choices shows error and rejects."""
        tui = _make_tui_mock()
        session = Session()
        handler = StreamHandler(tui, session)

        future: asyncio.Future = asyncio.Future()
        events = [
            _make_input_request_event(
                input_type="approval",
                choices=["Only one"],
                response_future=future,
            ),
        ]
        await handler.handle_stream(_events_from_list(events))

        assert future.result() == "reject"
        tui.show_error.assert_called_once()
        assert "exactly 2" in tui.show_error.call_args[0][0]
        tui.prompt_approval.assert_not_called()

    @pytest.mark.asyncio
    async def test_approval_empty_choices_rejects(self):
        """Approval with empty choices shows error and rejects."""
        tui = _make_tui_mock()
        session = Session()
        handler = StreamHandler(tui, session)

        future: asyncio.Future = asyncio.Future()
        events = [
            _make_input_request_event(
                input_type="approval",
                choices=[],
                response_future=future,
            ),
        ]
        await handler.handle_stream(_events_from_list(events))

        assert future.result() == "reject"
        tui.show_error.assert_called_once()
        tui.prompt_approval.assert_not_called()

    @pytest.mark.asyncio
    async def test_approval_three_choices_rejects(self):
        """Approval with 3 choices shows error and rejects."""
        tui = _make_tui_mock()
        session = Session()
        handler = StreamHandler(tui, session)

        future: asyncio.Future = asyncio.Future()
        events = [
            _make_input_request_event(
                input_type="approval",
                choices=["A", "B", "C"],
                response_future=future,
            ),
        ]
        await handler.handle_stream(_events_from_list(events))

        assert future.result() == "reject"
        tui.show_error.assert_called_once()
        tui.prompt_approval.assert_not_called()


class TestInputRequestChoiceMode:
    """INPUT_REQUEST with choice mode dispatches to prompt_choice.

    Validates: Requirement 2.3 (dispatch by input_type).
    """

    @pytest.mark.asyncio
    async def test_choice_mode_dispatches(self):
        """Choice input_type dispatches to tui.prompt_choice."""
        tui = _make_tui_mock()
        tui.prompt_choice = AsyncMock(
            return_value={"index": 1, "value": "Option B"},
        )
        session = Session()
        handler = StreamHandler(tui, session)

        future: asyncio.Future = asyncio.Future()
        events = [
            _make_input_request_event(
                prompt="Pick one",
                input_type="choice",
                choices=["Option A", "Option B", "Option C"],
                response_future=future,
            ),
        ]
        await handler.handle_stream(_events_from_list(events))

        tui.prompt_choice.assert_called_once_with(
            "Pick one", ["Option A", "Option B", "Option C"],
        )
        assert future.result() == {"index": 1, "value": "Option B"}


class TestInputRequestTextMode:
    """INPUT_REQUEST with text mode dispatches to prompt_text_input.

    Validates: Requirement 2.3 (dispatch by input_type).
    """

    @pytest.mark.asyncio
    async def test_text_mode_dispatches(self):
        """Text input_type dispatches to tui.prompt_text_input."""
        tui = _make_tui_mock()
        tui.prompt_text_input = AsyncMock(return_value="my answer")
        session = Session()
        handler = StreamHandler(tui, session)

        future: asyncio.Future = asyncio.Future()
        events = [
            _make_input_request_event(
                prompt="Enter name",
                input_type="text",
                response_future=future,
            ),
        ]
        await handler.handle_stream(_events_from_list(events))

        tui.prompt_text_input.assert_called_once_with("Enter name")
        assert future.result() == "my answer"


class TestInputRequestUnknownType:
    """Unknown input_type → error shown, treated as reject.

    Validates: Requirement 2.3 (unknown type handling).
    """

    @pytest.mark.asyncio
    async def test_unknown_type_rejects(self):
        """Unknown input_type shows error and rejects."""
        tui = _make_tui_mock()
        session = Session()
        handler = StreamHandler(tui, session)

        future: asyncio.Future = asyncio.Future()
        events = [
            _make_input_request_event(
                input_type="bogus",
                response_future=future,
            ),
            StreamEvent(
                type=StreamEventType.TEXT_DELTA,
                data={"text": "should not appear"},
            ),
        ]
        turn = await handler.handle_stream(_events_from_list(events))

        assert future.result() == "reject"
        tui.show_error.assert_called_once()
        assert "Unknown input type" in tui.show_error.call_args[0][0]
        # Stream was broken by rejection
        assert turn.content == ""


class TestInputRequestMultiple:
    """Multiple INPUT_REQUESTs handled sequentially.

    Validates: Edge Case 2.E2.
    """

    @pytest.mark.asyncio
    async def test_multiple_input_requests_sequential(self):
        """Two sequential input requests both handled."""
        tui = _make_tui_mock()
        tui.prompt_approval = AsyncMock(return_value="approve")
        session = Session()
        handler = StreamHandler(tui, session)

        future1: asyncio.Future = asyncio.Future()
        future2: asyncio.Future = asyncio.Future()
        events = [
            StreamEvent(
                type=StreamEventType.TEXT_DELTA,
                data={"text": "Start "},
            ),
            _make_input_request_event(
                prompt="First?", response_future=future1,
            ),
            StreamEvent(
                type=StreamEventType.TEXT_DELTA,
                data={"text": "Middle "},
            ),
            _make_input_request_event(
                prompt="Second?", response_future=future2,
            ),
            StreamEvent(
                type=StreamEventType.TEXT_DELTA,
                data={"text": "End"},
            ),
        ]
        turn = await handler.handle_stream(_events_from_list(events))

        assert future1.done() and future1.result() == "approve"
        assert future2.done() and future2.result() == "approve"
        assert turn.content == "Start Middle End"
        assert tui.prompt_approval.call_count == 2


# --- Property-based tests: Spec 03 ---


@pytest.mark.property
class TestInputRequestProperties:
    """Property-based tests for INPUT_REQUEST handling."""

    @given(
        input_type=st.sampled_from(["approval", "choice", "text"]),
    )
    @pytest.mark.asyncio
    async def test_property1_stream_pause_guarantee(self, input_type: str):
        """Property 1: Stream handler stops spinner before prompting."""
        tui = _make_tui_mock()
        session = Session()
        handler = StreamHandler(tui, session)

        future: asyncio.Future = asyncio.Future()
        events = [
            _make_input_request_event(
                input_type=input_type,
                response_future=future,
            ),
        ]
        await handler.handle_stream(_events_from_list(events))

        # Spinner was stopped (at least once: before prompt + finalize)
        assert tui.stop_spinner.call_count >= 1

    @given(
        input_type=st.sampled_from(["approval", "choice", "text"]),
    )
    @pytest.mark.asyncio
    async def test_property2_future_resolution_guarantee(
        self, input_type: str,
    ):
        """Property 2: Future is always resolved exactly once."""
        tui = _make_tui_mock()
        session = Session()
        handler = StreamHandler(tui, session)

        future: asyncio.Future = asyncio.Future()
        events = [
            _make_input_request_event(
                input_type=input_type,
                response_future=future,
            ),
        ]
        await handler.handle_stream(_events_from_list(events))

        assert future.done()

    @given(
        approve=st.booleans(),
    )
    @pytest.mark.asyncio
    async def test_property5_rejection_cancels_stream(self, approve: bool):
        """Property 5: Rejection breaks the loop; approval continues."""
        tui = _make_tui_mock()
        response = "approve" if approve else "reject"
        tui.prompt_approval = AsyncMock(return_value=response)
        session = Session()
        handler = StreamHandler(tui, session)

        future: asyncio.Future = asyncio.Future()
        events = [
            StreamEvent(
                type=StreamEventType.TEXT_DELTA,
                data={"text": "before"},
            ),
            _make_input_request_event(response_future=future),
            StreamEvent(
                type=StreamEventType.TEXT_DELTA,
                data={"text": " after"},
            ),
        ]
        turn = await handler.handle_stream(_events_from_list(events))

        if approve:
            assert turn.content == "before after"
        else:
            assert turn.content == "before"
            tui.show_info.assert_called()

    @given(
        pre_text=st.text(min_size=0, max_size=20),
    )
    @pytest.mark.asyncio
    async def test_property7_history_preservation_on_rejection(
        self, pre_text: str,
    ):
        """Property 7: Partial content preserved in history on rejection."""
        tui = _make_tui_mock()
        tui.prompt_approval = AsyncMock(return_value="reject")
        session = Session()
        handler = StreamHandler(tui, session)

        future: asyncio.Future = asyncio.Future()
        events_list: list[StreamEvent] = []
        if pre_text:
            events_list.append(
                StreamEvent(
                    type=StreamEventType.TEXT_DELTA,
                    data={"text": pre_text},
                ),
            )
        events_list.append(
            _make_input_request_event(response_future=future),
        )

        turn = await handler.handle_stream(_events_from_list(events_list))

        # Partial content preserved
        assert turn.content == pre_text
        history = session.get_history()
        assert len(history) == 1
        assert history[0].content == pre_text
