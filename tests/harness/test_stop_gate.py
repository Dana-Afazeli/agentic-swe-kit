"""The Stop hook blocks on a red `make check` or a weakened test, and only when code changed."""

import io
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from subprocess import CompletedProcess
from typing import Any

import pytest

import stop_gate

ORIGIN_BASE = f"origin/{stop_gate.BASE_BRANCH}"


@pytest.mark.parametrize(
    ("changed", "expected"),
    [
        (["docs/x.md"], False),
        ([], False),
        (["src/pkg/a.py"], True),
        (["tests/t.py"], True),
        (["scripts/fmt_hook.py"], True),
        (["Makefile"], True),
        (["uv.lock"], True),
        (["pyproject.toml"], True),
        ([".python-version"], True),
        # a tool's own config file changes what `make check` checks (PR #5 review, round 4)
        (["pytest.ini"], True),
        (["docs/x.md", "pyrightconfig.json"], True),
        (["GNUmakefile"], True),
        # pytest loads a conftest.py at the root (PR #5 review, round 8)
        (["conftest.py"], True),
        (["docs/conftest.py"], False),
        (["docs/ruff.toml"], False),
        (["docs/x.md", "README.md", "AGENTS.md", ".github/workflows/ci.yml"], False),
        (["docs/src/x.md", "srcs/a.py", "docs/Makefile"], False),
        (["docs/x.md", "tests/t.py"], True),
    ],
)
def test_needs_gate(changed: list[str], expected: bool) -> None:
    assert stop_gate.needs_gate(changed) is expected


class Runner:
    """Stands in for the commands the hook runs; records what was asked.

    `labels` is what `gh` answers when asked for the PR's labels: (exit code, output).
    """

    def __init__(
        self,
        make: tuple[int, str],
        integrity: tuple[int, str, str] = (0, "", ""),
        labels: tuple[int, str] = (0, ""),
    ):
        self.make = make
        self.integrity = integrity
        self.labels = labels
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str]) -> CompletedProcess[str]:
        self.calls.append(args)
        if args[0] == "make":
            code, out = self.make
            return CompletedProcess(args, code, stdout=out, stderr="")
        if args[0] == "gh":
            code, out = self.labels
            return CompletedProcess(args, code, stdout=out, stderr="")
        code, out, err = self.integrity
        return CompletedProcess(args, code, stdout=out, stderr=err)


GH_LABELS = ["gh", "pr", "view", "--json", "labels", "--jq", ".labels[].name"]
VANISHED = "vanished tests (1):\n  tests/t.py::test_gone\n"


def changed_set(
    monkeypatch: pytest.MonkeyPatch, *paths: str, base: str | None = ORIGIN_BASE
) -> None:
    def find_base() -> str | None:
        return base

    def changed_paths(_base: str) -> list[str]:
        return list(paths)

    monkeypatch.setattr(stop_gate, "find_base", find_base)
    monkeypatch.setattr(stop_gate, "changed_paths", changed_paths)


