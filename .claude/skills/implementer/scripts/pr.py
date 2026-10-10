"""The two things an implementer shows on a pull request: the page, and the proofs comment.

    uv run python .claude/skills/implementer/scripts/pr.py page <pr> <file>
    uv run python .claude/skills/implementer/scripts/pr.py proofs <pr> <folder>

`page` sets the pull request's description from a file written on `assets/pr-page.md`, and
refuses a file that is not the page: more than 80 lines above the reference line; a part that is
missing, out of order, there twice, or has nothing written under it; a comment left from the
template; a comment or a code fence that never closes. The page is read as GitHub shows it: what
stands in a code fence or in inline code is code, not a heading or a comment. The script checks
the page's shape and leaves its words alone: whether the part above the line can be read by
someone with no memory of the session is the conformance reviewer's to judge.

`proofs` posts one comment built from the files in a folder: a marker line that names the head
the proofs belong to and the sessions that produced them, then one collapsed block per file with
the file's text unchanged. A later call replaces the newest proofs comment that the account `gh`
is logged in as wrote, and keeps its session ids; a comment of another account that begins like
one is left alone, and nothing but ids goes into the marker. Every entry of the folder is in the
comment or the call is refused and names it: a folder inside it, a file that is not UTF-8 text.
Files whose name starts with a dot are not proofs. It never cuts: a cut is the session's to make,
and to mark with `[…]`.

With `--dry-run FOLDER` nothing reaches GitHub: the page is written to `FOLDER/page.md`, the
comment to `FOLDER/proofs.md`.

Exit codes: 0 done; 1 refused, or a file could not be read, or a command failed, did not start
or did not answer: one line on stderr says which.
"""

import argparse
import html
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from itertools import pairwise
from pathlib import Path
from subprocess import CompletedProcess
from typing import NamedTuple

REFERENCE_LINE = "Reference: below this line, checked by the reviewers"
PAGE_LINES = 80
PARTS = (
    "## What this is, and where it sits",
    "## Next steps for the maintainer",
    "## Decisions for the maintainer",
    "## Not proven",
)
REFERENCE_PARTS = (
    "## File by file",
    "## Where this differs from the brief",
    "## The review record",
    "## Out of scope, noticed",
    "## Docs made stale, and fixed",
    "## Gate files changed",
    "## Checks weakened",
)
COMMENT_LEFT = "the template's comments are instructions: delete each one as you write its part"
# Nothing, or an empty list item (with or without its checkbox) or an empty quote: GitHub shows a
# bullet, a box or a bar, and nothing is written.
# The spaces before a checkbox belong to the checkbox: two runs of `\s*` side by side would try
# every way to share a long run of spaces, four times the time for twice the length.
EMPTY = re.compile(r"\s*(?:>\s*)*(?:(?:[-*+]|\d+[.)])(?:\s*\[[ xX]?\])?)?\s*")
# GitHub ends a line at `\n`, `\r` or `\r\n` and nowhere else; str.splitlines() would also end one
# at a form feed or a Unicode line separator, where GitHub shows one paragraph.
LINE_END = re.compile(r"\r\n|\r|\n")

SESSION = "CLAUDE_CODE_SESSION_ID"
DRY_RUN_FILES = ("page.md", "proofs.md")  # what `--dry-run FOLDER` writes
# The marker line is an HTML comment at the top of a comment anyone can imitate: nothing goes
# into it but ids, and nothing is copied out of one that holds more.
AN_ID = r"[0-9A-Za-z_-]+"
MARKER = re.compile(rf"<!-- proofs head=([0-9a-f]{{7,40}}) sessions=({AN_ID}(?:,{AN_ID})*) -->")
COMMENT_LIMIT = 65536  # characters GitHub takes in one comment
COMMENTS = "repos/{owner}/{repo}/issues"  # gh fills in the repository of the current folder
# One line per comment on the pull request that begins like a proofs comment: its id, the
# account that wrote it, then its first line.
EARLIER = (
    '.[] | select(.body | startswith("<!-- proofs head=")) '
    '| "\\(.id) \\(.user.login) \\(.body | split("\\n")[0])"'
)
ME = ["gh", "api", "user", "--jq", ".login"]  # the account gh is logged in as
COMMAND_TIMEOUT_S = 120

