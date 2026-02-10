"""Unit and property tests for the stream handler.

Property 3: Empty Stream No-Op
Property 4: Final Render Invocation
Property 7: Stream Event Capture Completeness
Validates: Requirements 1.2, 1.3, 1.4, 1.5, stream_rendering 5.1-5.4
"""

from unittest.mock import MagicMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from agent_repl.session import Session
from agent_repl.stream_handler import handle_stream
from agent_repl.types import StreamEvent, StreamEventType, TokenStatistics


async def _async_iter(events):
    """Convert a list of events to an async iterator."""
    for event in events:
        yield event


class TestStreamHandler:
    @pytest.mark.asyncio
    async def test_text_delta_streamed(self):
        tui = MagicMock()
        tui.finish_stream.return_value = "hello"
        session = Session()
        stats = TokenStatistics()
        events = [StreamEvent(type=StreamEventType.TEXT_DELTA, content="hello")]

        turn = await handle_stream(_async_iter(events), tui, session, stats)

        tui.start_stream.assert_called_once()
        tui.append_stream.assert_called_with("hello")
        tui.finish_stream.assert_called_once()
        assert turn.content == "hello"

    @pytest.mark.asyncio
    async def test_multiple_text_deltas_concatenated(self):
        tui = MagicMock()
        tui.finish_stream.return_value = "hello world"
        session = Session()
        stats = TokenStatistics()
        events = [
            StreamEvent(type=StreamEventType.TEXT_DELTA, content="hello "),
            StreamEvent(type=StreamEventType.TEXT_DELTA, content="world"),
        ]

        turn = await handle_stream(_async_iter(events), tui, session, stats)

        tui.start_stream.assert_called_once()
        assert tui.append_stream.call_count == 2
        tui.append_stream.assert_any_call("hello ")
        tui.append_stream.assert_any_call("world")
        tui.finish_stream.assert_called_once()
        assert turn.content == "hello world"

    @pytest.mark.asyncio
    async def test_tool_result_displayed(self):
        tui = MagicMock()
        session = Session()
        stats = TokenStatistics()
        events = [
            StreamEvent(
                type=StreamEventType.TOOL_RESULT,
                content="result",
                metadata={"tool_id": "t1", "is_error": False, "tool_name": "read"},
            )
        ]

        turn = await handle_stream(_async_iter(events), tui, session, stats)

        tui.display_tool_result.assert_called_once()
        assert len(turn.tool_uses) == 1

    @pytest.mark.asyncio
    async def test_usage_accumulated(self):
        tui = MagicMock()
        session = Session()
        stats = TokenStatistics()
        events = [
            StreamEvent(
                type=StreamEventType.USAGE,
                metadata={"input_tokens": 100, "output_tokens": 50},
            )
        ]

        await handle_stream(_async_iter(events), tui, session, stats)

        assert stats.total_input_tokens == 100
        assert stats.total_output_tokens == 50

    @pytest.mark.asyncio
    async def test_error_displayed(self):
        tui = MagicMock()
        session = Session()
        stats = TokenStatistics()
        events = [StreamEvent(type=StreamEventType.ERROR, content="oops")]

        await handle_stream(_async_iter(events), tui, session, stats)

        tui.display_error.assert_called_with("oops")

    @pytest.mark.asyncio
    async def test_spinner_managed(self):
        tui = MagicMock()
        tui.finish_stream.return_value = "hi"
        session = Session()
        stats = TokenStatistics()
        events = [StreamEvent(type=StreamEventType.TEXT_DELTA, content="hi")]

        await handle_stream(_async_iter(events), tui, session, stats)

        tui.start_spinner.assert_called_once()
        tui.stop_spinner.assert_called()

    @pytest.mark.asyncio
    async def test_turn_added_to_session(self):
        tui = MagicMock()
        tui.finish_stream.return_value = "response"
        session = Session()
        stats = TokenStatistics()
        events = [StreamEvent(type=StreamEventType.TEXT_DELTA, content="response")]

        await handle_stream(_async_iter(events), tui, session, stats)

        history = session.get_history()
        assert len(history) == 1
        assert history[0].role == "assistant"

    @pytest.mark.asyncio
    async def test_empty_stream(self):
        tui = MagicMock()
        session = Session()
        stats = TokenStatistics()

        turn = await handle_stream(_async_iter([]), tui, session, stats)

        assert turn.content == ""
        tui.start_spinner.assert_called_once()
        tui.stop_spinner.assert_called()


class TestProperty3EmptyStreamNoOp:
    """Property 3: For streams with no TEXT_DELTA events, the streaming API
    is never called.

    Feature: stream_rendering, Property 3: Empty Stream No-Op
    """

    @pytest.mark.asyncio
    async def test_no_text_deltas_no_stream_calls(self):
        tui = MagicMock()
        session = Session()
        stats = TokenStatistics()
        events = [
            StreamEvent(
                type=StreamEventType.USAGE,
                metadata={"input_tokens": 10, "output_tokens": 5},
            )
        ]

        await handle_stream(_async_iter(events), tui, session, stats)

        tui.start_stream.assert_not_called()
        tui.append_stream.assert_not_called()
        tui.finish_stream.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_event_list_no_stream_calls(self):
        tui = MagicMock()
        session = Session()
        stats = TokenStatistics()

        await handle_stream(_async_iter([]), tui, session, stats)

        tui.start_stream.assert_not_called()
        tui.append_stream.assert_not_called()
        tui.finish_stream.assert_not_called()


class TestProperty4FinalRenderInvocation:
    """Property 4: For any non-empty sequence of TEXT_DELTA events,
    finish_stream() is called exactly once after the stream ends.

    Feature: stream_rendering, Property 4: Final Render Invocation
    """

    @pytest.mark.asyncio
    async def test_finish_called_once_for_single_delta(self):
        tui = MagicMock()
        tui.finish_stream.return_value = "text"
        session = Session()
        stats = TokenStatistics()
        events = [StreamEvent(type=StreamEventType.TEXT_DELTA, content="text")]

        await handle_stream(_async_iter(events), tui, session, stats)

        tui.finish_stream.assert_called_once()

    @pytest.mark.asyncio
    async def test_finish_called_once_for_many_deltas(self):
        tui = MagicMock()
        tui.finish_stream.return_value = "abcde"
        session = Session()
        stats = TokenStatistics()
        events = [
            StreamEvent(type=StreamEventType.TEXT_DELTA, content=c)
            for c in "abcde"
        ]

        await handle_stream(_async_iter(events), tui, session, stats)

        tui.start_stream.assert_called_once()
        assert tui.append_stream.call_count == 5
        tui.finish_stream.assert_called_once()


# Strategy for generating stream events
_event_strategy = st.builds(
    StreamEvent,
    type=st.sampled_from(list(StreamEventType)),
    content=st.text(min_size=0, max_size=50),
)


class TestProperty7StreamEventCaptureCompleteness:
    """Property 7: All stream events are stored in the session.

    Feature: agent_repl, Property 7: Stream Event Capture Completeness
    """

    @settings(max_examples=100)
    @given(events=st.lists(_event_strategy, min_size=0, max_size=10))
    @pytest.mark.asyncio
    async def test_all_events_result_in_turn(self, events):
        tui = MagicMock()
        tui.finish_stream.return_value = ""
        session = Session()
        stats = TokenStatistics()

        await handle_stream(_async_iter(events), tui, session, stats)

        # The turn is always added to session
        history = session.get_history()
        assert len(history) == 1
        assert history[0].role == "assistant"
