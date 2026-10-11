"""The two logs, `docs/BACKLOG.md` and `docs/FRICTION.md`, are tables that many branches append to.

`.gitattributes` gives both `merge=union`, so git keeps the rows each side added instead of
reporting a conflict. A union merge never reports anything, so what it can leave behind is found
here: a row with the wrong number of cells, the same row twice, and two versions of one row (a row
edited on both sides keeps both). The rules: as many cells as the header, no two equal
rows, no two rows with the same first 120 characters.
"""

import re
import subprocess
from pathlib import Path

import pytest

# The nearest directory above this file that holds the workflow: the repository root, also when
# mutmut runs the tests from its copy under mutants/ (which has no .github/ or docs/).
ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / ".github" / "workflows" / "ci.yml").is_file()
)
LOGS = ("docs/BACKLOG.md", "docs/FRICTION.md")
PREFIX = 120
HEADER = "| date | kind | what happened |\n|---|---|---|\n"


SEPARATOR = re.compile(r"^\|(?:\s*:?-+:?\s*\|)+\s*$")


def cell_count(line: str) -> int:
    """The cells of a row as GitHub renders it: split at every `|` not written `\\|`."""
    body = re.sub(r"(?<!\\)\|\s*$", "", line.strip().removeprefix("|"))
    return len(re.split(r"(?<!\\)\|", body))


def table_problems(text: str) -> list[str]:
    """What is wrong with the pipe tables of one Markdown file, each as one line of text.

    A table is a run of lines that start with `|`: its header, its separator, its rows. The rows
    of all the tables of the file are compared with each other; headers and separators are not."""
    problems: list[str] = []
    rows: list[tuple[int, str]] = []
    header_cells = 0
    position = 0  # the line's place in its table: 1 is the header, 2 the separator
    for number, line in enumerate(text.splitlines(), 1):
        if not line.startswith("|"):
            position = 0
            continue
        position += 1
        if position == 1:
            header_cells = cell_count(line)
        elif position != 2 or not SEPARATOR.match(line):
            rows.append((number, line.strip()))
            if (count := cell_count(line)) != header_cells:
                problems.append(f"line {number}: {count} cells, the header has {header_cells}")

    equal: dict[str, int] = {}
    starts: dict[str, int] = {}
    for number, row in rows:
        if row in equal:
            problems.append(f"lines {equal[row]} and {number}: the same row")
            continue
        equal[row] = number
        if row[:PREFIX] in starts:
            problems.append(
                f"lines {starts[row[:PREFIX]]} and {number}: the same first {PREFIX} characters"
            )
        else:
            starts[row[:PREFIX]] = number
    return problems


def a_row(label: str, tail: str = "") -> str:
    return f"| 2026-10-10 | wrong | {label}{tail} |\n"


# --- the checker, on tables made for it ---------------------------------------------------------


def test_a_table_that_follows_its_header_has_no_problem() -> None:
    text = HEADER + a_row("one") + a_row("two")

    assert table_problems(text) == []


def test_a_row_with_too_few_cells_is_named_with_its_line() -> None:
    text = HEADER + a_row("one") + "| 2026-10-10 | wrong |\n"

    problems = table_problems(text)

    assert len(problems) == 1
    assert "line 4" in problems[0]
    assert "2 cells" in problems[0]
    assert "3" in problems[0]


def test_a_pipe_inside_backticks_is_a_cell_border_as_it_is_when_rendered() -> None:
    """GitHub's tables split a row at every `|` that is not written `\\|`, code span or not."""
    broken = HEADER + a_row("the `Edit|Write` rule")
    fixed = HEADER + a_row(r"the `Edit\|Write` rule")

    assert len(table_problems(broken)) == 1
    assert table_problems(fixed) == []


def test_two_equal_rows_are_one_problem_that_names_both_lines() -> None:
    text = HEADER + a_row("one") + a_row("two") + a_row("one")

    problems = table_problems(text)

    assert len(problems) == 1
    assert "lines 3 and 5" in problems[0]
    assert "same row" in problems[0]


def test_two_rows_that_share_their_first_120_characters_are_named() -> None:
    long = "x" * 140
    text = HEADER + a_row(long, " first") + a_row(long, " second")

    problems = table_problems(text)

    assert len(problems) == 1
    assert "lines 3 and 4" in problems[0]
    assert "first 120" in problems[0]


def test_rows_that_differ_inside_the_first_120_characters_are_not_the_same_row() -> None:
    text = HEADER + a_row("a" + "x" * 140) + a_row("b" + "x" * 140)

    assert table_problems(text) == []


