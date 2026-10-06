"""Test and check integrity (brief 002, ADR-0008): list what a change took out of the safety net.

    python scripts/integrity.py --base REF [--tests-only]

Compares the working tree with the commit where the branch left REF, and lists:

  vanished tests       test IDs `make check` ran there and does not run now: both trees are
                       collected with the gate's marker expression, so a test moved behind
                       `live` or `eval` counts. A renamed test is a vanished test too: intended,
                       the label is the answer.
  new skips            added lines under tests/, or in a conftest.py at the root, that skip or
                       xfail a test.
  new escape hatches   added lines under src/, scripts/ or tests/, or in the root conftest.py,
                       with a comment that switches a check off for that line or file (lint,
                       format, types, coverage, mutation). A moved line that already had one is
                       listed too. Left out with --tests-only.

The tool lists and does not judge; the maintainer does, with the label `checks-weakened-approved`.
The Stop hook runs it with --tests-only and the CI job `integrity` runs all of it: one script, so
the two cannot disagree about a test.

Exit codes: 0 nothing listed, 1 findings, 2 the comparison could not be made (the gate fails
closed, like mutation_gate.py).

This file is scanned by its own check, as are its tests, so neither writes a marker out: the
patterns below are regular expressions that do not match their own source text.
"""

import argparse
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# The marker expression `make check` runs pytest with (Makefile, `test` and `cov`; kept in step by
# tests/harness/test_gate_lists.py). Both trees are collected with it: a test moved behind `live`,
# `eval` or `prove` is still collected without it, but the gate no longer runs it — a vanished test.
GATE_MARKERS = "not live and not eval and not prove"

