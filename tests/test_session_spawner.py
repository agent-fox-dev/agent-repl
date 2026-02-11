"""Tests for session_spawner module.

Covers Requirements 12.1-12.6, 12.E1-12.E3.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_repl.session_spawner import SessionSpawner
from agent_repl.types import SpawnConfig, StreamEvent, StreamEventType


async def _empty_stream() -> AsyncIterator[StreamEvent]:
    return
    yield  # Make it an async generator


async def _text_stream(text: str) -> AsyncIterator[StreamEvent]:
    yield StreamEvent(type=StreamEventType.TEXT_DELTA, data={"text": text})


def _make_mock_agent(stream_fn=None):
    """Create a mock agent that returns a stream."""
    agent = MagicMock()
    agent.name = "TestAgent"
    agent.default_model = "test-model"
    if stream_fn is None:
        stream_fn = _empty_stream
    agent.send_message = AsyncMock(return_value=stream_fn())
    return agent


class TestSuccessfulSpawn:
    """Requirements 12.1, 12.3, 12.4: Successful spawn lifecycle."""

    @pytest.mark.asyncio
    async def test_basic_spawn(self):
        """Agent is created, message sent, stream consumed."""
        agent = _make_mock_agent()
        spawner = SessionSpawner(agent_factory=lambda: agent)
        config = SpawnConfig(prompt="Do something")

        await spawner.spawn(config)

        agent.send_message.assert_called_once()
        msg_ctx = agent.send_message.call_args[0][0]
        assert msg_ctx.message == "Do something"

    @pytest.mark.asyncio
    async def test_pre_hook_called(self):
        """Pre-hook runs before agent session."""
        call_order: list[str] = []

        def pre_hook():
            call_order.append("pre")

        agent = _make_mock_agent()
        original_send = agent.send_message

        async def tracked_send(*args, **kwargs):
            call_order.append("send")
            return await original_send(*args, **kwargs)

        agent.send_message = tracked_send

        spawner = SessionSpawner(agent_factory=lambda: agent)
        config = SpawnConfig(prompt="test", pre_hook=pre_hook)

        await spawner.spawn(config)

        assert call_order == ["pre", "send"]

    @pytest.mark.asyncio
    async def test_post_hook_called(self):
        """Post-hook runs after agent session completes."""
        call_order: list[str] = []

        def post_hook():
            call_order.append("post")

        agent = _make_mock_agent()
        original_send = agent.send_message

        async def tracked_send(*args, **kwargs):
            call_order.append("send")
            return await original_send(*args, **kwargs)

        agent.send_message = tracked_send

        spawner = SessionSpawner(agent_factory=lambda: agent)
        config = SpawnConfig(prompt="test", post_hook=post_hook)

        await spawner.spawn(config)

        assert call_order == ["send", "post"]

    @pytest.mark.asyncio
    async def test_full_lifecycle_order(self):
        """Pre-hook → agent → post-hook in correct order."""
        call_order: list[str] = []

        agent = _make_mock_agent()
        original_send = agent.send_message

        async def tracked_send(*args, **kwargs):
            call_order.append("send")
            return await original_send(*args, **kwargs)

        agent.send_message = tracked_send

        spawner = SessionSpawner(agent_factory=lambda: agent)
        config = SpawnConfig(
            prompt="test",
            pre_hook=lambda: call_order.append("pre"),
            post_hook=lambda: call_order.append("post"),
        )

        await spawner.spawn(config)

        assert call_order == ["pre", "send", "post"]


class TestNoHooks:
    """Requirement 12.1: Spawn works without hooks."""

    @pytest.mark.asyncio
    async def test_spawn_no_hooks(self):
        agent = _make_mock_agent()
        spawner = SessionSpawner(agent_factory=lambda: agent)
        config = SpawnConfig(prompt="no hooks")

        await spawner.spawn(config)

        agent.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_spawn_no_pre_hook(self):
        post_called = False

        def post_hook():
            nonlocal post_called
            post_called = True

        agent = _make_mock_agent()
        spawner = SessionSpawner(agent_factory=lambda: agent)
        config = SpawnConfig(prompt="test", post_hook=post_hook)

        await spawner.spawn(config)

        assert post_called

    @pytest.mark.asyncio
    async def test_spawn_no_post_hook(self):
        pre_called = False

        def pre_hook():
            nonlocal pre_called
            pre_called = True

        agent = _make_mock_agent()
        spawner = SessionSpawner(agent_factory=lambda: agent)
        config = SpawnConfig(prompt="test", pre_hook=pre_hook)

        await spawner.spawn(config)

        assert pre_called


class TestPreHookFailure:
    """Requirement 12.E1: Pre-hook failure aborts session."""

    @pytest.mark.asyncio
    async def test_pre_hook_failure_aborts(self):
        """Pre-hook failure → no agent created, no post-hook."""
        agent = _make_mock_agent()
        post_called = False

        def bad_pre_hook():
            raise ValueError("pre-hook error")

        def post_hook():
            nonlocal post_called
            post_called = True

        spawner = SessionSpawner(agent_factory=lambda: agent)
        config = SpawnConfig(
            prompt="test",
            pre_hook=bad_pre_hook,
            post_hook=post_hook,
        )

        with pytest.raises(ValueError, match="pre-hook error"):
            await spawner.spawn(config)

        agent.send_message.assert_not_called()
        assert post_called is False


class TestAgentFailure:
    """Requirement 12.E3: Agent failure still runs post-hook."""

    @pytest.mark.asyncio
    async def test_agent_failure_runs_post_hook(self):
        """Agent exception → error reported, post-hook still called."""
        agent = MagicMock()
        agent.send_message = AsyncMock(side_effect=RuntimeError("agent crashed"))
        post_called = False

        def post_hook():
            nonlocal post_called
            post_called = True

        spawner = SessionSpawner(agent_factory=lambda: agent)
        config = SpawnConfig(prompt="test", post_hook=post_hook)

        with pytest.raises(RuntimeError, match="Spawned agent session failed"):
            await spawner.spawn(config)

        assert post_called

    @pytest.mark.asyncio
    async def test_agent_failure_no_post_hook(self):
        """Agent exception without post-hook."""
        agent = MagicMock()
        agent.send_message = AsyncMock(side_effect=RuntimeError("agent crashed"))

        spawner = SessionSpawner(agent_factory=lambda: agent)
        config = SpawnConfig(prompt="test")

        with pytest.raises(RuntimeError, match="Spawned agent session failed"):
            await spawner.spawn(config)


class TestPostHookFailure:
    """Requirement 12.E2: Post-hook failure is reported."""

    @pytest.mark.asyncio
    async def test_post_hook_failure_reported(self):
        """Post-hook failure → error logged but doesn't crash."""
        agent = _make_mock_agent()

        def bad_post_hook():
            raise ValueError("post-hook error")

        spawner = SessionSpawner(agent_factory=lambda: agent)
        config = SpawnConfig(prompt="test", post_hook=bad_post_hook)

        # Should not raise (post-hook error is logged, not propagated)
        await spawner.spawn(config)

        agent.send_message.assert_called_once()


