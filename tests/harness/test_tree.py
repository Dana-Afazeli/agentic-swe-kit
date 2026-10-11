"""`make tree` and `make untree`: one worktree per brief, in a sibling folder.

`scripts/tree.py` runs against temporary repositories with a bare `origin`, and the sync step
(`uv sync`) is passed in as a function, so no test installs anything.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import tree

BASE = tree.BASE_BRANCH
PREFIX = tree.BRANCH_PREFIX


def plain(name: str) -> str:
    """The branch as `--branch` and `--new` take it: one path segment. A prefix that holds
    a `/` (`feature/units`) makes a brief branch `--brief` finds and `--branch` refuses."""
    return name.replace("/", "-")


BRIEF_BRANCH = f"{PREFIX}-009-parallel"  # found by `--brief 009`
NAMED_BRANCH = plain(BRIEF_BRANCH)  # the same name, for `--branch` and `--new`
NEW_BRANCH = plain(f"{PREFIX}-010-y")
OTHER_BRANCH = f"{PREFIX}-009-other"
OLD_BRANCH = f"{PREFIX}-009-old"


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        [
            *("git", "-C", str(repo)),
            *("-c", "user.name=t", "-c", "user.email=t@example.invalid"),
            *("-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null"),
            *args,
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    return done.stdout.strip()


class Syncs:
    """The sync step, recording the folders it was asked to prepare."""

    def __init__(self, returncode: int = 0) -> None:
        self.folders: list[Path] = []
        self.returncode = returncode

    def __call__(self, folder: Path) -> int:
        self.folders.append(folder)
        return self.returncode


@pytest.fixture(autouse=True)
def no_user_git_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


@pytest.fixture
def main_checkout(tmp_path: Path) -> Path:
    """`<tmp>/project`, on the base branch, with a bare `origin` that holds the base and one
    brief branch (two, with the same commits, when a `/` in the prefix makes the name that
    `--branch` takes another one)."""
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", BASE, str(origin)], check=True)
    main = tmp_path / "project"
    main.mkdir()
    git(main, "init", "-q", "-b", BASE)
    (main / "f.txt").write_text("base\n", "utf-8")
    ignored = [".venv/", "__pycache__/", ".pytest_cache/", ".ruff_cache/", ".DS_Store", ".env"]
    (main / ".gitignore").write_text("\n".join([*ignored, ".claude/settings.local.json", ""]))
    git(main, "add", "-A")
    git(main, "commit", "-qm", "base")
    git(main, "remote", "add", "origin", str(origin))
    git(main, "push", "-q", "-u", "origin", BASE)
    for branch in dict.fromkeys((BRIEF_BRANCH, NAMED_BRANCH)):  # one name, or two
        git(main, "switch", "-q", "-c", branch)
        (main / "g.txt").write_text("brief\n", "utf-8")
        git(main, "add", "-A")
        git(main, "commit", "-qm", "brief work")
        git(main, "push", "-q", "-u", "origin", branch)
        git(main, "switch", "-q", BASE)
        git(main, "branch", "-q", "-D", branch)  # the checkout keeps no local copy
    return main


# --- make tree ------------------------------------------------------------------------------------


def test_a_brief_number_finds_the_one_branch_and_makes_a_worktree_beside_the_checkout(
    main_checkout: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    syncs = Syncs()

    code = tree.main(["tree", "--brief", "009"], cwd=main_checkout, sync=syncs)

    folder = main_checkout.parent / "project-009"
    out = capsys.readouterr().out
    assert code == 0
    assert git(folder, "branch", "--show-current") == BRIEF_BRANCH
    assert (folder / "g.txt").is_file()
    assert syncs.folders == [folder]
    assert f"tree: {folder}" in out
    assert f"cd {folder} && claude" in out
    assert git(folder, "rev-parse", "--abbrev-ref", "@{u}") == f"origin/{BRIEF_BRANCH}"


def test_no_branch_for_the_number_is_exit_2_that_says_what_was_looked_for(
    main_checkout: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = tree.main(["tree", "--brief", "042"], cwd=main_checkout, sync=Syncs())

    err = capsys.readouterr().err
    assert code == 2
    assert f"origin/{PREFIX}-042-*" in err
    assert not (main_checkout.parent / "project-042").exists()


def test_two_branches_for_the_number_are_exit_2_that_names_both(
    main_checkout: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    git(main_checkout, "push", "-q", "origin", f"{BASE}:refs/heads/{OTHER_BRANCH}")

    code = tree.main(["tree", "--brief", "009"], cwd=main_checkout, sync=Syncs())

    err = capsys.readouterr().err
    assert code == 2
    assert BRIEF_BRANCH in err
    assert OTHER_BRANCH in err


def test_an_existing_folder_is_exit_2_and_is_left_alone(
    main_checkout: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = main_checkout.parent / "project-009"
    folder.mkdir()
    (folder / "mine.txt").write_text("x", "utf-8")

    code = tree.main(["tree", "--brief", "009"], cwd=main_checkout, sync=Syncs())

    assert code == 2
    assert str(folder) in capsys.readouterr().err
    assert (folder / "mine.txt").is_file()


def test_run_from_inside_a_worktree_is_exit_2_that_names_the_main_checkout(
    main_checkout: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert tree.main(["tree", "--brief", "009"], cwd=main_checkout, sync=Syncs()) == 0
    capsys.readouterr()
    inside = main_checkout.parent / "project-009"

    code = tree.main(["tree", "--new", NEW_BRANCH], cwd=inside, sync=Syncs())

    err = capsys.readouterr().err
    assert code == 2
    assert str(main_checkout) in err
    assert not (main_checkout.parent / f"project-{NEW_BRANCH}").exists()


def test_outside_a_repository_is_exit_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = tree.main(["tree", "--brief", "009"], cwd=tmp_path, sync=Syncs())

    assert code == 2
    assert "main checkout" in capsys.readouterr().err


def test_new_creates_the_branch_at_the_base_on_origin_and_a_tree_for_it(
    main_checkout: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    git(main_checkout, "commit", "-q", "--allow-empty", "-m", "local only, not on origin")
    syncs = Syncs()

    code = tree.main(["tree", "--new", NEW_BRANCH], cwd=main_checkout, sync=syncs)

    folder = main_checkout.parent / f"project-{NEW_BRANCH}"
    assert code == 0
    assert git(folder, "branch", "--show-current") == NEW_BRANCH
    assert git(folder, "rev-parse", "HEAD") == git(main_checkout, "rev-parse", f"origin/{BASE}")
    assert syncs.folders == [folder]
    assert f"cd {folder} && claude" in capsys.readouterr().out


def test_new_with_a_name_that_exists_is_exit_2(
    main_checkout: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = tree.main(["tree", "--new", NAMED_BRANCH], cwd=main_checkout, sync=Syncs())

    assert code == 2
    assert NAMED_BRANCH in capsys.readouterr().err


def test_branch_takes_a_branch_by_name_and_names_the_folder_after_it(
    main_checkout: Path,
) -> None:
    code = tree.main(["tree", "--branch", NAMED_BRANCH], cwd=main_checkout, sync=Syncs())

    folder = main_checkout.parent / f"project-{NAMED_BRANCH}"
    assert code == 0
    assert git(folder, "branch", "--show-current") == NAMED_BRANCH


def test_a_branch_that_a_tree_already_holds_is_exit_2_with_git_s_reason(
    main_checkout: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    git(main_checkout, "switch", "-q", "-c", NAMED_BRANCH, f"origin/{NAMED_BRANCH}")

    code = tree.main(["tree", "--branch", NAMED_BRANCH], cwd=main_checkout, sync=Syncs())

    assert code == 2
    assert "already" in capsys.readouterr().err
    assert not (main_checkout.parent / f"project-{NAMED_BRANCH}").exists()


def test_a_sync_that_fails_leaves_the_tree_and_says_where_and_what_to_run(
    main_checkout: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = tree.main(["tree", "--brief", "009"], cwd=main_checkout, sync=Syncs(returncode=1))

    folder = main_checkout.parent / "project-009"
    err = capsys.readouterr().err
    assert code == 1
    assert folder.is_dir()
    assert str(folder) in err
    assert "uv sync --locked --all-groups" in err


@pytest.mark.parametrize(
    "args",
    [
        ["tree"],
        ["tree", "--brief", "009", "--new", NEW_BRANCH],
        ["tree", "--brief", "nine"],
        ["tree", "--branch", "-evil"],
        ["tree", "--new", "has space"],
        ["tree", "--new", "a/../b"],
        ["untree"],
        ["frobnicate", "--brief", "009"],
    ],
)
def test_an_argument_that_is_not_a_choice_of_one_brief_or_a_plain_branch_name_is_exit_2(
    main_checkout: Path, args: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    code = tree.main(args, cwd=main_checkout, sync=Syncs())

    assert code == 2
    assert capsys.readouterr().err != ""
    assert sorted(path.name for path in main_checkout.parent.iterdir()) == [
        "origin.git",
        "project",
    ]


# --- make untree ----------------------------------------------------------------------------------


@pytest.fixture
def made_tree(main_checkout: Path, capsys: pytest.CaptureFixture[str]) -> Path:
    assert tree.main(["tree", "--brief", "009"], cwd=main_checkout, sync=Syncs()) == 0
    capsys.readouterr()
    return main_checkout.parent / "project-009"


def test_untree_with_a_clean_pushed_tree_removes_the_folder_and_keeps_the_branch(
    main_checkout: Path, made_tree: Path
) -> None:
    code = tree.main(["untree", "--brief", "009"], cwd=main_checkout, sync=Syncs())

    assert code == 0
    assert not made_tree.exists()
    assert BRIEF_BRANCH in git(main_checkout, "branch", "--list", BRIEF_BRANCH)
    assert "project-009" not in git(main_checkout, "worktree", "list")


def test_untree_refuses_an_uncommitted_change_and_names_the_file(
    main_checkout: Path, made_tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (made_tree / "g.txt").write_text("changed\n", "utf-8")

    code = tree.main(["untree", "--brief", "009"], cwd=main_checkout, sync=Syncs())

    assert code == 2
    assert "g.txt" in capsys.readouterr().err
    assert made_tree.is_dir()


def test_untree_refuses_a_file_git_does_not_track_yet(
    main_checkout: Path, made_tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (made_tree / "notes.md").write_text("mine\n", "utf-8")

    code = tree.main(["untree", "--brief", "009"], cwd=main_checkout, sync=Syncs())

    assert code == 2
    assert "notes.md" in capsys.readouterr().err
    assert made_tree.is_dir()


def test_untree_refuses_a_commit_that_is_not_on_origin(
    main_checkout: Path, made_tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    git(made_tree, "commit", "-q", "--allow-empty", "-m", "not pushed")

    code = tree.main(["untree", "--brief", "009"], cwd=main_checkout, sync=Syncs())

    err = capsys.readouterr().err
    assert code == 2
    assert "not on origin" in err
    assert "1 commit" in err
    assert made_tree.is_dir()


def test_untree_of_a_new_branch_that_has_no_commit_of_its_own_removes_it(
    main_checkout: Path,
) -> None:
    assert tree.main(["tree", "--new", NEW_BRANCH], cwd=main_checkout, sync=Syncs()) == 0

    code = tree.main(["untree", "--branch", NEW_BRANCH], cwd=main_checkout, sync=Syncs())

    assert code == 0
    assert not (main_checkout.parent / f"project-{NEW_BRANCH}").exists()
    assert NEW_BRANCH in git(main_checkout, "branch", "--list", NEW_BRANCH)


def test_untree_of_a_new_branch_with_a_commit_that_was_never_pushed_is_refused(
    main_checkout: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert tree.main(["tree", "--new", NEW_BRANCH], cwd=main_checkout, sync=Syncs()) == 0
    folder = main_checkout.parent / f"project-{NEW_BRANCH}"
    git(folder, "commit", "-q", "--allow-empty", "-m", "mine")

    code = tree.main(["untree", "--branch", NEW_BRANCH], cwd=main_checkout, sync=Syncs())

    assert code == 2
    assert "not on origin" in capsys.readouterr().err
    assert folder.is_dir()


def test_untree_of_a_brief_with_no_tree_is_exit_2(
    main_checkout: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = tree.main(["untree", "--brief", "009"], cwd=main_checkout, sync=Syncs())

    assert code == 2
    assert "no tree" in capsys.readouterr().err


def test_untree_from_inside_a_tree_is_exit_2_that_names_the_main_checkout(
    main_checkout: Path, made_tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = tree.main(["untree", "--brief", "009"], cwd=made_tree, sync=Syncs())

    assert code == 2
    assert str(main_checkout) in capsys.readouterr().err
    assert made_tree.is_dir()


# --- the Makefile targets -------------------------------------------------------------------------

ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / ".github" / "workflows" / "ci.yml").is_file()
)


@pytest.mark.parametrize(
    ("target", "variable", "flag"),
    [
        ("tree", "BRIEF=009", "--brief '009'"),
        ("tree", f"BRANCH={NAMED_BRANCH}", f"--branch '{NAMED_BRANCH}'"),
        ("tree", f"NEW={NEW_BRANCH}", f"--new '{NEW_BRANCH}'"),
        ("untree", "BRIEF=009", "--brief '009'"),
        ("untree", f"BRANCH={NAMED_BRANCH}", f"--branch '{NAMED_BRANCH}'"),
    ],
)
def test_each_target_hands_its_variable_to_the_script(
    target: str, variable: str, flag: str
) -> None:
    done = subprocess.run(
        ["make", "-n", target, variable],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )

    assert done.returncode == 0, done.stderr
    assert f"scripts/tree.py {target} {flag}" in " ".join(done.stdout.split())


def test_a_target_without_its_variable_is_refused_by_the_script_with_exit_2() -> None:
    """The target hands the script no flag, and the script refuses that with exit 2. The script
    is run with this interpreter: `uv run` looks for the project's own Python, which a machine
    that runs a rendered project's tests may not have."""
    recipe = subprocess.run(
        ["make", "-n", "tree"], cwd=ROOT, capture_output=True, text=True, check=False, timeout=60
    )
    done = subprocess.run(
        [sys.executable, "scripts/tree.py", "tree"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )

    assert recipe.returncode == 0, recipe.stderr
    assert " ".join(recipe.stdout.split()) == "uv run python scripts/tree.py tree"
    assert done.returncode == 2
    assert "required" in done.stderr


def test_the_sync_does_not_inherit_the_virtual_environment_of_the_command_that_started_it() -> None:
    """`make tree` runs under `uv run`, which sets VIRTUAL_ENV to the main checkout's `.venv`; the
    sync in the new folder would warn about it and ignore it."""
    environment = {"VIRTUAL_ENV": "/main/.venv", "PATH": "/bin", "HOME": "/home/x"}

    assert tree.sync_environment(environment) == {"PATH": "/bin", "HOME": "/home/x"}
    assert tree.sync_environment({"PATH": "/bin"}) == {"PATH": "/bin"}


# --- what the first review round found ------------------------------------------------------------


def push_a_commit_from_a_second_clone(main: Path, branch: str, name: str) -> str:
    """Another machine's push: a commit on origin's `branch`, made in a clone of origin."""
    second = main.parent / f"second-{name}"
    origin = git(main, "remote", "get-url", "origin")
    subprocess.run(["git", "clone", "-q", origin, str(second)], check=True, timeout=60)
    git(second, "switch", "-q", branch)
    (second / f"{name}.txt").write_text(f"{name}\n", "utf-8")
    git(second, "add", "-A")
    git(second, "commit", "-qm", name)
    git(second, "push", "-q", "origin", branch)
    return git(second, "rev-parse", "HEAD")


def delete_a_branch_from_a_second_clone(main: Path, branch: str) -> None:
    """Another machine deletes `branch` on origin; this checkout keeps its tracking ref."""
    second = main.parent / f"second-delete-{branch}"
    subprocess.run(
        ["git", "clone", "-q", git(main, "remote", "get-url", "origin"), str(second)],
        check=True,
        timeout=60,
    )
    git(second, "push", "-q", "origin", "--delete", branch)


def a_local_commit_on_the_branch(main: Path, branch: str) -> str:
    """A commit on the local branch, made without a tree: `commit-tree` and `update-ref`."""
    tip = git(main, "rev-parse", branch)
    commit = git(main, "commit-tree", f"{tip}^{{tree}}", "-p", tip, "-m", "local")
    git(main, "update-ref", f"refs/heads/{branch}", commit)
    return commit


def test_untree_refuses_an_ignored_file_that_cannot_be_rebuilt_and_names_it(
    main_checkout: Path, made_tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (made_tree / ".env").write_text("TOKEN=x\n", "utf-8")
    (made_tree / ".claude").mkdir()
    (made_tree / ".claude" / "settings.local.json").write_text("{}\n", "utf-8")

    code = tree.main(["untree", "--brief", "009"], cwd=main_checkout, sync=Syncs())

    err = capsys.readouterr().err
    assert code == 2
    assert ".env" in err
    assert "settings.local.json" in err
    assert made_tree.is_dir()


def test_untree_removes_a_tree_whose_ignored_files_can_all_be_rebuilt(
    main_checkout: Path, made_tree: Path
) -> None:
    (made_tree / ".venv" / "bin").mkdir(parents=True)
    (made_tree / ".venv" / "bin" / "python").write_text("x", "utf-8")
    (made_tree / "pkg" / "__pycache__").mkdir(parents=True)
    (made_tree / "pkg" / "__pycache__" / "m.pyc").write_text("x", "utf-8")

    code = tree.main(["untree", "--brief", "009"], cwd=main_checkout, sync=Syncs())

    assert code == 0
    assert not made_tree.exists()


def test_a_second_tree_for_a_brief_starts_at_origin_when_its_local_branch_is_behind(
    main_checkout: Path, made_tree: Path
) -> None:
    assert tree.main(["untree", "--brief", "009"], cwd=main_checkout, sync=Syncs()) == 0
    pushed = push_a_commit_from_a_second_clone(main_checkout, BRIEF_BRANCH, "second")

    code = tree.main(["tree", "--brief", "009"], cwd=main_checkout, sync=Syncs())

    assert code == 0
    assert git(made_tree, "rev-parse", "HEAD") == pushed
    # tracking origin, and neither ahead nor behind it
    first_line = git(made_tree, "status", "--porcelain", "--branch").splitlines()[0]
    assert first_line == f"## {BRIEF_BRANCH}...origin/{BRIEF_BRANCH}"


def test_a_second_tree_for_a_brief_with_a_local_commit_says_it_is_ahead_and_keeps_it(
    main_checkout: Path, made_tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert tree.main(["untree", "--brief", "009"], cwd=main_checkout, sync=Syncs()) == 0
    local = a_local_commit_on_the_branch(main_checkout, BRIEF_BRANCH)

    code = tree.main(["tree", "--brief", "009"], cwd=main_checkout, sync=Syncs())

    assert code == 0
    assert git(made_tree, "rev-parse", "HEAD") == local
    assert "ahead of origin" in capsys.readouterr().out


def test_a_second_tree_for_a_brief_whose_branch_diverged_says_so_and_changes_nothing(
    main_checkout: Path, made_tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert tree.main(["untree", "--brief", "009"], cwd=main_checkout, sync=Syncs()) == 0
    local = a_local_commit_on_the_branch(main_checkout, BRIEF_BRANCH)
    push_a_commit_from_a_second_clone(main_checkout, BRIEF_BRANCH, "second")

    code = tree.main(["tree", "--brief", "009"], cwd=main_checkout, sync=Syncs())

    assert code == 0
    assert git(made_tree, "rev-parse", "HEAD") == local
    assert "diverged from origin" in capsys.readouterr().out


def test_a_branch_deleted_on_origin_no_longer_counts_for_a_brief_number(
    main_checkout: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    git(main_checkout, "push", "-q", "origin", f"{BASE}:refs/heads/{OLD_BRANCH}")
    git(main_checkout, "fetch", "-q", "origin")  # the checkout has seen it
    delete_a_branch_from_a_second_clone(main_checkout, OLD_BRANCH)

    code = tree.main(["tree", "--brief", "009"], cwd=main_checkout, sync=Syncs())

    assert code == 0, capsys.readouterr().err
    assert (main_checkout.parent / "project-009").is_dir()


def test_untree_refuses_commits_of_a_branch_that_was_deleted_on_origin(
    main_checkout: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert tree.main(["tree", "--new", NEW_BRANCH], cwd=main_checkout, sync=Syncs()) == 0
    folder = main_checkout.parent / f"project-{NEW_BRANCH}"
    git(folder, "commit", "-q", "--allow-empty", "-m", "pushed, then its branch deleted")
    git(folder, "push", "-q", "-u", "origin", NEW_BRANCH)
    git(main_checkout, "fetch", "-q", "origin")  # the checkout has seen the branch
    delete_a_branch_from_a_second_clone(main_checkout, NEW_BRANCH)

    code = tree.main(["untree", "--branch", NEW_BRANCH], cwd=main_checkout, sync=Syncs())

    assert code == 2
    assert "not on origin" in capsys.readouterr().err
    assert folder.is_dir()


# --- what the second review round found -----------------------------------------------------------


def test_untree_removes_a_tree_that_has_rebuildable_files_below_the_top_level(
    main_checkout: Path, made_tree: Path
) -> None:
    """`.gitignore` ignores these names at any depth, so they are rebuildable at any depth."""
    for name in ("docs/.DS_Store", "tests/.pytest_cache/v/x", "tests/.ruff_cache/x"):
        target = made_tree / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x", "utf-8")

    code = tree.main(["untree", "--brief", "009"], cwd=main_checkout, sync=Syncs())

    assert code == 0
    assert not made_tree.exists()


def test_untree_of_a_tree_whose_folder_was_deleted_by_hand_says_to_prune(
    main_checkout: Path, made_tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    shutil.rmtree(made_tree)

    code = tree.main(["untree", "--brief", "009"], cwd=main_checkout, sync=Syncs())

    assert code == 2
    assert "git worktree prune" in capsys.readouterr().err


def test_tree_for_a_brief_whose_folder_was_deleted_by_hand_says_to_prune(
    main_checkout: Path, made_tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    shutil.rmtree(made_tree)

    code = tree.main(["tree", "--brief", "009"], cwd=main_checkout, sync=Syncs())

    assert code == 2
    assert "git worktree prune" in capsys.readouterr().err


def test_a_catch_up_that_git_refuses_is_a_note_and_the_tree_is_still_synced(
    main_checkout: Path,
    made_tree: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert tree.main(["untree", "--brief", "009"], cwd=main_checkout, sync=Syncs()) == 0
    push_a_commit_from_a_second_clone(main_checkout, BRIEF_BRANCH, "second")

    def refusing_merge(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        if args[:1] == ("merge",) and "--ff-only" in args:
            return subprocess.CompletedProcess(args, 1, "", "fatal: not possible to fast-forward")
        return subprocess.run(
            ["git", "-C", str(cwd), *args], capture_output=True, text=True, check=False, timeout=60
        )

    monkeypatch.setattr("tree._git", refusing_merge)
    syncs = Syncs()

    code = tree.main(["tree", "--brief", "009"], cwd=main_checkout, sync=syncs)

    assert code == 0
    assert syncs.folders == [made_tree]
    assert "could not be brought up to it" in capsys.readouterr().out


# --- what the third review round found ------------------------------------------------------------


def test_a_tree_deleted_by_hand_says_to_prune_whatever_name_the_next_tree_would_have(
    main_checkout: Path, made_tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The invariant: git lists a tree whose folder is gone. It is found before git is asked to
    make another tree for the branch, and the message names the way out, whatever folder the
    lost tree had: here one that neither `BRIEF=` nor `BRANCH=` would have made."""
    assert tree.main(["untree", "--brief", "009"], cwd=main_checkout, sync=Syncs()) == 0
    elsewhere = main_checkout.parent / "somewhere-else"
    git(main_checkout, "worktree", "add", "-q", str(elsewhere), BRIEF_BRANCH)
    shutil.rmtree(elsewhere)

    code = tree.main(["tree", "--brief", "009"], cwd=main_checkout, sync=Syncs())

    err = capsys.readouterr().err
    assert code == 2
    assert "git worktree prune" in err
    assert not (main_checkout.parent / f"project-{NAMED_BRANCH}").exists()


def test_untree_finds_a_tree_whose_head_is_detached_by_its_folder(
    main_checkout: Path, made_tree: Path
) -> None:
    git(made_tree, "checkout", "-q", "--detach")

    code = tree.main(["untree", "--brief", "009"], cwd=main_checkout, sync=Syncs())

    assert code == 0
    assert not made_tree.exists()
    assert BRIEF_BRANCH in git(main_checkout, "branch", "--list", BRIEF_BRANCH)


def test_untree_of_a_detached_tree_still_refuses_a_commit_that_is_on_no_branch_of_origin(
    main_checkout: Path, made_tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    git(made_tree, "checkout", "-q", "--detach")
    git(made_tree, "commit", "-q", "--allow-empty", "-m", "made while detached")

    code = tree.main(["untree", "--brief", "009"], cwd=main_checkout, sync=Syncs())

    assert code == 2
    assert "not on origin" in capsys.readouterr().err
    assert made_tree.is_dir()


def test_a_git_call_that_hangs_is_exit_2_with_a_message_and_makes_no_tree(
    main_checkout: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    real_run = subprocess.run

    def hanging_fetch(
        command: list[str], *, capture_output: bool, text: bool, check: bool, timeout: int
    ) -> subprocess.CompletedProcess[str]:
        if "fetch" in command:
            raise subprocess.TimeoutExpired(command, timeout)
        return real_run(
            command, capture_output=capture_output, text=text, check=check, timeout=timeout
        )

    monkeypatch.setattr(subprocess, "run", hanging_fetch)

    code = tree.main(["tree", "--brief", "009"], cwd=main_checkout, sync=Syncs())

    assert code == 2
    assert "no answer" in capsys.readouterr().err
    assert not (main_checkout.parent / "project-009").exists()