def test_red_make_check_blocks_with_the_last_40_lines(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    changed_set(monkeypatch, "src/pkg/a.py")
    output = "".join(f"line {number}\n" for number in range(1, 61))
    run = Runner(make=(2, output))

    assert stop_gate.main(run) == 2

    err = capsys.readouterr().err
    assert "line 21\n" in err
    assert "line 60\n" in err
    assert "line 20\n" not in err
    assert "make check" in err
    assert run.calls == [["make", "check"]]  # integrity is not asked while the gate is red


def test_weakened_test_blocks_and_names_the_label(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    changed_set(monkeypatch, "tests/t.py")
    run = Runner(make=(0, "ok\n"), integrity=(1, VANISHED, ""), labels=(0, "brief-approved\n"))

    assert stop_gate.main(run) == 2

    err = capsys.readouterr().err
    assert "tests/t.py::test_gone" in err
    assert "needs the maintainer: label `checks-weakened-approved`" in err
    assert run.calls[-1] == GH_LABELS  # the hook asked for the PR's labels before blocking


@pytest.mark.parametrize(
    "labels",
    ["checks-weakened-approved\n", "brief-approved\nchecks-weakened-approved\ngates-approved\n"],
)
def test_a_weakened_test_dana_approved_lets_the_session_stop(
    labels: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The label on the branch's PR is the maintainer's answer; the hook reads it as CI does."""
    changed_set(monkeypatch, "tests/t.py")
    run = Runner(make=(0, "ok\n"), integrity=(1, VANISHED, ""), labels=(0, labels))

    assert stop_gate.main(run) == 0
    assert run.calls[-1] == GH_LABELS


def test_a_label_that_only_contains_the_name_is_not_the_label(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    changed_set(monkeypatch, "tests/t.py")
    labels = "not-checks-weakened-approved\nchecks-weakened-approved-later\n"
    run = Runner(make=(0, "ok\n"), integrity=(1, VANISHED, ""), labels=(0, labels))

    assert stop_gate.main(run) == 2


def test_labels_that_cannot_be_read_block(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """No PR, no network, no login: the hook cannot know, so it fails closed."""
    changed_set(monkeypatch, "tests/t.py")
    failure = "no pull requests found for branch\nchecks-weakened-approved\n"
    run = Runner(make=(0, "ok\n"), integrity=(1, VANISHED, ""), labels=(1, failure))

    assert stop_gate.main(run) == 2

    err = capsys.readouterr().err
    assert "tests/t.py::test_gone" in err
    assert "could not read the labels of this branch's PR" in err
    assert "no pull requests found for branch" in err
    assert "needs the maintainer: label `checks-weakened-approved`" in err


class MissingProgram(Runner):
    """A runner on a machine where one program is not installed: starting it raises."""

    def __init__(self, missing: str, **results: Any):
        super().__init__(**results)
        self.missing = missing

    def __call__(self, args: list[str]) -> CompletedProcess[str]:
        if args[0] == self.missing:
            self.calls.append(args)
            raise FileNotFoundError(2, "No such file or directory", self.missing)
        return super().__call__(args)


def test_gh_that_cannot_be_started_blocks(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An uncaught exception would exit 1, and Claude Code does not block on exit 1."""
    changed_set(monkeypatch, "tests/t.py")
    run = MissingProgram("gh", make=(0, "ok\n"), integrity=(1, VANISHED, ""))

    assert stop_gate.main(run) == 2

    err = capsys.readouterr().err
    assert "tests/t.py::test_gone" in err
    assert "could not read the labels of this branch's PR" in err
    assert "No such file or directory" in err
    assert "needs the maintainer: label `checks-weakened-approved`" in err


def test_make_that_cannot_be_started_blocks(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    changed_set(monkeypatch, "src/pkg/a.py")
    run = MissingProgram("make", make=(0, "ok\n"))

    assert stop_gate.main(run) == 2

    err = capsys.readouterr().err
    assert err.startswith("stop gate: the gate itself failed")
    assert "FileNotFoundError" in err


def test_any_failure_inside_the_hook_blocks(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def find_base() -> str | None:
        raise RuntimeError("boom")

    monkeypatch.setattr(stop_gate, "find_base", find_base)

    assert stop_gate.main(Runner(make=(0, ""))) == 2
    assert "stop gate: the gate itself failed (RuntimeError('boom'))" in capsys.readouterr().err


def test_integrity_that_cannot_be_determined_blocks_with_its_reason(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    changed_set(monkeypatch, "tests/t.py")
    cannot = (2, "", "integrity: cannot determine: no base\n")
    run = Runner(make=(0, "ok\n"), integrity=cannot, labels=(0, "checks-weakened-approved\n"))

    assert stop_gate.main(run) == 2

    err = capsys.readouterr().err
    assert "integrity: cannot determine: no base" in err
    assert "checks-weakened-approved" not in err
    assert GH_LABELS not in run.calls  # no label covers "could not compare"


def test_green_gate_and_clean_integrity_let_the_session_stop(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    changed_set(monkeypatch, "src/pkg/a.py", base=stop_gate.BASE_BRANCH)
    run = Runner(make=(0, "ok\n"), integrity=(0, "integrity: clean\n", ""))

    assert stop_gate.main(run) == 0

    assert capsys.readouterr().err == ""
    integrity = [sys.executable, str(stop_gate.ROOT / "scripts" / "integrity.py")]
    assert run.calls == [
        ["make", "check"],
        [*integrity, "--base", stop_gate.BASE_BRANCH, "--tests-only"],
    ]


def test_nothing_changed_runs_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    changed_set(monkeypatch, "docs/x.md")
    run = Runner(make=(2, "would be red\n"))

    assert stop_gate.main(run) == 0
    assert run.calls == []


def test_git_that_cannot_say_what_changed_blocks_with_its_reason(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def find_base() -> str | None:
        return f"origin/{stop_gate.BASE_BRANCH}"

    def changed_paths(_base: str) -> list[str]:
        raise stop_gate.GitError("fatal: no merge base")

    monkeypatch.setattr(stop_gate, "find_base", find_base)
    monkeypatch.setattr(stop_gate, "changed_paths", changed_paths)
    run = Runner(make=(0, ""))

    assert stop_gate.main(run) == 2
    assert f"origin/{stop_gate.BASE_BRANCH}: fatal: no merge base" in capsys.readouterr().err
    assert run.calls == []


def test_run_in_root_runs_in_the_repository_and_folds_stderr_into_stdout() -> None:
    result = stop_gate.run_in_root(["sh", "-c", "pwd; echo to-stderr >&2; exit 3"])

    assert result.returncode == 3
    assert result.stdout == f"{stop_gate.ROOT}\nto-stderr\n"
    assert result.stderr is None


def test_no_base_branch_blocks_with_a_reason(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    changed_set(monkeypatch, base=None)
    run = Runner(make=(0, ""))

    assert stop_gate.main(run) == 2
    assert f"origin/{stop_gate.BASE_BRANCH}" in capsys.readouterr().err
    assert run.calls == []


def test_a_red_gate_still_blocks_when_the_hook_already_blocked_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No `stop_hook_active` bypass (HARNESS.md): the CLI's block cap is the only way out."""
    changed_set(monkeypatch, "src/pkg/a.py")
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"stop_hook_active": true}'))

    assert stop_gate.main(Runner(make=(2, "red\n"))) == 2


Git = Callable[..., None]


@pytest.fixture
def repo(tmp_path: Path) -> tuple[Path, Git]:
    root = tmp_path / "repo"
    root.mkdir()

    def git(*args: str) -> None:
        identity = ["-c", "user.name=t", "-c", "user.email=t@example.invalid"]
        quiet = ["-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null"]
        subprocess.run(
            ["git", "-C", str(root), *identity, *quiet, *args], check=True, capture_output=True
        )

    git("init", "-q", "-b", stop_gate.BASE_BRANCH)
    (root / "README.md").write_text("base\n", "utf-8")
    git("add", "README.md")
    git("commit", "-q", "-m", "base")
    return root, git


def test_find_base_prefers_the_remote_branch(repo: tuple[Path, Git]) -> None:
    root, git = repo
    assert stop_gate.find_base(root) == stop_gate.BASE_BRANCH
    git("update-ref", "refs/remotes/origin/main", "HEAD")
    assert stop_gate.find_base(root) == f"origin/{stop_gate.BASE_BRANCH}"


def test_find_base_is_none_without_a_base_branch(repo: tuple[Path, Git]) -> None:
    root, git = repo
    git("branch", "-m", "trunk")
    assert stop_gate.find_base(root) is None


def test_changed_paths_joins_the_branch_diff_and_the_working_tree(repo: tuple[Path, Git]) -> None:
    root, git = repo
    git("switch", "-q", "-c", "main-999-probe")
    (root / "src").mkdir()
    (root / "src" / "committed.py").write_text("x = 1\n", "utf-8")
    git("add", "src/committed.py")
    git("commit", "-q", "-m", "work")
    (root / "README.md").write_text("edited\n", "utf-8")  # modified, unstaged
    (root / "tests").mkdir()
    (root / "tests" / "new file.py").write_text("y = 2\n", "utf-8")  # untracked, a space in it
    (root / "staged.md").write_text("z\n", "utf-8")
    git("add", "staged.md")

    assert stop_gate.changed_paths(stop_gate.BASE_BRANCH, root) == [
        "README.md",
        "src/committed.py",
        "staged.md",
        "tests/new file.py",
    ]


def test_changed_paths_lists_both_names_of_a_renamed_file(repo: tuple[Path, Git]) -> None:
    """A rename out of src/ must still count as a change under src/."""
    root, git = repo
    (root / "src").mkdir()
    body = "".join(f"line_{number} = {number}\n" for number in range(30))
    (root / "src" / "one.py").write_text(body, "utf-8")
    (root / "src" / "two.py").write_text(body.replace("line", "name"), "utf-8")
    git("add", ".")
    git("commit", "-q", "-m", "two files on the base")
    git("switch", "-q", "-c", "main-999-probe")
    git("mv", "src/one.py", "docs_one.py")
    git("commit", "-q", "-m", "renamed on the branch")
    git("mv", "src/two.py", "docs_two.py")  # renamed, staged, not committed

    assert stop_gate.changed_paths(stop_gate.BASE_BRANCH, root) == [
        "docs_one.py",
        "docs_two.py",
        "src/one.py",
        "src/two.py",
    ]


def test_changed_paths_cannot_answer_for_an_unknown_base(repo: tuple[Path, Git]) -> None:
    root, _git = repo
    with pytest.raises(stop_gate.GitError, match="no-such-base"):
        stop_gate.changed_paths("no-such-base", root)


def test_changed_paths_is_empty_on_an_untouched_base(repo: tuple[Path, Git]) -> None:
    root, _git = repo
    assert stop_gate.changed_paths(stop_gate.BASE_BRANCH, root) == []
