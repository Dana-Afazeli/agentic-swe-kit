"""kit.py: the ownership manifest covers every file, render() rewrites every knob, init works.

`init` is exercised in a committed copy of the kit's tracked files, which is what "Use this
template" on GitHub hands a new project.
"""

import fnmatch
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import kit
import pytest

from conftest import Leftovers

ROOT = Path(__file__).resolve().parents[2]
ANSWERS = kit.Answers(
    package="demo", base="develop", prefix="unit", maintainer="Ada Lovelace", python="3.13.14"
)
OTHER_PYTHON = kit.Answers(
    package="demo", base="main", prefix="main", maintainer="x", python="3.12.9"
)
# Patterns for files the kit does not have yet; dropped when the files arrive.
FUTURE_PATTERNS = {"tests/prove/*"}

SETTINGS_BEFORE = (
    '"Bash(git switch -c main-:*)",\n'
    '"Bash(git push origin main-:*)",\n'
    '"Bash(gh pr create --base main:*)",\n'
    '"Bash(git push origin main)",\n'
    '"Bash(git push -u origin main)",\n'
    '"Bash(git push origin HEAD:main)",\n'
)
SETTINGS_AFTER = (
    '"Bash(git switch -c unit-:*)",\n'
    '"Bash(git push origin unit-:*)",\n'
    '"Bash(gh pr create --base develop:*)",\n'
    '"Bash(git push origin develop)",\n'
    '"Bash(git push -u origin develop)",\n'
    '"Bash(git push origin HEAD:develop)",\n'
)
PROSE_BEFORE = (
    "Never push to `main`. Branch `main-NNN-slug`: `git switch main-NNN-slug`. The maintainer\n"
    "reads; the maintainer's label. def main(): kitpkg.main, KITPKG_EVAL_BUDGET_USD, origin/main,\n"
    "main-001-x\n"
)
PROSE_AFTER = (
    "Never push to `develop`. Branch `unit-NNN-slug`: `git switch unit-NNN-slug`. Ada Lovelace\n"
    "reads; Ada Lovelace's label. def main(): demo.main, DEMO_EVAL_BUDGET_USD, origin/develop,\n"
    "unit-001-x\n"
)


# ---------------------------------------------------------------------------- ownership


def test_every_tracked_file_has_an_owner() -> None:
    unowned = [path for path in kit.tracked_files(ROOT) if kit.category(path) is None]
    assert unowned == []


def test_every_ownership_pattern_names_a_file() -> None:
    tracked = kit.tracked_files(ROOT)
    for _name, patterns in kit.CATEGORIES:
        for pattern in patterns:
            if pattern in FUTURE_PATTERNS:
                continue
            assert any(fnmatch.fnmatchcase(path, pattern) for path in tracked), pattern


def test_the_categories_are_what_the_harness_doc_says() -> None:
    assert kit.category("scripts/guard_bash.py") == "kit-owned"
    assert kit.category("docs/kit/PHILOSOPHY.md") == "kit-owned"
    # the template is kit-owned; the kit's own records are kit-only
    assert kit.category("docs/decisions/0000-TEMPLATE.md") == "kit-owned"
    assert kit.category("docs/decisions/0001-template-repo-with-its-own-updater.md") == "kit-only"
    assert kit.category("pyproject.toml") == "mixed"
    assert kit.category("src/kitpkg/core/text.py") == "project-owned"
    assert kit.category("README.md") == "kit-only"
    assert kit.category("tests/harness/test_kit.py") == "kit-only"  # before `tests/harness/*`
    assert kit.category("tests/harness/test_knobs.py") == "kit-owned"
    assert (
        kit.render_text("kit.py", "PLACEHOLDER kitpkg main", ANSWERS) == "PLACEHOLDER kitpkg main"
    )
    assert kit.is_managed("Makefile") and kit.is_managed("pyproject.toml")
    assert not kit.is_managed("project.mk") and not kit.is_managed("CHANGELOG.md")


