from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from agent_repl.types import MessageContext, SpawnConfig

if TYPE_CHECKING:
    from agent_repl.types import AgentPlugin

logger = logging.getLogger(__name__)


class SessionSpawner:
    """Spawns independent agent sessions with clean context."""

    def __init__(self, agent_factory: Callable[..., AgentPlugin]) -> None:
        self._agent_factory = agent_factory

    async def spawn(self, config: SpawnConfig) -> None:
        """Run a spawned agent session with optional pre/post hooks.

        1. Execute pre-hook (if provided). On failure: report error, abort, no post-hook.
        2. Create agent and send message. On failure: report error, still run post-hook.
        3. Execute post-hook (if provided). On failure: report error.
        """
        # 1. Pre-hook
        if config.pre_hook is not None:
            try:
                config.pre_hook()
            except Exception as e:
                logger.error("Pre-hook failed, aborting spawned session: %s", e)
                raise

        # 2. Create agent and send message
        agent_failed = False
        try:
            agent = self._agent_factory()
            msg_ctx = MessageContext(message=config.prompt)
            stream = await agent.send_message(msg_ctx)
            # Consume the full response stream
            async for _ in stream:
                pass
        except Exception as e:
            logger.error("Spawned agent session failed: %s", e)
            agent_failed = True

        # 3. Post-hook (always runs if pre-hook succeeded, even if agent failed)
        if config.post_hook is not None:
            try:
                config.post_hook()
            except Exception as e:
                logger.error("Post-hook failed: %s", e)

        if agent_failed:
            raise RuntimeError("Spawned agent session failed")
