"""The Stop hook blocks on a red `make check`, and only when code changed.

It asks nothing else: a test that vanished is the CI job `integrity`'s to report, with the
maintainer's label (`test_ci_still_holds_the_merge_for_a_weakened_test` is where that stays
true)."""

import io
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from subprocess import CompletedProcess

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
        # a tool's own config file changes what `make check` checks
        (["pytest.ini"], True),
        (["docs/x.md", "pyrightconfig.json"], True),
        (["GNUmakefile"], True),
        # pytest loads a conftest.py at the root
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

    The hook runs `make check` and nothing else: any other command fails the test.
    """

    def __init__(self, make: tuple[int, str]):
        self.make = make
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str]) -> CompletedProcess[str]:
        self.calls.append(args)
        if args[0] != "make":
            raise AssertionError(f"the hook ran {args}: it may run `make check` only")
        code, out = self.make
        return CompletedProcess(args, code, stdout=out, stderr="")


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
    assert run.calls == [["make", "check"]]  # nothing else is run


class MissingProgram(Runner):
    """A runner on a machine where one program is not installed: starting it raises."""

    def __init__(self, missing: str, make: tuple[int, str]):
        super().__init__(make)
        self.missing = missing

    def __call__(self, args: list[str]) -> CompletedProcess[str]:
        if args[0] == self.missing:
            self.calls.append(args)
            raise FileNotFoundError(2, "No such file or directory", self.missing)
        return super().__call__(args)


def test_make_that_cannot_be_started_blocks(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An uncaught exception would exit 1, and Claude Code does not block on exit 1."""
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


def test_a_green_gate_lets_the_session_stop_and_nothing_else_is_run(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A session that removed a test on purpose is not held: CI's `integrity` job reports it."""
    changed_set(monkeypatch, "tests/t.py", base=stop_gate.BASE_BRANCH)
    run = Runner(make=(0, "ok\n"))

    assert stop_gate.main(run) == 0

    assert capsys.readouterr().err == ""
    assert run.calls == [["make", "check"]]  # no integrity check, no `gh` for a label


CI = stop_gate.ROOT / ".github" / "workflows" / "ci.yml"


def test_ci_still_holds_the_merge_for_a_weakened_test() -> None:
    """The check the hook gave up is CI's: the job runs the whole script and wants the label."""
    text = CI.read_text(encoding="utf-8")
    job = text.split("\n  integrity:\n", 1)[1].split("\n  gate-guard:\n", 1)[0]
    assert "if: github.event_name == 'pull_request'" in job
    assert 'uv run python scripts/integrity.py --base "$BASE"' in job
    assert "--tests-only" not in job  # the whole check, escape-hatch comments and skips included
    assert "grep -qxF 'checks-weakened-approved'" in job
    assert "exit 1" in job.split("grep -qxF 'checks-weakened-approved'", 1)[1]  # no label: red


def test_nothing_changed_runs_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    changed_set(monkeypatch, "docs/x.md")
    run = Runner(make=(2, "would be red\n"))

    assert stop_gate.main(run) == 0
    assert run.calls == []


def test_a_reviewers_clone_is_not_gated(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The review launcher marks its processes: a reviewer changes nothing, and a red gate on the
    PR under review is the author's to pass, not the reviewer's (without the marker both reviewers
    would run to their time limits on the branch's own red)."""
    changed_set(monkeypatch, "src/pkg/a.py")
    monkeypatch.setenv(stop_gate.REVIEWER_CLONE_VARIABLE, "1")
    run = Runner(make=(2, "would be red\n"))

    assert stop_gate.main(run) == 0
    assert run.calls == []
    assert "reviewer" in capsys.readouterr().err


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
    git("update-ref", f"refs/remotes/origin/{stop_gate.BASE_BRANCH}", "HEAD")
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