def test_every_seed_source_is_tracked_and_kit_only() -> None:
    tracked = set(kit.tracked_files(ROOT))
    for source in kit.SEEDS:
        assert source in tracked, source
        assert kit.category(source) == "kit-only", source


# ---------------------------------------------------------------------------- render


@pytest.mark.parametrize(
    ("path", "text", "expected"),
    [
        (".python-version", "3.13.12\n", "3.13.14\n"),
        (
            "scripts/stop_gate.py",
            'BASE_BRANCH = "main"  # knob: base\nx = "main"\n',
            'BASE_BRANCH = "develop"  # knob: base\nx = "main"\n',
        ),
        (
            "scripts/review.py",
            'BRANCH_PREFIX = "main"  # knob: prefix — unit branches are `<prefix>-NNN-slug`\n',
            'BRANCH_PREFIX = "unit"  # knob: prefix — unit branches are `<prefix>-NNN-slug`\n',
        ),
        (
            ".github/workflows/ci.yml",
            "    branches: [main] # knob: base\n",
            "    branches: [develop] # knob: base\n",
        ),
        (".claude/settings.json", SETTINGS_BEFORE, SETTINGS_AFTER),
        ("AGENTS.md", PROSE_BEFORE, PROSE_AFTER),
        ("README.md", "git switch -c main-kit-update\n", "git switch -c unit-kit-update\n"),
        (
            "scripts/review.py",
            'WORK = Path(tempfile.gettempdir()) / "kitpkg-review"  # knob: package\n',
            'WORK = Path(tempfile.gettempdir()) / "demo-review"  # knob: package\n',
        ),
        (
            "docs/x.md",
            "a maintainer, the maintainers, maintainer\n",
            "a maintainer, the maintainers, maintainer\n",
        ),
        (
            "scripts/guard_bash.py",
            'LABEL_MESSAGE = "labels are the maintainer\'s"  # kitpkg\n',
            'LABEL_MESSAGE = "labels are the maintainer\'s"  # demo\n',
        ),
        (
            "docs/x.md",
            "kitpkgs kitpkg_x x_kitpkg kitpkg.core `kitpkg`\n",
            "kitpkgs kitpkg_x x_kitpkg demo.core `demo`\n",
        ),
    ],
)
def test_render_text_rewrites_the_knob_sites_and_nothing_else(
    path: str, text: str, expected: str
) -> None:
    assert kit.render_text(path, text, ANSWERS) == expected


def test_render_text_moves_the_python_bounds_with_the_minor_version() -> None:
    text = (
        'requires-python = ">=3.13,<3.14" # knob: python\n'
        'pythonVersion = "3.13" # knob: python\n'
        'v = "3.13"\n'
    )
    assert kit.render_text("pyproject.toml", text, OTHER_PYTHON) == (
        'requires-python = ">=3.12,<3.13" # knob: python\n'
        'pythonVersion = "3.12" # knob: python\n'
        'v = "3.13"\n'
    )
    assert kit.render_text("pyproject.toml", text, ANSWERS) == text  # same minor: unchanged


def test_rendering_with_the_kits_own_values_changes_nothing() -> None:
    for path in kit.tracked_files(ROOT):
        text = (ROOT / path).read_text("utf-8")
        assert kit.render_text(path, text, kit.PLACEHOLDER) == text, path


def test_render_path_renames_the_sample_package_only() -> None:
    assert kit.render_path("src/kitpkg/core/text.py", ANSWERS) == "src/demo/core/text.py"
    assert kit.render_path("tests/test_text.py", ANSWERS) == "tests/test_text.py"
    assert kit.render_path("src/kitpkg/core/text.py", kit.PLACEHOLDER) == "src/kitpkg/core/text.py"


