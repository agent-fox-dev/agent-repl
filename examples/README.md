# agent_repl Examples

## Echo Agent Demo

Run the interactive REPL with the echo agent (no credentials required):

```bash
uv run python -m examples.demo
```

The echo agent repeats your messages back. Try these commands in the REPL:

- Type any text to send it to the echo agent
- `@somefile.py hello` to include file context
- `/help` to list all commands
- `/greet Alice` to run a custom plugin command
- `/time` to show the current time
- `/stats` to see token usage
- `/quit` to exit

## Claude Agent Demo

Run with the Claude agent (requires `ANTHROPIC_API_KEY`):

```bash
export ANTHROPIC_API_KEY=your-key-here
uv run python -m examples.demo --claude
```

## CLI Invocation

Run a slash command from the shell without entering the REPL:

```bash
uv run python -m examples.demo --version
```

## Session Spawning

Run the spawn demo to see independent agent sessions with hooks:

```bash
uv run python -m examples.spawn_demo
```

In the REPL, use `/spawn Say something` to spawn a background session.

## File Structure

- `echo_agent.py` - Echo agent plugin (implements `AgentPlugin` protocol)
- `demo_plugin.py` - Custom plugin with `/greet` and `/time` commands
- `demo.py` - Main demo application entry point
- `spawn_demo.py` - Session spawning demo

## Creating Custom Plugins

A plugin implements the `Plugin` protocol:

```python
from agent_repl.types import PluginContext, SlashCommand, CommandContext

class MyPlugin:
    name = "my_plugin"
    description = "My custom plugin"

    def get_commands(self) -> list[SlashCommand]:
        return [
            SlashCommand(
                name="mycmd",
                description="My command",
                handler=my_handler,
            ),
        ]

    async def on_load(self, context: PluginContext) -> None:
        pass

    async def on_unload(self) -> None:
        pass

    def get_status_hints(self) -> list[str]:
        return []

async def my_handler(ctx: CommandContext) -> None:
    ctx.tui.show_info("Hello from my plugin!")
```

## Creating Custom Agents

An agent implements the `AgentPlugin` protocol (extends `Plugin`):

```python
from agent_repl.types import MessageContext, StreamEvent, StreamEventType

class MyAgent:
    name = "MyAgent"
    description = "My custom agent"
    default_model = "my-model-1.0"

    # ... Plugin methods ...

    async def send_message(self, context: MessageContext):
        yield StreamEvent(
            type=StreamEventType.TEXT_DELTA,
            data={"text": "Response text here"},
        )

    async def compact_history(self, session) -> str:
        return "Compacted summary"
```
