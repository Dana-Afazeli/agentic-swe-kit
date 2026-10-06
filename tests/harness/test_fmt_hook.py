"""The format hook runs `ruff format` on an edited Python file, never an autofix, never blocks."""

import io
import json
from pathlib import Path

import pytest

import fmt_hook


def hook_input(path: Path | str) -> io.StringIO:
    return io.StringIO(json.dumps({"tool_name": "Edit", "tool_input": {"file_path": str(path)}}))


def test_target_is_the_edited_python_file() -> None:
    assert fmt_hook.target({"tool_input": {"file_path": "/r/a.py"}}) == Path("/r/a.py")


@pytest.mark.parametrize(
    "payload",
    [
        {"tool_input": {"file_path": "/r/notes.md"}},
        {"tool_input": {"file_path": "/r/a.pyc"}},
        {"tool_input": {}},
        {"tool_input": {"file_path": 7}},
        {"tool_input": "not a mapping"},
        {},
    ],
)
def test_target_is_none_for_anything_else(payload: dict[str, object]) -> None:
    assert fmt_hook.target(payload) is None


def test_formats_the_file_and_keeps_the_unused_import(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "a.py"
    path.write_text("import os\nx=1\n", "utf-8")

    assert fmt_hook.main(hook_input(path)) == 0

    assert path.read_text("utf-8") == "import os\n\nx = 1\n"
    assert capsys.readouterr().out == ""


def test_leaves_other_files_alone(tmp_path: Path) -> None:
    path = tmp_path / "notes.md"
    path.write_text("x=1\n", "utf-8")

    assert fmt_hook.main(hook_input(path)) == 0
    assert path.read_text("utf-8") == "x=1\n"


def test_a_file_ruff_cannot_format_is_reported_and_does_not_block(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "broken.py"
    path.write_text("def f(:\n", "utf-8")

    assert fmt_hook.main(hook_input(path)) == 0

    assert path.read_text("utf-8") == "def f(:\n"
    output = json.loads(capsys.readouterr().out)
    assert output["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    context = output["hookSpecificOutput"]["additionalContext"]
    assert "broken.py" in context
    assert "Failed to parse" in context  # ruff's own words, so the cause can be fixed


@pytest.mark.parametrize("stdin", ["not json", "[]", ""])
def test_unreadable_input_does_not_block(stdin: str) -> None:
    assert fmt_hook.main(io.StringIO(stdin)) == 0