@pytest.mark.parametrize(
    ("field", "value", "fragment"),
    [
        ("package", "1abc", "not a Python identifier"),
        ("package", "class", "not a Python identifier"),
        ("package", "kitpkg", "placeholder"),
        ("package", "Demo", "lowercase"),
        ("base", "a b", "not a branch name"),
        ("prefix", "-x", "not a branch name"),
        ("python", "3.13", "not X.Y.Z"),
        ("maintainer", " ", "empty"),
    ],
)
def test_answers_are_validated(field: str, value: str, fragment: str) -> None:
    answers = kit.Answers(**{**ANSWERS.__dict__, field: value})
    problems = answers.validate()
    assert len(problems) == 1 and fragment in problems[0], problems


def test_minor_versions() -> None:
    assert ANSWERS.minor == "3.13" and ANSWERS.next_minor == "3.14"
    assert OTHER_PYTHON.minor == "3.12" and OTHER_PYTHON.next_minor == "3.13"


def test_the_lock_round_trips(tmp_path: Path) -> None:
    kit.write_lock(tmp_path, ANSWERS)
    version, answers = kit.read_lock(tmp_path)
    assert (version, answers) == (kit.KIT_VERSION, ANSWERS)
    data = tomllib.loads((tmp_path / kit.LOCK).read_text("utf-8"))
    assert data["kit"]["repo"] == kit.KIT_REPO


def test_label_descriptions_fit_githubs_limit() -> None:
    assert all(len(description) <= 100 for _name, _color, description in kit.LABELS)


def test_the_changelog_has_a_section_for_the_kit_version() -> None:
    changelog = (ROOT / "CHANGELOG.md").read_text("utf-8")
    assert "## Unreleased" in changelog or f"## v{kit.KIT_VERSION}" in changelog


# ---------------------------------------------------------------------------- init, in a copy


def git(cwd: Path, *args: str) -> str:
    identity = ["-c", "user.name=t", "-c", "user.email=t@example.invalid"]
    quiet = ["-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null"]
    result = subprocess.run(
        ["git", *identity, *quiet, *args], cwd=cwd, check=True, capture_output=True, text=True
    )
    return result.stdout


def files_of(root: Path) -> list[str]:
    return sorted(
        str(p.relative_to(root)) for p in root.rglob("*") if p.is_file() and ".git" not in p.parts
    )


@pytest.fixture
def copy_of_the_kit(tmp_path: Path) -> Path:
    """The kit's tracked files, committed in a repository of their own."""
    copy = tmp_path / "project"
    for path in kit.tracked_files(ROOT):
        target = copy / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / path, target)
    git(copy, "init", "-q", "-b", "main")
    git(copy, "add", "-A")
    git(copy, "commit", "-q", "-m", "Initial commit")
    return copy


def kit_py(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "kit.py", *args], cwd=cwd, capture_output=True, text=True, check=False
    )