Runner = Callable[[list[str]], CompletedProcess[str]]


class Refused(Exception):
    """Nothing was sent, or it is not known whether it was; the message says which and why."""


def run_command(args: list[str]) -> CompletedProcess[str]:
    return subprocess.run(
        args, capture_output=True, text=True, check=False, timeout=COMMAND_TIMEOUT_S
    )


def _call(run: Runner, args: list[str]) -> str:
    shown = " ".join(args[:4])
    try:
        done = run(args)
    except subprocess.TimeoutExpired as late:
        raise Refused(
            f"`{shown}` did not answer within {late.timeout:.0f} s; whether it took effect is "
            "not known: look at the pull request before you run this again"
        ) from late
    except OSError as error:
        raise Refused(f"`{shown}` could not be started: {error}") from error
    if done.returncode != 0:
        reason = (done.stderr or done.stdout).strip()
        raise Refused(f"`{shown}` failed: {reason}")
    return done.stdout


def _read(file: Path) -> str:
    try:
        return file.read_text("utf-8")
    except UnicodeDecodeError as error:
        raise Refused(f"{file} is not UTF-8 text") from error
    except OSError as error:
        raise Refused(f"{file} could not be read: {error}") from error


def _write(folder: Path, name: str, text: str) -> Path:
    try:
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text(text, "utf-8")
    except OSError as error:
        raise Refused(f"{folder / name} could not be written: {error}") from error
    return folder / name


# --- the page -------------------------------------------------------------------------------------


class Scan(NamedTuple):
    """A page as GitHub shows it, line by line."""

    marks: list[str]  # where a heading can stand: comments taken out, the inside of a fence blank
    written: list[str]  # what counts as writing: comments taken out
    comments: list[int]  # the numbers of the lines on which a comment starts
    unclosed: str  # the comment or the fence that never closes, as a problem; or ""


FENCE = re.compile(r"\s*(`{3,}|~{3,})(.*)")
TICKS = re.compile(r"`+")


def _fence(line: str) -> tuple[str, int, str] | None:
    """A line that can open or close a code fence: the fence's character, its length, and what
    follows it on the line. A run of backticks that closes again on the same line is inline
    code, not a fence."""
    found = FENCE.fullmatch(line)
    if found is None:
        return None
    run, rest = found.group(1), found.group(2)
    if run[0] == "`" and "`" in rest:
        return None
    return run[0], len(run), rest.strip()


def _closing(line: str, start: int, length: int) -> int:
    """Where the run of backticks that closes an inline code span starts: the next run of the
    same length. -1 when there is none, and the opening run is plain text."""
    for run in TICKS.finditer(line, start):
        if len(run.group()) == length:
            return run.start()
    return -1


def _inline(line: str, number: int, comment: int) -> tuple[str, int, bool]:
    """One line outside a fence: its text without comments, the line on which the comment that
    is still open at its end started (0 when none is), and whether a comment starts on it. A
    comment starts only outside inline code."""
    kept = ""
    starts = False
    at = 0
    while at < len(line):
        if comment:
            end = line.find("-->", at)
            if end < 0:
                break
            comment, at = 0, end + 3
        elif line.startswith("<!--", at):
            comment, starts, at = number, True, at + 4
        elif line[at] == "`":
            length = len(line) - at - len(line[at:].lstrip("`"))
            close = _closing(line, at + length, length)
            # a span of inline code, or backticks that never close and are plain text
            end = at + length if close < 0 else close + length
            kept += line[at:end]
            at = end
        else:
            kept += line[at]
            at += 1
    return kept, comment, starts