# Without `pytest.` in front, so that `from pytest import mark, skip` is covered; unittest's too.
SKIP = re.compile(
    r"\bmark\.(?:skip|skipif|xfail)\b"
    r"|\b(?:skip|skipIf|skipUnless|xfail|importorskip)\("
    r"|\bSkipTest\b|\bexpectedFailure\b"
)
ESCAPE = re.compile(
    r"#\s*(?:"
    r"(?:(?:ruff|flake8):\s*)?noqa\b"  # lint, one line or the whole file
    r"|ruff:\s*disable\b"  # lint, from here to the matching `enable`
    r"|type:\s*ignore|pyright:"  # types; `pyright:` also covers a file-level downgrade
    r"|pragma[:\s]?\s*no\s*(?:cover|mutate|branch)"  # coverage, mutation
    r"|(?:fmt|isort):\s*(?:off|skip)|yapf:\s*disable"  # `ruff format --check`, import order
    r")",
    re.IGNORECASE,
)
_HUNK = re.compile(r"@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
# Fixed prefixes and no rename detection, so the output does not depend on the user's git config.
# `--text`, so that it does not depend on the tree's `.gitattributes` either: with `*.py -diff`
# git prints "Binary files differ" and not one line, and that file is on no gate list.
_DIFF = (
    *("-c", "core.quotePath=false", "diff", "--no-color", "--no-ext-diff", "--no-renames"),
    *("--text", "--no-textconv", "--unified=0", "--src-prefix=a/", "--dst-prefix=b/"),
)
# pytest loads a conftest.py at the root as it loads the ones under tests/: it is test code.
_ROOT_CONFTEST = "conftest.py"


class CannotDetermine(RuntimeError):
    """The comparison could not be made; the caller must not read that as "nothing found"."""


@dataclass(frozen=True)
class Report:
    vanished: list[str]
    skips: list[str]
    escapes: list[str]

    @property
    def findings(self) -> int:
        return len(self.vanished) + len(self.skips) + len(self.escapes)


def vanished(base_ids: frozenset[str], head_ids: frozenset[str]) -> list[str]:
    return sorted(base_ids - head_ids)


def _added_lines(diff: str) -> Iterator[tuple[str, int, str]]:
    """(path, line number, text) of every line a unified diff adds."""
    path = ""
    old_left = new_left = number = 0
    for line in diff.split("\n"):
        if old_left > 0 or new_left > 0:  # inside a hunk: its header said how many lines follow
            if line.startswith("+"):
                yield path, number, line[1:]
                new_left -= 1
                number += 1
            elif line.startswith("-"):
                old_left -= 1
            elif not line.startswith("\\"):  # context ("\ No newline at end of file" is not)
                old_left -= 1
                new_left -= 1
                number += 1
        elif line.startswith("+++ "):
            path = line[4:].rstrip("\t").strip('"').removeprefix("b/")
        elif match := _HUNK.match(line):
            old_left = int(match[1] or 1)
            number = int(match[2])
            new_left = int(match[3] or 1)


def _findings(diff: str, pattern: re.Pattern[str], directories: tuple[str, ...]) -> list[str]:
    return [
        f"{path}:{number}: {text.strip()}"
        for path, number, text in _added_lines(diff)
        if path.endswith(".py") and path.startswith(directories) and pattern.search(text)
    ]


def new_skips(diff: str) -> list[str]:
    """Added lines in Python files under tests/, or in the root conftest.py, that skip or xfail."""
    return _findings(diff, SKIP, ("tests/", _ROOT_CONFTEST))


def new_escapes(diff: str) -> list[str]:
    """Added lines in Python files under src/, scripts/ or tests/, or in the root conftest.py,
    that switch a check off."""
    return _findings(diff, ESCAPE, ("src/", "scripts/", "tests/", _ROOT_CONFTEST))


class _Collector:
    """A pytest plugin object: the node IDs of one collection.

    The IDs are taken from pytest's hooks, not read off its terminal output: what pytest prints
    depends on the tree's own options (`-q`, `-v`, `-r…` in `addopts`), the hooks do not.
    """

    def __init__(self) -> None:
        self.ids: list[str] = []

    def pytest_collectreport(self, report: pytest.CollectReport) -> None:
        if report.failed:  # a module that cannot be imported: its tests cannot be listed
            self.ids.append(f"{report.nodeid} (cannot be collected)")

    def pytest_collection_finish(self, session: pytest.Session) -> None:
        self.ids.extend(item.nodeid for item in session.items)


def _collect_here(tree: Path, into: Path) -> int:
    """Collect `tree`/tests in this process and write the IDs to `into` (see `collect_ids`)."""
    collector = _Collector()
    config = tree / "pyproject.toml"
    code = pytest.main(
        [
            *("--collect-only", "-p", "no:cacheprovider", "--rootdir", str(tree)),
            *(("-c", str(config)) if config.is_file() else ()),
            *("-m", GATE_MARKERS),  # after the tree's `addopts`, as on `make check`'s command line
            str(tree / "tests"),
        ],
        plugins=[collector],
    )
    into.write_text(json.dumps(collector.ids), "utf-8")
    return int(code)


def collect_ids(tree: Path) -> frozenset[str]:
    """The test IDs `make check` runs in `tree`/tests, using this environment's pytest.

    A module that cannot be imported is kept as one entry of its own, because its tests cannot be
    listed: at the base that makes it a vanished test, which the label can resolve.

    The collection runs in a process of its own — this file, started with `--collect` — so that
    the tree's test modules are imported there and not here, and so that the collector is this
    file by path: a module of the same name inside the tree cannot stand in for it.
    """
    tree = tree.resolve()  # pytest names files relative to the real path, not through a symlink
    if not (tree / "tests").is_dir():
        return frozenset()
    # The tree's own src/ goes first on the import path. Its tests must import the package as it
    # is in that tree; otherwise the base tree would be collected against the working tree's
    # src/ (the editable install), and a module the change renamed would break every base test
    # that imports it.
    import_path = [str(tree / "src"), os.environ.get("PYTHONPATH", "")]
    with tempfile.TemporaryDirectory(prefix="integrity-ids-") as directory:
        into = Path(directory) / "ids.json"
        run = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--collect", str(tree), str(into)],
            cwd=tree,
            env=os.environ
            | {
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPATH": os.pathsep.join(filter(None, import_path)),
            },
            capture_output=True,
            text=True,
            errors="replace",
            check=False,
        )
        # 0 collected / 2 collection errors / 5 nothing to collect; anything else is no answer
        if run.returncode not in (0, 2, 5) or not into.is_file():
            last = (run.stderr or run.stdout).strip().splitlines()[-1:]
            raise CannotDetermine(f"pytest --collect-only exit {run.returncode} in {tree}: {last}")
        ids: list[str] = json.loads(into.read_text("utf-8"))
    return frozenset(ids)


