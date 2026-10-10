"""The implementer skill's `pr.py`: the page the maintainer reads, and the proofs comment."""

import json
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from subprocess import CompletedProcess

import pytest

import pr
from conftest import REPO_ROOT

ROOT = REPO_ROOT
HEAD = "b" * 40
ABOVE = [
    "Brief: [`docs/briefs/901-slug.md`](docs/briefs/901-slug.md)",
    "",
    "## What this is, and where it sits",
    "A function that joins the words of a message.",
    "",
    "## Next steps for the maintainer",
    "- [ ] Read the diff and merge. That lets brief 902 start.",
    "",
    "## Decisions for the maintainer",
    "None.",
    "",
    "## Not proven",
    "- A message of more than 4,096 characters: no test sends one.",
    "",
]
BELOW = [
    pr.REFERENCE_LINE,
    "",
    "## File by file",
    "- `src/pkg/core/words.py`: the function.",
    "## Where this differs from the brief",
    "Nowhere.",
    "## The review record",
    "- code-review · round 1 · FINDINGS 3: finding 3 was rejected with evidence.",
    "## Out of scope, noticed",
    "None.",
    "## Docs made stale, and fixed",
    "None.",
    "## Gate files changed",
    "None.",
    "## Checks weakened",
    "None.",
]


def page(above: list[str] | None = None, below: list[str] | None = None) -> str:
    return "\n".join([*(ABOVE if above is None else above), *(BELOW if below is None else below)])


def padded(lines: int) -> list[str]:
    """The four parts in exactly `lines` lines above the reference line."""
    return [*ABOVE, *(f"- step {number}" for number in range(lines - len(ABOVE)))]


class Shell:
    """git and gh as `pr.py` calls them: answers from a table, and keeps every call."""

    def __init__(self, *, pr_head: str = HEAD, local_head: str = HEAD, earlier: str = "") -> None:
        self.calls: list[list[str]] = []
        self.pr_head = pr_head
        self.local_head = local_head
        self.earlier = earlier  # what the lookup of an earlier proofs comment prints
        self.posted: list[str] = []  # the text of each file sent as a description or a comment

    def __call__(self, args: list[str]) -> CompletedProcess[str]:
        self.calls.append(args)
        out = ""
        if args[:3] == ["git", "rev-parse", "HEAD"]:
            out = self.local_head + "\n"
        elif args[:3] == ["gh", "pr", "view"]:
            out = self.pr_head + "\n"
        elif args[:3] == ["gh", "api", "user"]:
            out = "me\n"  # the account `gh` is logged in as
        elif args[:2] == ["gh", "api"] and "--paginate" in args:
            out = self.earlier
        for arg in args:
            if arg.startswith("body=@"):
                self.posted.append(Path(arg.removeprefix("body=@")).read_text("utf-8"))
        if "--body-file" in args:
            self.posted.append(Path(args[args.index("--body-file") + 1]).read_text("utf-8"))
        return CompletedProcess(args, 0, stdout=out, stderr="")

    def writes(self) -> list[list[str]]:
        reads = (["git", "rev-parse"], ["gh", "pr", "view"], ["gh", "api", "user"])
        return [
            call
            for call in self.calls
            if not any(call[: len(read)] == read for read in reads) and "--paginate" not in call
        ]


Env = dict[str, str]
SESSION = {"CLAUDE_CODE_SESSION_ID": "session-one"}


@pytest.fixture
def written(tmp_path: Path) -> Callable[[str], Path]:
    def write(text: str) -> Path:
        path = tmp_path / "page-in.md"
        path.write_text(text, "utf-8")
        return path

    return write


# --- criterion 4: the page ------------------------------------------------------------------------