def _scan(lines: Sequence[str]) -> Scan:
    """Read a page the way GitHub renders it. A fence closes only on a line of its own character
    that is at least as long, with nothing after it. What never closes is named with the line
    it opens on: GitHub hides everything after an open comment and shows everything after an
    open fence as code, so every other message about such a page would be a consequence."""
    scan = Scan([], [], [], "")
    fence: tuple[str, int, int] | None = None  # its character, its length, the line it opens on
    comment = 0  # the line on which the comment that is still open started
    for number, line in enumerate(lines, start=1):
        edge = None if comment else _fence(line)
        if fence is not None or edge is not None:
            if fence is None and edge is not None:
                fence = (edge[0], edge[1], number)
            elif fence is not None and edge is not None:
                closes = edge[0] == fence[0] and edge[1] >= fence[1] and not edge[2]
                fence = None if closes else fence
            scan.marks.append("")
            scan.written.append(line)
            continue
        kept, comment, starts = _inline(line, number, comment)
        if starts:
            scan.comments.append(number)
        scan.marks.append(kept.rstrip())
        scan.written.append(kept)
    unclosed = ""
    if comment:
        unclosed = (
            f"line {comment}: a comment opens here and never closes: GitHub hides everything "
            "after it. Close it with `-->`, or put the mark in backticks if it is meant as text"
        )
    elif fence is not None:
        unclosed = (
            f"line {fence[2]}: a code fence opens here and never closes: GitHub shows everything "
            "after it as code. Close it on a line of its own with the same marks, at least as many"
        )
    return scan._replace(unclosed=unclosed)


def _parts(marks: Sequence[str], parts: Sequence[str], where: str) -> list[str]:
    """Each part is a line of its own, once, and the parts come in their order."""
    at = {part: marks.index(part) for part in parts if part in marks}
    problems = [f'the part "{part}" is missing {where}' for part in parts if part not in at]
    problems += [
        f'the part "{part}" appears {marks.count(part)} times'
        for part in parts
        if marks.count(part) > 1
    ]
    found = [part for part in parts if part in at]
    problems += [
        f'"{later}" comes before "{earlier}"'
        for earlier, later in pairwise(found)
        if at[later] < at[earlier]
    ]
    return problems


def _empty(marks: Sequence[str], written: Sequence[str], parts: Sequence[str]) -> list[str]:
    """The parts with nothing written under them, up to the next heading or the reference line."""
    problems: list[str] = []
    for part in parts:
        if part not in marks:
            continue
        under: list[str] = []
        start = marks.index(part) + 1
        for mark, line in zip(marks[start:], written[start:], strict=True):
            if mark.startswith("## ") or mark == REFERENCE_LINE:
                break
            under.append(line)
        if all(EMPTY.fullmatch(line) for line in under):
            problems.append(f'the part "{part}" is empty')
    return problems


def page_problems(text: str) -> list[str]:
    """Why a text is not the page; empty when it is."""
    lines = [line.rstrip() for line in LINE_END.split(text)]
    if lines and lines[-1] == "":  # a final line end closes the last line, it opens no new one
        lines.pop()
    marks, written, comments, unclosed = _scan(lines)
    if unclosed:
        return [unclosed]
    if REFERENCE_LINE not in marks:
        return [f'the line "{REFERENCE_LINE}" is missing', *_parts(marks, PARTS, "from the page")]
    cut = marks.index(REFERENCE_LINE)
    problems: list[str] = []
    if cut > PAGE_LINES:
        problems.append(f"{cut} lines above the reference line; the page is at most {PAGE_LINES}")
    if marks.count(REFERENCE_LINE) > 1:
        times = marks.count(REFERENCE_LINE)
        problems.append(f'the line "{REFERENCE_LINE}" appears {times} times')
    problems += _parts(marks[:cut], PARTS, "above the reference line")
    problems += _parts(marks[cut + 1 :], REFERENCE_PARTS, "below the reference line")
    problems += _empty(marks[:cut], written[:cut], PARTS)
    problems += _empty(marks[cut + 1 :], written[cut + 1 :], REFERENCE_PARTS)
    problems += [
        f"line {number}: a comment is left: {lines[number - 1].strip()}\n    {COMMENT_LEFT}"
        for number in comments
    ]
    return problems


