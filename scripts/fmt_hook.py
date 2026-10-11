"""PostToolUse hook for Edit and Write: `ruff format` the Python file just edited.

Formatting only — never `ruff check --fix`: an autofix would delete an import that one edit adds
and the next edit uses. The hook never blocks (exit 0 always). When ruff cannot format the file,
typically a syntax error halfway through a change, it tells Claude so and leaves the file alone.

ruff runs as `python -m ruff` from the interpreter running this script, which is the project's
(the hook is started with `uv run`): the same ruff as `make lint`, with no second `uv run`.
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import IO, Any, cast


def target(hook_input: dict[str, Any]) -> Path | None:
    """The file to format: the edited file, when it is a Python file."""
    tool_input = hook_input.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    file_path = cast("dict[str, object]", tool_input).get("file_path")
    if isinstance(file_path, str) and file_path.endswith(".py"):
        return Path(file_path)
    return None


def main(stdin: IO[str] = sys.stdin) -> int:
    try:
        hook_input: object = json.load(stdin)
    except ValueError:
        return 0
    path = target(cast("dict[str, Any]", hook_input)) if isinstance(hook_input, dict) else None
    if path is None:
        return 0
    ruff = subprocess.run(
        [sys.executable, "-m", "ruff", "format", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if ruff.returncode != 0:
        detail = (ruff.stderr or ruff.stdout).strip().splitlines()
        reason = detail[0] if detail else f"exit {ruff.returncode}"
        context = f"ruff format could not format {path} and left it unchanged: {reason}"
        output = {"hookEventName": "PostToolUse", "additionalContext": context}
        print(json.dumps({"hookSpecificOutput": output}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