def test_81_lines_above_the_reference_line_are_refused_and_the_message_says_81(
    written: Callable[[str], Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    shell = Shell()
    file = written(page(above=padded(81)))

    code = pr.main(["page", "15", str(file), "--dry-run", str(tmp_path / "out")], shell, SESSION)

    assert code == 1
    assert "81 lines above the reference line; the page is at most 80" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()
    assert shell.writes() == []


def test_80_lines_above_the_reference_line_are_a_page(
    written: Callable[[str], Path], tmp_path: Path
) -> None:
    file = written(page(above=padded(80)))

    assert pr.main(["page", "15", str(file), "--dry-run", str(tmp_path / "out")], Shell(), {}) == 0


def test_a_missing_part_is_refused_by_name(
    written: Callable[[str], Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    without = [line for line in ABOVE if line != "## Not proven"]
    file = written(page(above=without))

    code = pr.main(["page", "15", str(file), "--dry-run", str(tmp_path / "out")], Shell(), {})

    assert code == 1
    assert 'the part "## Not proven" is missing' in capsys.readouterr().err


def test_a_missing_reference_part_is_refused_by_name(
    written: Callable[[str], Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    without = [line for line in BELOW if line != "## Checks weakened"]
    file = written(page(below=without))

    code = pr.main(["page", "15", str(file), "--dry-run", str(tmp_path / "out")], Shell(), {})

    assert code == 1
    assert 'the part "## Checks weakened" is missing' in capsys.readouterr().err


def test_a_page_with_no_reference_line_is_refused(
    written: Callable[[str], Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    file = written(page(below=BELOW[1:]))

    code = pr.main(["page", "15", str(file), "--dry-run", str(tmp_path / "out")], Shell(), {})

    assert code == 1
    assert f'the line "{pr.REFERENCE_LINE}" is missing' in capsys.readouterr().err


def test_parts_out_of_order_are_refused(
    written: Callable[[str], Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    swapped = [
        *ABOVE[:2],
        *ABOVE[5:8],
        *ABOVE[2:5],
        *ABOVE[8:],
    ]  # the maintainer's steps before "What"
    file = written(page(above=swapped))

    code = pr.main(["page", "15", str(file), "--dry-run", str(tmp_path / "out")], Shell(), {})

    assert code == 1
    err = capsys.readouterr().err
    assert (
        '"## Next steps for the maintainer" comes before "## What this is, and where it sits"'
        in err
    )


def test_a_part_of_the_page_below_the_reference_line_is_missing_above_it(
    written: Callable[[str], Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    without = [line for line in ABOVE if line != "## Not proven"]
    file = written(page(above=without, below=[*BELOW, "## Not proven", "x"]))

    code = pr.main(["page", "15", str(file), "--dry-run", str(tmp_path / "out")], Shell(), {})

    assert code == 1
    assert 'the part "## Not proven" is missing above the reference line' in capsys.readouterr().err


@pytest.mark.parametrize(
    "line",
    [
        "This replaces the first draft, which had rule lists.",
        "- [ ] Decide on the cancel gap (see finding 3).",
        "As you said, the template moves.",
        "Rewritten after your correction of round 2.",
        "The walkthrough is updated per feedback.",
        "The bot keeps the first draft of a message until it is sent.",
        "A failed write restores the previous version of the file.",
    ],
)
def test_what_a_sentence_says_is_the_reviewers_to_judge_and_the_script_lets_it_through(
    line: str, written: Callable[[str], Path], tmp_path: Path
) -> None:
    """Whether a page reads cold is the conformance reviewer's to judge. No list of phrases can
    tell a label of the session from a sentence about the product, so the script keeps none: it
    checks the page's shape and leaves its words alone."""
    file = written(page(above=[*ABOVE[:4], line, *ABOVE[4:]]))

    assert pr.main(["page", "15", str(file), "--dry-run", str(tmp_path / "out")], Shell(), {}) == 0
    assert (tmp_path / "out" / "page.md").read_text("utf-8") == file.read_text("utf-8")


def test_every_problem_of_a_page_is_reported_at_once(
    written: Callable[[str], Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    above = [line for line in padded(81) if line != "## Decisions for the maintainer"]
    file = written(page(above=[*above, "<!-- a comment of the template -->"]))

    code = pr.main(["page", "15", str(file), "--dry-run", str(tmp_path / "out")], Shell(), {})

    assert code == 1
    err = capsys.readouterr().err
    assert "81 lines above the reference line" in err
    assert 'the part "## Decisions for the maintainer" is missing' in err
    assert "line 81: a comment is left" in err


def test_a_right_page_with_dry_run_lands_in_the_folder_and_not_on_github(
    written: Callable[[str], Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    shell = Shell()
    file = written(page())
    out = tmp_path / "out"

    assert pr.main(["page", "15", str(file), "--dry-run", str(out)], shell, {}) == 0

    assert (out / "page.md").read_text("utf-8") == page()
    assert shell.calls == []
    assert str(out / "page.md") in capsys.readouterr().out


def test_a_right_page_becomes_the_description_of_the_pull_request(
    written: Callable[[str], Path],
) -> None:
    shell = Shell()
    file = written(page())

    assert pr.main(["page", "15", str(file)], shell, {}) == 0

    assert shell.calls == [["gh", "pr", "edit", "15", "--body-file", str(file)]]
    assert shell.posted == [page()]


def test_a_page_that_github_refuses_fails(
    written: Callable[[str], Path], capsys: pytest.CaptureFixture[str]
) -> None:
    def refuse(args: list[str]) -> CompletedProcess[str]:
        return CompletedProcess(args, 1, stdout="", stderr="HTTP 403")

    assert pr.main(["page", "15", str(written(page()))], refuse, {}) == 1
    assert "HTTP 403" in capsys.readouterr().err


# A page is its eleven parts, each once, each a heading of its own, each with something written
# under it. A file that only holds the headings as lines somewhere is not one.

HEADINGS = [*pr.PARTS, pr.REFERENCE_LINE, *pr.REFERENCE_PARTS]


def test_headings_with_nothing_under_them_are_refused() -> None:
    problems = pr.page_problems("\n".join(HEADINGS))

    assert [each for each in problems if "is empty" in each] == [
        f'the part "{part}" is empty' for part in (*pr.PARTS, *pr.REFERENCE_PARTS)
    ]


def test_a_part_with_only_an_empty_checkbox_is_empty() -> None:
    above = [
        *ABOVE[:6],
        "- [ ]",
        *ABOVE[7:],
    ]  # "Next steps for the maintainer" with its step taken out

    assert pr.page_problems(page(above=above)) == [
        'the part "## Next steps for the maintainer" is empty'
    ]


def test_a_comment_left_from_the_template_is_refused_and_does_not_count_as_writing() -> None:
    above = [*ABOVE[:3], "<!-- For a reader who has never", "     seen this. -->", *ABOVE[4:]]

    problems = pr.page_problems(page(above=above))

    assert len(problems) == 2
    assert problems[0] == 'the part "## What this is, and where it sits" is empty'
    assert problems[1].startswith("line 4: a comment is left: <!-- For a reader who has never\n")


def test_headings_inside_a_comment_are_not_the_parts() -> None:
    text = "\n".join(["<!--", *pr.PARTS, "-->", pr.REFERENCE_LINE, *BELOW[1:]])

    problems = pr.page_problems(text)

    for part in pr.PARTS:
        assert f'the part "{part}" is missing above the reference line' in problems


def test_headings_inside_a_code_fence_are_not_the_parts() -> None:
    text = "\n".join(["```", *ABOVE, "```", *BELOW])

    problems = pr.page_problems(text)

    for part in pr.PARTS:
        assert f'the part "{part}" is missing above the reference line' in problems


def test_a_part_that_appears_twice_is_refused() -> None:
    again = [*ABOVE, "## What this is, and where it sits", "Said once more."]

    assert 'the part "## What this is, and where it sits" appears 2 times' in pr.page_problems(
        page(above=again)
    )


def test_a_reference_line_that_appears_twice_is_refused() -> None:
    text = page(below=[*BELOW, pr.REFERENCE_LINE])

    assert f'the line "{pr.REFERENCE_LINE}" appears 2 times' in pr.page_problems(text)


# The invariant of the scan: it sees the page as GitHub shows it. A comment starts only outside
# code; a fence closes only on a line of its own character, at least as long, with nothing after
# it; and a comment or a fence that never closes is reported with the line it opens on, since
# GitHub hides or swallows everything after it and every other message would be a consequence.

T3, T4 = "`" * 3, "`" * 4


@pytest.mark.parametrize(
    "lines",
    [
        ["The script refuses a page that still holds `<!--`."],
        ["Use `a <!-- b` in the template."],
        ["A template comment (`<!-- like this -->`) is refused."],
        ["Two backticks can hold one: ``a ` <!-- b``."],
        [T4, T3, "## Not proven", T4],  # a longer fence around a shorter one
        [f"{T3}make check{T3} is green."],  # inline code that opens a line
        ["~~~", T3, "## Not proven", "~~~"],
        [T3, "~~~", "## Not proven", T3],
        [T3 + "python", "mark = '<!--'", T3],
        ["- a step:", "  " + T3, "  make check", "  " + T3],  # a fence inside a list item
        [T3, "make check", T3 + "   "],  # spaces after the closing run
    ],
)
def test_code_on_a_page_is_read_as_github_shows_it(lines: list[str]) -> None:
    assert pr.page_problems(page(above=[*ABOVE[:4], *lines, *ABOVE[4:]])) == []


@pytest.mark.parametrize(
    ("lines", "problem"),
    [
        (["<!-- left open"], "line 5: a comment opens here and never closes"),
        (["Text, then <!-- left open", "more"], "line 5: a comment opens here and never closes"),
        ([T3, "make check"], "line 5: a code fence opens here and never closes"),
        ([T4, "make check", T3], "line 5: a code fence opens here and never closes"),
        (["~~~", "make check", T3], "line 5: a code fence opens here and never closes"),
        ([T3, "make check", T3 + " and more"], "line 5: a code fence opens here and never closes"),
    ],
)
def test_what_never_closes_is_reported_with_the_line_it_opens_on(
    lines: list[str], problem: str
) -> None:
    problems = pr.page_problems(page(above=[*ABOVE[:4], *lines, *ABOVE[4:]]))

    assert len(problems) == 1
    assert problems[0].startswith(problem)


def test_a_comment_mark_in_a_fence_or_in_inline_code_is_not_a_comment_left() -> None:
    lines = [T3, "<!-- shown as code -->", T3, "And `<!-- this too -->`."]

    assert pr.page_problems(page(above=[*ABOVE[:4], *lines, *ABOVE[4:]])) == []


def test_a_real_comment_beside_inline_code_is_still_a_comment_left() -> None:
    lines = ["The mark `<!--` opens one. <!-- like this one -->"]

    problems = pr.page_problems(page(above=[*ABOVE[:4], *lines, *ABOVE[4:]]))

    assert len(problems) == 1
    assert problems[0].startswith("line 5: a comment is left")


@pytest.mark.parametrize("separator", ["\u2028", "\u2029", "\x0c", "\x0b", "\x85", "\x1e"])
def test_a_line_ends_where_github_ends_it(separator: str) -> None:
    """GitHub ends a line at `\\n`, `\\r` or `\\r\\n` and nowhere else; a heading that is not at the
    start of such a line is not a heading, and the page is read as GitHub shows it."""
    one_line = f"- A message of more than 4,096 characters.{separator}## Not proven{separator}Text."
    above = [*ABOVE[:11], one_line, *ABOVE[13:]]  # "## Not proven" and its text, on one line

    problems = pr.page_problems(page(above=above))

    assert 'the part "## Not proven" is missing above the reference line' in problems


@pytest.mark.parametrize("body", ["-", "*", "+ [ ]", "1. [ ]", "1) [x]", "> ", "> - [ ]"])
def test_a_part_with_only_an_empty_list_marker_or_quote_is_empty(body: str) -> None:
    above = [*ABOVE[:12], body, *ABOVE[13:]]  # "## Not proven" with nothing but a marker under it

    assert pr.page_problems(page(above=above)) == ['the part "## Not proven" is empty']


@pytest.mark.parametrize("name", ["page.md", "proofs.md"])
def test_a_dry_runs_output_among_the_proofs_is_refused_by_name(
    name: str, proofs: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`page --dry-run` cannot know which folder holds the proofs; `proofs` knows what a dry run
    writes, and would otherwise post the page as a proof."""
    (proofs / name).write_text("written by a dry run\n", "utf-8")

    code = pr.main(
        ["proofs", "15", str(proofs), "--dry-run", str(tmp_path / "out")], Shell(), SESSION
    )

    assert code == 1
    assert f"{name} is what a dry run writes" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


# Anything that goes wrong while reading a file or running a command ends in one line and exit
# code 1, never in a traceback: the caller is a session that reads the last line.


def test_a_page_that_is_not_utf8_is_refused_by_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    file = tmp_path / "latin.md"
    file.write_bytes(b"caf\xe9\n")

    assert pr.main(["page", "15", str(file)], Shell(), {}) == 1
    assert f"{file} is not UTF-8 text" in capsys.readouterr().err


def test_a_command_that_does_not_answer_is_reported_and_says_what_is_not_known(
    written: Callable[[str], Path], capsys: pytest.CaptureFixture[str]
) -> None:
    def hangs(args: list[str]) -> CompletedProcess[str]:
        raise subprocess.TimeoutExpired(args, 120)

    assert pr.main(["page", "15", str(written(page()))], hangs, {}) == 1
    err = capsys.readouterr().err
    assert "`gh pr edit 15` did not answer within 120 s" in err
    assert "whether it took effect is not known" in err


def test_a_command_that_cannot_be_started_is_reported(
    written: Callable[[str], Path], capsys: pytest.CaptureFixture[str]
) -> None:
    def missing(args: list[str]) -> CompletedProcess[str]:
        raise FileNotFoundError(2, "No such file or directory", args[0])

    assert pr.main(["page", "15", str(written(page()))], missing, {}) == 1
    assert "`gh pr edit 15` could not be started" in capsys.readouterr().err


def test_a_dry_run_folder_that_cannot_be_made_is_reported(
    written: Callable[[str], Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    in_the_way = tmp_path / "a-file"
    in_the_way.write_text("x", "utf-8")

    code = pr.main(["page", "15", str(written(page())), "--dry-run", str(in_the_way)], Shell(), {})

    assert code == 1
    assert str(in_the_way) in capsys.readouterr().err


def test_a_page_file_that_does_not_exist_is_refused(capsys: pytest.CaptureFixture[str]) -> None:
    assert pr.main(["page", "15", "/nowhere/page.md"], Shell(), {}) == 1
    assert "/nowhere/page.md" in capsys.readouterr().err


# --- criterion 5: the proofs comment --------------------------------------------------------------

RED = "FAILED tests/test_words.py::test_join - AssertionError\nexit code: 1\n"
GREEN = "1233 passed in 43.10s\n[…]\nexit code: 0\n"


@pytest.fixture
def proofs(tmp_path: Path) -> Path:
    folder = tmp_path / "proofs"
    folder.mkdir()
    (folder / "red.txt").write_text(RED, "utf-8")
    (folder / "green.txt").write_text(GREEN, "utf-8")
    return folder


def block(name: str, text: str, fence: str = "````") -> str:
    return (
        f"<details><summary><code>{name}</code></summary>\n\n{fence}\n{text}{fence}\n</details>\n"
    )


def test_proofs_with_dry_run_are_one_file_marker_first_then_a_block_per_file(
    proofs: Path, tmp_path: Path
) -> None:
    shell = Shell()
    out = tmp_path / "out"

    assert pr.main(["proofs", "15", str(proofs), "--dry-run", str(out)], shell, SESSION) == 0

    text = (out / "proofs.md").read_text("utf-8")
    assert [path.name for path in out.iterdir()] == ["proofs.md"]
    assert text.splitlines()[0] == f"<!-- proofs head={HEAD} sessions=session-one -->"
    assert text.count("<details>") == 2
    # the text of each file is there unchanged, in the order of the file names
    assert block("green.txt", GREEN) in text
    assert block("red.txt", RED) in text
    assert text.index("green.txt") < text.index("red.txt")
    assert shell.writes() == []


def test_a_second_run_under_another_session_keeps_both_ids_in_the_marker(
    proofs: Path, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    args = ["proofs", "15", str(proofs), "--dry-run", str(out)]

    assert pr.main(args, Shell(), SESSION) == 0
    assert pr.main(args, Shell(), {"CLAUDE_CODE_SESSION_ID": "session-two"}) == 0
    assert pr.main(args, Shell(), {"CLAUDE_CODE_SESSION_ID": "session-two"}) == 0

    first = (out / "proofs.md").read_text("utf-8").splitlines()[0]
    assert first == f"<!-- proofs head={HEAD} sessions=session-one,session-two -->"


def test_a_proof_that_holds_a_fence_gets_a_longer_one(proofs: Path, tmp_path: Path) -> None:
    fenced = "the report:\n`````\ninside\n`````\n"
    (proofs / "report.md").write_text(fenced, "utf-8")
    out = tmp_path / "out"

    assert pr.main(["proofs", "15", str(proofs), "--dry-run", str(out)], Shell(), SESSION) == 0

    assert block("report.md", fenced, fence="``````") in (out / "proofs.md").read_text("utf-8")


def test_a_proof_whose_last_line_has_no_newline_still_closes_its_fence_on_a_line_of_its_own(
    proofs: Path, tmp_path: Path
) -> None:
    (proofs / "red.txt").write_text("exit code: 1", "utf-8")
    out = tmp_path / "out"

    assert pr.main(["proofs", "15", str(proofs), "--dry-run", str(out)], Shell(), SESSION) == 0

    assert "````\nexit code: 1\n````\n" in (out / "proofs.md").read_text("utf-8")


def test_proofs_without_a_session_id_are_refused(
    proofs: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = pr.main(["proofs", "15", str(proofs), "--dry-run", str(tmp_path / "out")], Shell(), {})

    assert code == 1
    assert "CLAUDE_CODE_SESSION_ID" in capsys.readouterr().err


def test_an_empty_proofs_folder_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()

    code = pr.main(["proofs", "15", str(empty), "--dry-run", str(tmp_path / "o")], Shell(), SESSION)

    assert code == 1
    assert "no files" in capsys.readouterr().err


# Every entry of the proofs folder is in the comment as text, or the call is refused and names
# it. Nothing is left out without a word, nothing is garbled, and the script's own output is
# never one of its inputs.


def test_a_folder_inside_the_proofs_folder_is_refused_by_name(
    proofs: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (proofs / "round-2").mkdir()
    (proofs / "round-2" / "green.txt").write_text("exit code: 0\n", "utf-8")

    code = pr.main(
        ["proofs", "15", str(proofs), "--dry-run", str(tmp_path / "out")], Shell(), SESSION
    )

    assert code == 1
    assert "round-2 is a folder" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


def test_a_proof_that_is_not_text_is_refused_by_name(
    proofs: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (proofs / "shot.png").write_bytes(bytes(range(256)))

    code = pr.main(
        ["proofs", "15", str(proofs), "--dry-run", str(tmp_path / "out")], Shell(), SESSION
    )

    assert code == 1
    assert "shot.png is not UTF-8 text" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("inside", ["", "out"])
def test_a_dry_run_into_the_proofs_folder_is_refused(
    inside: str, proofs: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Written there, `proofs.md` would be a proof of the next run."""
    target = proofs / inside if inside else proofs

    assert pr.main(["proofs", "15", str(proofs), "--dry-run", str(target)], Shell(), SESSION) == 1
    assert "is inside the folder of proofs" in capsys.readouterr().err
    assert sorted(path.name for path in proofs.iterdir()) == ["green.txt", "red.txt"]


def test_a_file_name_is_shown_as_text_not_read_as_markup(proofs: Path, tmp_path: Path) -> None:
    (proofs / "<b>&x.txt").write_text("named like markup\n", "utf-8")
    out = tmp_path / "out"

    assert pr.main(["proofs", "15", str(proofs), "--dry-run", str(out)], Shell(), SESSION) == 0

    text = (out / "proofs.md").read_text("utf-8")
    assert "<summary><code>&lt;b&gt;&amp;x.txt</code></summary>" in text
    assert "<b>&x.txt" not in text


def test_a_hidden_file_is_no_proof(proofs: Path, tmp_path: Path) -> None:
    """Finder leaves `.DS_Store` in a folder it has shown; that is not something a session saved."""
    (proofs / ".DS_Store").write_bytes(b"\x00\x01Bud1")
    out = tmp_path / "out"

    assert pr.main(["proofs", "15", str(proofs), "--dry-run", str(out)], Shell(), SESSION) == 0
    assert (out / "proofs.md").read_text("utf-8").count("<details>") == 2


def test_proofs_too_long_for_one_comment_are_refused_and_never_cut(
    proofs: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (proofs / "long.txt").write_text("x" * 70000, "utf-8")

    code = pr.main(
        ["proofs", "15", str(proofs), "--dry-run", str(tmp_path / "out")], Shell(), SESSION
    )

    assert code == 1
    err = capsys.readouterr().err
    assert "long.txt" in err
    assert "[…]" in err  # the session cuts, and marks the cut; the script does not


def test_the_first_proofs_comment_is_posted(proofs: Path) -> None:
    shell = Shell()

    assert pr.main(["proofs", "15", str(proofs)], shell, SESSION) == 0

    (write,) = shell.writes()
    assert write[:3] == ["gh", "api", "repos/{owner}/{repo}/issues/15/comments"]
    (body,) = shell.posted
    assert body.splitlines()[0] == f"<!-- proofs head={HEAD} sessions=session-one -->"
    assert block("red.txt", RED) in body


def test_a_later_proofs_comment_replaces_the_earlier_one_and_keeps_its_session_ids(
    proofs: Path,
) -> None:
    earlier = f"4711 me <!-- proofs head={'a' * 40} sessions=session-zero,session-one -->\n"
    shell = Shell(earlier=earlier)

    assert pr.main(["proofs", "15", str(proofs)], shell, {"CLAUDE_CODE_SESSION_ID": "s-two"}) == 0

    (write,) = shell.writes()
    assert write[:5] == ["gh", "api", "-X", "PATCH", "repos/{owner}/{repo}/issues/comments/4711"]
    (body,) = shell.posted
    marker = f"<!-- proofs head={HEAD} sessions=session-zero,session-one,s-two -->"
    assert body.splitlines()[0] == marker


# The invariant of the proofs comment: the script writes only to a proofs comment that the
# account it is logged in as wrote, and puts into the marker line only what is an id. Anyone who
# can comment on the pull request can post a comment that begins like a proofs comment.

OLD = "a" * 40
EVIL = "a--><b>MERGE-ME</b>[x](http://evil.example),b"


def test_a_proofs_comment_of_another_account_is_not_the_one_replaced(proofs: Path) -> None:
    earlier = (
        f"111 me <!-- proofs head={OLD} sessions=session-zero -->\n"
        f"999 mallory <!-- proofs head={OLD} sessions={EVIL} -->\n"
    )
    shell = Shell(earlier=earlier)

    assert pr.main(["proofs", "15", str(proofs)], shell, SESSION) == 0

    (write,) = shell.writes()
    assert write[:5] == ["gh", "api", "-X", "PATCH", "repos/{owner}/{repo}/issues/comments/111"]
    (body,) = shell.posted
    assert body.splitlines()[0] == f"<!-- proofs head={HEAD} sessions=session-zero,session-one -->"


def test_with_only_another_accounts_proofs_comment_a_new_one_is_posted(proofs: Path) -> None:
    shell = Shell(earlier=f"999 mallory <!-- proofs head={OLD} sessions={EVIL} -->\n")

    assert pr.main(["proofs", "15", str(proofs)], shell, SESSION) == 0

    (write,) = shell.writes()
    assert write[:3] == ["gh", "api", "repos/{owner}/{repo}/issues/15/comments"]
    (body,) = shell.posted
    assert body.splitlines()[0] == f"<!-- proofs head={HEAD} sessions=session-one -->"


def test_the_newest_of_the_accounts_own_proofs_comments_is_the_one_replaced(proofs: Path) -> None:
    earlier = (
        f"111 me <!-- proofs head={OLD} sessions=session-zero -->\n"
        f"222 me <!-- proofs head={OLD} sessions=session-two -->\n"
    )
    shell = Shell(earlier=earlier)

    assert pr.main(["proofs", "15", str(proofs)], shell, SESSION) == 0

    (write,) = shell.writes()
    assert write[4] == "repos/{owner}/{repo}/issues/comments/222"


@pytest.mark.parametrize("sessions", [EVIL, "a b", "a,<img>", "é", ",", "a,,b"])
def test_an_earlier_marker_that_holds_more_than_ids_gives_no_ids(
    proofs: Path, sessions: str
) -> None:
    """Its own comment, edited by someone else: the comment is replaced, and nothing of its
    first line is copied into the new one."""
    shell = Shell(earlier=f"111 me <!-- proofs head={OLD} sessions={sessions} -->\n")

    assert pr.main(["proofs", "15", str(proofs)], shell, SESSION) == 0

    (write,) = shell.writes()
    assert write[4] == "repos/{owner}/{repo}/issues/comments/111"
    (body,) = shell.posted
    assert body.splitlines()[0] == f"<!-- proofs head={HEAD} sessions=session-one -->"


@pytest.mark.parametrize("session", ["s 1 --> x", "a,b", "<b>", "é", "a\nb"])
def test_a_session_id_that_is_not_an_id_is_refused(
    proofs: Path, session: str, capsys: pytest.CaptureFixture[str]
) -> None:
    shell = Shell()

    assert pr.main(["proofs", "15", str(proofs)], shell, {"CLAUDE_CODE_SESSION_ID": session}) == 1

    assert shell.calls == []
    assert "$CLAUDE_CODE_SESSION_ID is not an id" in capsys.readouterr().err


OLD_MARKER = f"<!-- proofs head={OLD} sessions=x -->"


@pytest.mark.parametrize("separator", ["\u2028", "\r", "\x0c", "\x85"])
def test_a_comment_that_hides_a_second_line_cannot_choose_the_comment_replaced(
    proofs: Path, separator: str
) -> None:
    """The listing has one line per comment, cut at `\\n` by jq; a body whose first line holds
    another separator must stay one entry, or its author chooses the id that is overwritten and
    the session ids that are carried."""
    planted = f"999 me <!-- proofs head={OLD} sessions=planted1,planted2 -->"
    shell = Shell(earlier=f"50 mallory {OLD_MARKER}{separator}{planted}\n")

    assert pr.main(["proofs", "15", str(proofs)], shell, {"CLAUDE_CODE_SESSION_ID": "mine"}) == 0

    (write,) = shell.writes()
    assert write[:3] == ["gh", "api", "repos/{owner}/{repo}/issues/15/comments"]  # a new comment
    assert "comments/999" not in " ".join(write)
    (body,) = shell.posted
    assert body.splitlines()[0] == f"<!-- proofs head={HEAD} sessions=mine -->"


def test_a_hidden_second_line_in_the_accounts_own_comment_changes_nothing_either(
    proofs: Path,
) -> None:
    planted = f"999 me <!-- proofs head={OLD} sessions=planted -->"
    shell = Shell(earlier=f"50 me {OLD_MARKER}\u2028{planted}\n")

    assert pr.main(["proofs", "15", str(proofs)], shell, {"CLAUDE_CODE_SESSION_ID": "mine"}) == 0

    (write,) = shell.writes()
    assert write[4] == "repos/{owner}/{repo}/issues/comments/50"
    (body,) = shell.posted
    assert body.splitlines()[0] == f"<!-- proofs head={HEAD} sessions=mine -->"  # nothing carried


def test_a_first_line_that_ends_in_a_carriage_return_is_still_the_marker(proofs: Path) -> None:
    """GitHub stores bodies with `\\r\\n`; jq's cut at `\\n` leaves the `\\r`."""
    shell = Shell(earlier=f"50 me {OLD_MARKER}\r\n")

    assert pr.main(["proofs", "15", str(proofs)], shell, SESSION) == 0

    (write,) = shell.writes()
    assert write[4] == "repos/{owner}/{repo}/issues/comments/50"
    (body,) = shell.posted
    assert body.splitlines()[0] == f"<!-- proofs head={HEAD} sessions=x,session-one -->"


def test_an_entry_whose_id_is_not_a_number_is_no_comment_to_replace(proofs: Path) -> None:
    shell = Shell(earlier=f"../../repos/x/y/issues/comments/7 me {OLD_MARKER}\n")

    assert pr.main(["proofs", "15", str(proofs)], shell, SESSION) == 0

    (write,) = shell.writes()
    assert write[:3] == ["gh", "api", "repos/{owner}/{repo}/issues/15/comments"]


def test_the_empty_part_pattern_costs_the_same_on_a_long_run_of_spaces() -> None:
    """Two runs of `\\s*` side by side made the pattern try every way to share the spaces: four
    times the time for twice the length. The spaces before a checkbox belong to the checkbox."""
    import time

    line = "-" + " " * 64_000 + "x"
    started = time.perf_counter()
    assert pr.EMPTY.fullmatch(line) is None
    assert time.perf_counter() - started < 2  # the quadratic pattern took about 14 s here


def test_the_lookup_of_earlier_proofs_comments_asks_who_wrote_each(proofs: Path) -> None:
    shell = Shell()

    assert pr.main(["proofs", "15", str(proofs)], shell, SESSION) == 0

    (listing,) = [call for call in shell.calls if "--paginate" in call]
    assert ".user.login" in listing[-1]
    assert ["gh", "api", "user", "--jq", ".login"] in shell.calls


def test_proofs_are_refused_while_the_head_is_not_pushed(
    proofs: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    shell = Shell(pr_head="c" * 40)

    assert pr.main(["proofs", "15", str(proofs)], shell, SESSION) == 1

    assert shell.writes() == []
    err = capsys.readouterr().err
    assert "ccccccc" in err
    assert "bbbbbbb" in err


def test_a_command_that_fails_is_reported_with_its_reason(
    proofs: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def broken(args: list[str]) -> CompletedProcess[str]:
        return CompletedProcess(args, 128, stdout="", stderr="fatal: not a git repository")

    assert pr.main(["proofs", "15", str(proofs)], broken, SESSION) == 1
    assert "not a git repository" in capsys.readouterr().err


def test_the_script_passes_the_strict_type_check_on_a_copy_outside_its_dot_folder(
    tmp_path: Path,
) -> None:
    """`make types` never reads this script where it lives: basedpyright leaves out every folder
    whose name starts with a dot, also when it is named to it, and then reports 0 errors in the
    files it did read. A copy has no such folder above it; the unannotated function beside it
    shows that the run is strict and that it read what it was given."""
    copy = tmp_path / "pr.py"
    copy.write_bytes(Path(pr.__file__).read_bytes())
    untyped = tmp_path / "untyped.py"
    untyped.write_text("def same(value):\n    return value\n", "utf-8")

    done = subprocess.run(
        [sys.executable, "-m", "basedpyright", "--outputjson", str(copy), str(untyped)],
        cwd=ROOT,  # where pyproject.toml sets the mode
        capture_output=True,
        text=True,
        check=False,
    )

    report = json.loads(done.stdout)
    assert report["summary"]["filesAnalyzed"] == 2
    files = {Path(diagnostic["file"]).name for diagnostic in report["generalDiagnostics"]}
    assert files == {"untyped.py"}, done.stdout


SKILL = Path(pr.__file__).resolve().parents[1]


def test_the_page_template_in_the_skill_is_refused_until_it_is_filled_in() -> None:
    template = (SKILL / "assets" / "pr-page.md").read_text("utf-8")

    problems = pr.page_problems(template)

    # nothing is wrong with its shape: what is wrong is that nobody has written the page yet
    assert problems
    assert all("comment" in each or "is empty" in each for each in problems), problems
    assert any('the part "## Next steps for the maintainer" is empty' in each for each in problems)


def test_the_page_template_filled_in_is_a_page() -> None:
    template = (SKILL / "assets" / "pr-page.md").read_text("utf-8")
    without_comments = re.sub(r"<!--.*?-->\n?", "", template, flags=re.DOTALL)
    filled = re.sub(r"^(## .+)$", r"\1\nWritten.", without_comments, flags=re.MULTILINE)

    assert pr.page_problems(filled.replace("- [ ]\n", "")) == []


def test_the_filled_example_in_the_skill_is_a_page() -> None:
    example = (SKILL / "references" / "page.md").read_text("utf-8")
    filled = example.split("````markdown\n", 1)[1].split("\n````\n", 1)[0]

    assert pr.page_problems(filled) == []
    above = filled.split(pr.REFERENCE_LINE, 1)[0].splitlines()
    assert 30 < len(above) <= pr.PAGE_LINES  # a whole page, not a stub that passes for one
