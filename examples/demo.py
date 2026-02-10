"""Entry-point script for the agent_repl example application.

Usage:
    uv run python examples/demo.py           # Default mode (Claude agent)
    uv run python examples/demo.py --echo    # Echo mode (no API key needed)
"""

import argparse
import sys
from pathlib import Path

# Ensure the project root is on sys.path so that `examples.demo_plugin`
# is importable by the plugin loader.
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from agent_repl import App, Config  # noqa: E402
from agent_repl.constants import DEFAULT_CLAUDE_MODEL  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="agent_repl demo application")
    parser.add_argument(
        "--echo",
        action="store_true",
        help="Use the echo agent instead of the default Claude agent",
    )
    args = parser.parse_args()

    config_kwargs: dict = {
        "app_name": "demo",
        "app_version": "0.1.0",
        "default_model": DEFAULT_CLAUDE_MODEL,
        "plugins": ["examples.demo_plugin"],
    }

    if args.echo:
        from examples.echo_agent import EchoAgent

        config_kwargs["agent_factory"] = lambda cfg: EchoAgent()

    config = Config(**config_kwargs)
    App(config).run()


if __name__ == "__main__":
    main()