def set_page(number: int, file: Path, dry_run: Path | None, run: Runner) -> str:
    if not file.is_file():
        raise Refused(f"{file} is not a file")
    text = _read(file)
    problems = page_problems(text)
    if problems:
        raise Refused(f"{file} is not the page:\n" + "\n".join(f"- {each}" for each in problems))
    if dry_run is not None:
        return f"dry run: the page is in {_write(dry_run, 'page.md', text)}"
    _call(run, ["gh", "pr", "edit", str(number), "--body-file", str(file)])
    return f"the description of PR #{number} is {file}"


# --- the proofs comment ---------------------------------------------------------------------------


def _block(name: str, text: str) -> str:
    if not text.endswith("\n"):
        text += "\n"
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    fence = "`" * max(4, longest + 1)  # longer than any fence inside the proof
    return (
        f"<details><summary><code>{html.escape(name)}</code></summary>\n\n"
        f"{fence}\n{text}{fence}\n</details>\n"
    )


def proofs_body(proofs: Sequence[tuple[str, str]], head: str, sessions: Sequence[str]) -> str:
    """The comment: the marker, one line for the reader, and a collapsed block per proof, each
    given as (the file's name, its text)."""
    marker = f"<!-- proofs head={head} sessions={','.join(sessions)} -->"
    title = (
        f"**Proofs** at head `{head[:7]}`. Each block is a saved file, word for word; "
        "`[…]` marks every cut."
    )
    return "\n".join([marker, title, "", *(_block(name, text) for name, text in proofs)])


def _sessions(marker_line: str, current: str) -> list[str]:
    """The ids an earlier comment carries, then this session's, each once. A first line that is
    not a marker and nothing else carries none."""
    found = MARKER.fullmatch(marker_line.strip())
    earlier = found.group(2).split(",") if found else []
    return list(dict.fromkeys([*earlier, current]))


def _proof_files(folder: Path, dry_run: Path | None) -> list[Path]:
    """The files of the folder, or a refusal that names what cannot be a proof."""
    if not folder.is_dir():
        raise Refused(f"{folder} is not a folder")
    if dry_run is not None:
        inside, target = folder.resolve(), dry_run.resolve()
        if target == inside or inside in target.parents:
            raise Refused(
                f"{dry_run} is inside the folder of proofs: what is written there would be a "
                "proof of the next run. Name a folder elsewhere"
            )
    try:
        entries = sorted(path for path in folder.iterdir() if not path.name.startswith("."))
    except OSError as error:
        raise Refused(f"{folder} could not be read: {error}") from error
    for entry in entries:
        if entry.is_dir():
            raise Refused(
                f"{entry.name} is a folder: the comment holds the files at the top of {folder} "
                "and would leave it out without a word. Move its files up, or take it out"
            )
    for entry in entries:
        if (
            entry.name in DRY_RUN_FILES
        ):  # `page --dry-run` cannot know which folder holds the proofs
            raise Refused(
                f"{entry.name} is what a dry run writes, not a proof: move it out of {folder}"
            )
    if not entries:
        raise Refused(f"no files in {folder}: save each proof to a file first")
    return entries