class TestEmptyContext:
    """Requirement 12.1: Spawned sessions start with empty context."""

    @pytest.mark.asyncio
    async def test_empty_context(self):
        agent = _make_mock_agent()
        spawner = SessionSpawner(agent_factory=lambda: agent)
        config = SpawnConfig(prompt="do the thing")

        await spawner.spawn(config)

        msg_ctx = agent.send_message.call_args[0][0]
        assert msg_ctx.message == "do the thing"
        assert msg_ctx.file_contexts == []
        assert msg_ctx.history == []


class TestParallelSpawning:
    """Requirement 12.2, 12.6: Multiple concurrent spawns."""

    @pytest.mark.asyncio
    async def test_parallel_spawns(self):
        """Two spawns run concurrently via asyncio tasks."""
        results: list[str] = []

        async def slow_stream(label: str) -> AsyncIterator[StreamEvent]:
            await asyncio.sleep(0.01)
            results.append(label)
            yield StreamEvent(type=StreamEventType.TEXT_DELTA, data={"text": label})

        call_count = 0

        def make_agent():
            nonlocal call_count
            call_count += 1
            agent = MagicMock()
            agent.send_message = AsyncMock(
                return_value=slow_stream(f"agent_{call_count}")
            )
            return agent

        spawner = SessionSpawner(agent_factory=make_agent)

        task1 = asyncio.create_task(
            spawner.spawn(SpawnConfig(prompt="task 1"))
        )
        task2 = asyncio.create_task(
            spawner.spawn(SpawnConfig(prompt="task 2"))
        )

        await asyncio.gather(task1, task2)

        assert len(results) == 2
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_independent_agents(self):
        """Each spawn creates its own agent instance."""
        agents_created: list[MagicMock] = []

        def make_agent():
            agent = _make_mock_agent()
            agents_created.append(agent)
            return agent

        spawner = SessionSpawner(agent_factory=make_agent)

        await spawner.spawn(SpawnConfig(prompt="one"))
        await spawner.spawn(SpawnConfig(prompt="two"))

        assert len(agents_created) == 2
        assert agents_created[0] is not agents_created[1]


class TestStreamConsumption:
    """Verify the full response stream is consumed."""

    @pytest.mark.asyncio
    async def test_stream_fully_consumed(self):
        events_yielded = 0

        async def counting_stream() -> AsyncIterator[StreamEvent]:
            nonlocal events_yielded
            for i in range(3):
                events_yielded += 1
                yield StreamEvent(
                    type=StreamEventType.TEXT_DELTA, data={"text": f"chunk_{i}"}
                )

        agent = MagicMock()
        agent.send_message = AsyncMock(return_value=counting_stream())

        spawner = SessionSpawner(agent_factory=lambda: agent)
        await spawner.spawn(SpawnConfig(prompt="test"))

        assert events_yielded == 3