def _git(root: Path, *args: str, ok: tuple[int, ...] = (0,)) -> str:
    git = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    )
    if git.returncode not in ok:
        reason = git.stderr.strip() or f"exit {git.returncode}"
        raise CannotDetermine(f"git {' '.join(args)}: {reason}")
    return git.stdout


def _diff(root: Path, commit: str, directories: tuple[str, ...]) -> str:
    """What the working tree adds under `directories` since `commit`, untracked files included."""
    tracked = _git(root, *_DIFF, commit, "--", *directories)
    untracked = _git(root, "ls-files", "--others", "--exclude-standard", "-z", "--", *directories)
    new_files = [
        _git(root, *_DIFF, "--no-index", "--", "/dev/null", path, ok=(0, 1))
        for path in untracked.split("\0")
        if path
    ]
    return "\n".join([tracked, *new_files])


def _extract(root: Path, commit: str, into: Path) -> None:
    """Unpack the tree of `commit` into a directory: no second checkout, nothing left in .git."""
    archive = subprocess.run(
        ["git", "-C", str(root), "archive", "--format=tar", commit],
        capture_output=True,
        check=False,
    )
    if archive.returncode != 0:
        reason = archive.stderr.decode(errors="replace").strip()
        raise CannotDetermine(f"git archive {commit}: {reason}")
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
        tar.extractall(into, filter="data")


def check(base: str, root: Path = ROOT, *, tests_only: bool = False) -> Report:
    # Where the branch left the base, not the base's tip: tests added to the base since then have
    # not vanished from this branch. In CI the checkout is the merge commit, and the two coincide.
    commit = _git(root, "merge-base", base, "HEAD").strip()
    skips = new_skips(_diff(root, commit, ("tests", _ROOT_CONFTEST)))
    everywhere = ("src", "scripts", "tests", _ROOT_CONFTEST)
    escapes = [] if tests_only else new_escapes(_diff(root, commit, everywhere))
    with tempfile.TemporaryDirectory(prefix="integrity-base-") as directory:
        _extract(root, commit, Path(directory))
        base_ids = collect_ids(Path(directory))
    return Report(vanished=vanished(base_ids, collect_ids(root)), skips=skips, escapes=escapes)


def main(argv: Sequence[str]) -> int:
    if list(argv[:1]) == ["--collect"]:  # internal: the process `collect_ids` starts
        return _collect_here(Path(argv[1]), Path(argv[2]))
    parser = argparse.ArgumentParser(
        prog="integrity.py", description="List vanished tests, new skips and new escape hatches."
    )
    parser.add_argument("--base", required=True, metavar="REF", help="the branch being merged into")
    parser.add_argument(
        "--tests-only", action="store_true", help="leave out escape hatches (the Stop hook does)"
    )
    arguments = parser.parse_args(argv)
    base: str = arguments.base
    tests_only: bool = arguments.tests_only
    try:
        report = check(base, tests_only=tests_only)
    except Exception as error:  # anything at all: a crash would exit 1, which means "findings"
        detail = error if isinstance(error, CannotDetermine) else repr(error)
        print(f"integrity: cannot determine: {detail}", file=sys.stderr)
        return 2
    if report.findings == 0:
        print(f"integrity: clean against {base}")
        return 0
    noun = "finding" if report.findings == 1 else "findings"
    print(
        f"integrity: {report.findings} {noun} against {base} — listed, not judged: "
        "the maintainer decides"
    )
    sections = (
        (
            "vanished tests",
            "in `make check` at the base, not now; a rename or a live/eval marker counts too",
            report.vanished,
        ),
        ("new skip or xfail markers", "added lines under tests/", report.skips),
        ("new escape-hatch comments", "added lines; a moved line counts too", report.escapes),
    )
    for title, note, lines in sections:
        if lines:
            print(f"{title} ({len(lines)}) — {note}:")
            for line in lines:
                print(f"  {line}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