def post_proofs(
    number: int, folder: Path, dry_run: Path | None, run: Runner, environ: Mapping[str, str]
) -> str:
    session = environ.get(SESSION, "")
    if not session:
        raise Refused(f"${SESSION} is not set: the marker names the session that made the proofs")
    if not re.fullmatch(AN_ID, session):
        raise Refused(
            f"${SESSION} is not an id (letters, digits, dashes and underscores): {session!r}"
        )
    files = _proof_files(folder, dry_run)
    proofs = [(file.name, _read(file)) for file in files]
    head = _call(run, ["git", "rev-parse", "HEAD"]).strip()

    comment = ""  # the id of the comment this one replaces
    if dry_run is not None:
        earlier = dry_run / "proofs.md"
        marker_line = _read(earlier).split("\n", 1)[0] if earlier.is_file() else ""
    else:
        view = ["gh", "pr", "view", str(number), "--json", "headRefOid", "--jq", ".headRefOid"]
        pushed = _call(run, view).strip()
        if pushed != head:
            raise Refused(
                f"PR #{number} is at {pushed[:7]} on GitHub and this checkout is at {head[:7]}: "
                "push first, the comment names the head its proofs belong to"
            )
        me = _call(run, ME).strip()
        listing = ["gh", "api", f"{COMMENTS}/{number}/comments", "--paginate", "--jq", EARLIER]
        # one line per comment, cut at `\n` only: jq cut the body's first line there, and a line
        # ended at any other separator would be text the comment's author chose (an id, a login)
        lines = [line.rstrip("\r") for line in _call(run, listing).split("\n")]
        found = [line.split(" ", 2) for line in lines]
        # only a comment this account wrote is its to replace: the newest one, by a numeric id
        own = [each for each in found if len(each) == 3 and each[1] == me and each[0].isdigit()]
        comment, marker_line = (own[-1][0], own[-1][2]) if own else ("", "")

    body = proofs_body(proofs, head, _sessions(marker_line, session))
    if len(body) > COMMENT_LIMIT:
        largest = max(proofs, key=lambda proof: len(proof[1]))[0]
        raise Refused(
            f"the comment would be {len(body)} characters and GitHub takes {COMMENT_LIMIT}: "
            f"the largest file is {largest}. Cut it yourself, and mark every cut with […]"
        )
    if dry_run is not None:
        return f"dry run: the proofs comment is in {_write(dry_run, 'proofs.md', body)}"
    with tempfile.TemporaryDirectory() as scratch:
        file = _write(Path(scratch), "proofs.md", body)
        field = ["-F", f"body=@{file}"]
        if comment:
            _call(run, ["gh", "api", "-X", "PATCH", f"{COMMENTS}/comments/{comment}", *field])
            return f"the proofs comment of PR #{number} is replaced ({len(files)} files)"
        _call(run, ["gh", "api", f"{COMMENTS}/{number}/comments", *field])
    return f"the proofs comment of PR #{number} is posted ({len(files)} files)"


# --- the command line -----------------------------------------------------------------------------


def parse(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="pr.py", description=(__doc__ or "").split("\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    page = commands.add_parser("page", help="set the description from a page file")
    page.add_argument("pr", type=int)
    page.add_argument("file", type=Path)
    proofs = commands.add_parser("proofs", help="post the proofs comment from a folder of files")
    proofs.add_argument("pr", type=int)
    proofs.add_argument("folder", type=Path)
    for command in (page, proofs):
        command.add_argument(
            "--dry-run",
            type=Path,
            metavar="FOLDER",
            help="write the result into FOLDER and send nothing to GitHub",
        )
    return parser.parse_args(argv)


def main(
    argv: Sequence[str] | None = None,
    run: Runner = run_command,
    environ: Mapping[str, str] = os.environ,
) -> int:
    call = parse(argv)
    number: int = call.pr
    dry_run: Path | None = call.dry_run
    try:
        if call.command == "page":
            file: Path = call.file
            done = set_page(number, file, dry_run, run)
        else:
            folder: Path = call.folder
            done = post_proofs(number, folder, dry_run, run, environ)
    except Refused as refusal:
        print(f"pr: {refusal}", file=sys.stderr)
        return 1
    print(f"pr: {done}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