def test_the_headers_and_separators_of_several_tables_are_not_compared() -> None:
    text = HEADER + a_row("one") + "\nSome prose.\n\n" + HEADER + a_row("two")

    assert table_problems(text) == []


def test_rows_are_compared_across_the_tables_of_one_file() -> None:
    text = HEADER + a_row("one") + "\nSome prose.\n\n" + HEADER + a_row("one")

    problems = table_problems(text)

    assert len(problems) == 1
    assert "same row" in problems[0]


# --- the two files ------------------------------------------------------------------------------


@pytest.mark.parametrize("name", LOGS)
def test_the_tables_of_the_log_have_no_problem(name: str) -> None:
    text = (ROOT / name).read_text("utf-8")

    assert re.search(r"^\|", text, flags=re.MULTILINE), "the file has no table"
    assert table_problems(text) == []


def test_gitattributes_gives_both_logs_the_union_merge() -> None:
    lines = (ROOT / ".gitattributes").read_text("utf-8").splitlines()

    assert "docs/BACKLOG.md merge=union" in lines
    assert "docs/FRICTION.md merge=union" in lines


# --- the merge, in a temporary repository -------------------------------------------------------


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """git in `repo`, with no user or system configuration, bounded."""
    return subprocess.run(
        [
            *("git", "-C", str(repo)),
            *("-c", "user.name=t", "-c", "user.email=t@example.invalid"),
            *("-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null"),
            *args,
        ],
        capture_output=True,
        text=True,
        check=check,
        timeout=60,
        env={
            "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_NOSYSTEM": "1",
        },
    )


def repo_with_a_log(path: Path, *, attributes: bool) -> Path:
    """A repository on `main` that holds `docs/FRICTION.md` with one row, and, if asked, the
    repository's own `.gitattributes`."""
    path.mkdir()
    git(path, "init", "-q", "-b", "main")
    (path / "docs").mkdir()
    (path / "docs" / "FRICTION.md").write_text(HEADER + a_row("base"), "utf-8")
    if attributes:
        (path / ".gitattributes").write_text((ROOT / ".gitattributes").read_text("utf-8"), "utf-8")
    git(path, "add", "-A")
    git(path, "commit", "-qm", "base")
    return path


def append_on_a_branch(repo: Path, branch: str, row: str) -> None:
    git(repo, "switch", "-q", "-c", branch, "main")
    with (repo / "docs" / "FRICTION.md").open("a", encoding="utf-8") as log:
        log.write(row)
    git(repo, "commit", "-qam", f"add {branch}")


def test_two_branches_that_each_append_a_row_merge_with_both_rows(tmp_path: Path) -> None:
    repo = repo_with_a_log(tmp_path / "repo", attributes=True)
    append_on_a_branch(repo, "left", a_row("from the left"))
    append_on_a_branch(repo, "right", a_row("from the right"))

    merged = git(repo, "merge", "-q", "left", check=False)

    assert merged.returncode == 0, merged.stdout + merged.stderr
    text = (repo / "docs" / "FRICTION.md").read_text("utf-8")
    assert "from the left" in text
    assert "from the right" in text
    assert table_problems(text) == []


def test_without_the_attribute_the_same_two_appends_conflict(tmp_path: Path) -> None:
    """The control: the merge above is clean because of `.gitattributes`, not by luck."""
    repo = repo_with_a_log(tmp_path / "repo", attributes=False)
    append_on_a_branch(repo, "left", a_row("from the left"))
    append_on_a_branch(repo, "right", a_row("from the right"))

    merged = git(repo, "merge", "-q", "left", check=False)

    assert merged.returncode == 1
    assert "CONFLICT" in merged.stdout


def test_a_row_edited_on_both_sides_merges_clean_and_the_table_check_names_it(
    tmp_path: Path,
) -> None:
    """What a union merge leaves behind: both versions of the row. The merge says nothing; the
    check finds two rows that start the same."""
    repo = repo_with_a_log(tmp_path / "repo", attributes=True)
    long = "x" * 140
    log = repo / "docs" / "FRICTION.md"
    log.write_text(HEADER + a_row(long, " draft"), "utf-8")
    git(repo, "commit", "-qam", "a long row")
    for branch, ending in (("left", " left's ending"), ("right", " right's ending")):
        git(repo, "switch", "-q", "-c", branch, "main")
        log.write_text(HEADER + a_row(long, ending), "utf-8")
        git(repo, "commit", "-qam", branch)

    merged = git(repo, "merge", "-q", "left", check=False)

    assert merged.returncode == 0, merged.stdout + merged.stderr
    problems = table_problems(log.read_text("utf-8"))
    assert len(problems) == 1
    assert "first 120" in problems[0]