def test_init_renders_seeds_removes_and_writes_the_lock(
    copy_of_the_kit: Path, leftovers: Leftovers
) -> None:
    result = kit_py(
        copy_of_the_kit, "init", "--package", "demo", "--maintainer", "Ada Lovelace", "--no-sync"
    )
    assert result.returncode == 0, result.stdout + result.stderr

    present = files_of(copy_of_the_kit)
    assert "src/demo/core/text.py" in present
    assert not any(p.startswith("src/kitpkg/") for p in present)
    gone = (
        "CHANGELOG.md",
        "LICENSE",
        "docs/templates/README.md",
        "docs/decisions/0001-template-repo-with-its-own-updater.md",
    )
    for path in gone:
        assert path not in present, path
    seeded = (
        "README.md",
        "docs/DELTAS.md",
        "docs/ROADMAP.md",
        "docs/FRICTION.md",
        "docs/BACKLOG.md",
        "docs/kit/LICENSE",
        "docs/decisions/0000-TEMPLATE.md",
        kit.LOCK,
    )
    for path in seeded:
        assert path in present, path
    assert (copy_of_the_kit / "README.md").read_text("utf-8").startswith("# demo\n")
    assert (copy_of_the_kit / "docs/FRICTION.md").read_text("utf-8").startswith("# Friction log\n")

    version, answers = kit.read_lock(copy_of_the_kit)
    assert version == kit.KIT_VERSION
    assert answers == kit.Answers(
        package="demo", base="main", prefix="main", maintainer="Ada Lovelace", python="3.13.12"
    )

    pyproject = tomllib.loads((copy_of_the_kit / "pyproject.toml").read_text("utf-8"))
    assert pyproject["project"]["name"] == "demo"
    assert pyproject["tool"]["mutmut"]["source_paths"] == ["src/demo"]
    assert "kitpkg" not in (copy_of_the_kit / "tests/test_skeleton.py").read_text("utf-8")

    scanned = [p for p in present if p != kit.LOCK]
    verbatim = ("uv.lock", *kit.VERBATIM)  # re-locked; the tool's own constants
    assert leftovers(copy_of_the_kit, scanned, ("kitpkg", "KITPKG"), verbatim) == []
    # the maintainer's name is in the documents and rules; hook messages keep the role phrase
    phrase = ("the maintainer", "The maintainer")
    assert leftovers(copy_of_the_kit, scanned, phrase, (*verbatim, "*.py")) == []
    assert "Next steps for Ada Lovelace:" in result.stdout


def test_init_with_another_base_and_prefix_rewrites_the_rules(copy_of_the_kit: Path) -> None:
    result = kit_py(
        copy_of_the_kit,
        "init",
        "--package",
        "demo",
        "--base",
        "develop",
        "--branch-prefix",
        "unit",
        "--no-sync",
    )
    assert result.returncode == 0, result.stdout + result.stderr

    def text(path: str) -> str:
        return (copy_of_the_kit / path).read_text("utf-8")

    assert '"Bash(git switch -c unit-:*)"' in text(".claude/settings.json")
    assert '"Bash(gh pr create --base develop:*)"' in text(".claude/settings.json")
    assert 'BASE_BRANCH = "develop"  # knob: base' in text("scripts/stop_gate.py")
    assert 'BRANCH_PREFIX = "unit"  # knob: prefix' in text("scripts/review.py")
    assert "branches: [develop] # knob: base" in text(".github/workflows/ci.yml")
    assert "`unit-NNN-slug`" in text("AGENTS.md")


def test_init_refuses_an_invalid_package_a_dirty_tree_and_a_second_run(
    copy_of_the_kit: Path,
) -> None:
    bad = kit_py(copy_of_the_kit, "init", "--package", "Demo", "--no-sync")
    assert bad.returncode == 2 and "lowercase" in bad.stdout

    (copy_of_the_kit / "README.md").write_text("changed\n", "utf-8")
    dirty = kit_py(copy_of_the_kit, "init", "--package", "demo", "--no-sync")
    assert dirty.returncode == 2 and "not clean" in dirty.stdout
    git(copy_of_the_kit, "checkout", "--", "README.md")

    assert kit_py(copy_of_the_kit, "init", "--package", "demo", "--no-sync").returncode == 0
    git(copy_of_the_kit, "add", "-A")
    git(copy_of_the_kit, "commit", "-q", "-m", "init")
    again = kit_py(copy_of_the_kit, "init", "--package", "demo", "--no-sync")
    assert again.returncode == 2 and "initialised already" in again.stdout


def test_render_into_another_directory_leaves_the_kit_alone(
    copy_of_the_kit: Path, tmp_path: Path
) -> None:
    into = tmp_path / "rendered"
    result = kit_py(copy_of_the_kit, "render", "--package", "demo", "--into", str(into))
    assert result.returncode == 0, result.stdout + result.stderr
    assert (into / "src/demo/main.py").is_file() and (into / kit.LOCK).is_file()
    assert not (into / "CHANGELOG.md").exists()
    assert git(copy_of_the_kit, "status", "--porcelain") == ""
