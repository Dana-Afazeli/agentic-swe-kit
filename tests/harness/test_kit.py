"""kit.py: the ownership manifest covers every file, render() rewrites every knob, init works.

`init` is exercised in a committed copy of the kit's tracked files, which is what "Use this
template" on GitHub hands a new project. Kit-only: the kit's tree is what it tests.
"""

import fnmatch
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import kit
import pytest
from test_knobs import check_all

import conftest
import stop_gate
from conftest import REPO_ROOT

ROOT = REPO_ROOT
ANSWERS = kit.Answers(
    package="demo", base="develop", prefix="unit", maintainer="Ada Lovelace", python="3.13.14"
)
LONG_NAMES = kit.Answers(
    package="demo",
    base="release/2026-stable",
    prefix="feature/units",
    maintainer="Ada Lovelace",
    python="3.13.14",
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


def scan_for(
    root: Path, paths: list[str], tokens: tuple[str, ...], allow: tuple[str, ...]
) -> list[str]:
    """`path:line: token` for every token found in a file not covered by `allow` — in any case and
    inside identifiers too (a token inside a test name is a leftover). URLs are stripped first: the
    kit's own address names its owner."""
    found: list[str] = []
    lowered = [token.lower() for token in tokens]
    for path in paths:
        if any(fnmatch.fnmatchcase(path, pattern) for pattern in allow):
            continue
        text = re.sub(r"https?://\S+", "", (root / path).read_text("utf-8", errors="replace"))
        for number, line in enumerate(text.splitlines(), 1):
            low = line.lower()
            found.extend(f"{path}:{number}: {token}" for token in lowered if token in low)
    return found


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
    assert kit.category("tests/harness/test_no_leftovers.py") == "kit-only"
    assert kit.category("tests/harness/test_knobs.py") == "kit-owned"
    assert kit.is_managed("Makefile") and kit.is_managed("pyproject.toml")
    assert not kit.is_managed("project.mk") and not kit.is_managed("CHANGELOG.md")


def test_a_projects_own_additions_are_not_the_kits() -> None:
    """The manifest names the kit's files. What a project adds beside them — its own workflow, its
    skills, its decisions — is nobody's but the project's (HARNESS.md §9: add, don't edit)."""
    assert kit.category(".github/workflows/ci.yml") == "kit-owned"
    assert kit.category(".github/actions/base/action.yml") == "kit-owned"
    assert kit.category(".claude/skills/implementer/assets/pr-page.md") == "kit-owned"
    assert kit.category(".claude/skills/implementer/scripts/pr.py") == "kit-owned"
    assert kit.category(".github/workflows/project.yml") is None
    assert not kit.is_managed(".github/workflows/project.yml")
    assert not kit.is_managed("docs/decisions/0008-our-own.md")
    assert not kit.is_managed("docs/briefs/002-our-brief.md")


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
            '    branches: ["main"] # knob: base\n',
            '    branches: ["develop"] # knob: base\n',
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
            "docs/x.md",
            "kitpkgs kitpkg_x x_kitpkg kitpkg.core `kitpkg`\n",
            "kitpkgs kitpkg_x x_kitpkg demo.core `demo`\n",
        ),
        # prose only: the role phrase, and the branch names, never change a .py file's lines
        # beyond its knob lines (a rename must not reformat code, nor break a test's own data)
        (
            "scripts/guard_bash.py",
            'LABEL_MESSAGE = "labels are the maintainer\'s"  # kitpkg\n',
            'LABEL_MESSAGE = "labels are the maintainer\'s"  # demo\n',
        ),
        (
            "tests/harness/test_review.py",
            'base="main"; "origin/main"; "HEAD:main"; "`main`"; "main-001-x"\n',
            'base="main"; "origin/main"; "HEAD:main"; "`main`"; "main-001-x"\n',
        ),
        # the role phrase wrapped over a line end in hard-wrapped prose
        ("docs/x.md", "what the\nmaintainer's label says\n", "what Ada Lovelace's label says\n"),
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


@pytest.mark.parametrize("answers", [ANSWERS, LONG_NAMES], ids=["short", "long"])
def test_kit_owned_python_changes_only_on_knob_lines(answers: kit.Answers) -> None:
    """Whatever the names, a kit-owned .py file differs from the kit only on `# knob:` lines, so a
    rename cannot change how it is formatted or what its test data means."""
    for path in kit.tracked_files(ROOT):
        if not path.endswith(".py") or kit.category(path) != "kit-owned":
            continue
        before = (ROOT / path).read_text("utf-8").splitlines()
        after = kit.render_text(path, "\n".join(before) + "\n", answers).splitlines()
        assert len(before) == len(after), path
        changed = [b for b, a in zip(before, after, strict=True) if b != a]
        assert all("# knob:" in line for line in changed), (path, changed)


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
        ("package", "kit", "shadow"),  # kit.py and the gate scripts come first on pytest's path
        ("package", "review", "shadow"),
        ("package", "conftest", "shadow"),
        ("package", "calendar", "shadow"),  # the standard library comes before src/ as well
        ("package", "json", "shadow"),
        ("base", "a b", "not a branch name"),
        ("base", "a..b", "not a branch name"),  # git refuses it
        ("base", "x.lock", "not a branch name"),
        ("base", 'a"b', "not a branch name"),  # git accepts; a Python string and JSON would not
        ("base", "a,b", "not a branch name"),  # git accepts; YAML's [a,b] is two branches
        ("base", "rel$(id)", "not a branch name"),
        ("prefix", "-x", "not a branch name"),
        ("prefix", "develop/unit", "under the base"),  # git cannot create develop/unit-001
        ("package", "_demo", "project name"),  # a Python identifier, not a project name for uv
        ("package", "demo_", "project name"),
        ("package", "café", "project name"),
        ("python", "3.13", "not X.Y.Z"),
        ("maintainer", " ", "empty"),
        ("maintainer", 'Sam "S"', "quote"),  # the name lands inside echo "…" lines of ci.yml
        ("maintainer", "a`b", "quote"),
        ("maintainer", "a$b", "quote"),
    ],
)
def test_answers_are_validated(field: str, value: str, fragment: str) -> None:
    answers = kit.Answers(**{**ANSWERS.__dict__, field: value})
    problems = answers.validate()
    assert len(problems) == 1 and fragment in problems[0], problems


def test_long_branch_names_are_valid_answers() -> None:
    assert LONG_NAMES.validate() == []


def test_minor_versions() -> None:
    assert ANSWERS.minor == "3.13" and ANSWERS.next_minor == "3.14"
    assert OTHER_PYTHON.minor == "3.12" and OTHER_PYTHON.next_minor == "3.13"


@pytest.mark.parametrize("maintainer", ["Ada Lovelace", "𠮷田 太郎", "Zoë 😀"])
def test_the_lock_round_trips(tmp_path: Path, maintainer: str) -> None:
    answers = kit.Answers(**{**ANSWERS.__dict__, "maintainer": maintainer})
    kit.write_lock(tmp_path, answers)
    lock = kit.read_lock(tmp_path)
    version, read_back = lock.version, lock.answers
    assert (version, read_back) == (kit.KIT_VERSION, answers)
    data = tomllib.loads((tmp_path / kit.LOCK).read_text("utf-8"))
    assert data["kit"]["repo"] == kit.KIT_REPO


def test_label_descriptions_fit_githubs_limit() -> None:
    assert all(len(description) <= 100 for _name, _color, description in kit.LABELS)


def test_the_changelog_has_a_section_for_the_kit_version() -> None:
    changelog = (ROOT / "CHANGELOG.md").read_text("utf-8")
    assert "## Unreleased" in changelog or f"## v{kit.KIT_VERSION}" in changelog


def test_repo_root_ignores_gits_location_variables(tmp_path: Path) -> None:
    here = ROOT / "tests" / "harness"
    assert conftest.repo_root({"GIT_DIR": str(ROOT / ".git")}, here) == ROOT
    (tmp_path / "tests" / "harness").mkdir(parents=True)  # no repository: the layout decides
    assert conftest.repo_root({}, tmp_path / "tests" / "harness") == tmp_path


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


def kit_py(
    cwd: Path, *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "kit.py", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def path_with_only(tmp_path: Path, *programs: str) -> dict[str, str]:
    """An environment whose PATH holds only the named programs (as links to the real ones)."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    for program in programs:
        real = shutil.which(program)
        assert real, program
        (bin_dir / program).symlink_to(real)
    return {**os.environ, "PATH": str(bin_dir)}


def test_init_renders_seeds_removes_and_writes_the_lock(copy_of_the_kit: Path) -> None:
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
        "docs/research/2026-10-05-review-model-and-effort.md",
        "docs/MAINTAINING.md",
        "tests/harness/test_kit.py",
        "tests/harness/test_no_leftovers.py",
        "tests/harness/test_stateless.py",
    )
    for path in gone:
        assert path not in present, path
    for place in ("docs/briefs/.gitkeep", "docs/research/.gitkeep"):  # the project's own, empty
        assert place in present, place
        assert (copy_of_the_kit / place).stat().st_size == 0, place
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
    assert git(copy_of_the_kit, "diff", "--name-only") == ""  # everything init did is staged
    assert "kit.lock" in git(copy_of_the_kit, "diff", "--cached", "--name-only")

    lock = kit.read_lock(copy_of_the_kit)
    version, answers = lock.version, lock.answers
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
    assert scan_for(copy_of_the_kit, scanned, ("kitpkg",), verbatim) == []
    # the maintainer's name is in the documents and rules; hook messages keep the role phrase, and
    # so do the skills (they name no person: AGENTS.md's Roles section says who the maintainer is)
    allowed = (*verbatim, "*.py", ".claude/skills/*")
    hits = scan_for(copy_of_the_kit, scanned, ("the maintainer",), allowed)
    # in backticks the phrase is the skills' term for the role, left as it is (`_maintainer`)
    outside_code = [
        hit
        for hit in hits
        for path, number, _ in [hit.split(":", 2)]
        for line in [(copy_of_the_kit / path).read_text("utf-8").splitlines()[int(number) - 1]]
        if "the maintainer" in re.sub(r"`[^`\n]*`", "", line).lower()
    ]
    assert outside_code == []
    agents = (copy_of_the_kit / "AGENTS.md").read_text("utf-8")
    assert "`the maintainer` is Ada Lovelace" in agents  # the term in backticks, then the name
    assert agents.count("the maintainer") == 1
    check_all(copy_of_the_kit)  # every knob's sites agree in the project too
    assert "Next steps for Ada Lovelace:" in result.stdout
    assert "make prove" not in result.stdout  # no such target yet


def test_init_with_another_base_and_prefix_rewrites_the_rules(copy_of_the_kit: Path) -> None:
    options = ("--package", "demo", "--base", "develop", "--branch-prefix", "unit", "--no-sync")
    result = kit_py(copy_of_the_kit, "init", *options)
    assert result.returncode == 0, result.stdout + result.stderr

    def text(path: str) -> str:
        return (copy_of_the_kit / path).read_text("utf-8")

    assert '"Bash(git switch -c unit-:*)"' in text(".claude/settings.json")
    assert '"Bash(gh pr create --base develop:*)"' in text(".claude/settings.json")
    assert 'BASE_BRANCH = "develop"  # knob: base' in text("scripts/stop_gate.py")
    assert 'BRANCH_PREFIX = "unit"  # knob: prefix' in text("scripts/review.py")
    assert 'branches: ["develop"] # knob: base' in text(".github/workflows/ci.yml")
    assert "`unit-NNN-slug`" in text("AGENTS.md")
    check_all(copy_of_the_kit)


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
    git(copy_of_the_kit, "commit", "-q", "-m", "init")
    again = kit_py(copy_of_the_kit, "init", "--package", "demo", "--no-sync")
    assert again.returncode == 2 and "initialised already" in again.stdout
    # and `render` is the kit's dry run, not a project's
    rendered = kit_py(copy_of_the_kit, "render", "--package", "zz", "--into", "x")
    assert rendered.returncode == 2 and "a project" in rendered.stdout


def test_a_missing_program_is_a_sentence_not_a_traceback(
    copy_of_the_kit: Path, tmp_path: Path
) -> None:
    env = path_with_only(tmp_path, "git")  # no uv, no make, no gh
    result = kit_py(copy_of_the_kit, "init", "--package", "demo", env=env)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "Traceback" not in result.stderr
    assert "uv is not installed" in result.stdout
    assert "Next steps for the maintainer:" in result.stdout
    assert git(copy_of_the_kit, "diff", "--name-only") == ""  # staged all the same

    labels = kit_py(copy_of_the_kit, "labels", env=env)
    assert labels.returncode == 1 and "gh is not installed" in labels.stdout
    assert "Traceback" not in labels.stderr


def test_render_into_another_directory_leaves_the_kit_alone(
    copy_of_the_kit: Path, tmp_path: Path
) -> None:
    into = tmp_path / "rendered"
    result = kit_py(copy_of_the_kit, "render", "--package", "demo", "--into", str(into))
    assert result.returncode == 0, result.stdout + result.stderr
    assert (into / "src/demo/main.py").is_file() and (into / kit.LOCK).is_file()
    assert not (into / "CHANGELOG.md").exists()
    assert git(copy_of_the_kit, "status", "--porcelain") == ""


def test_a_rendered_projects_harness_tests_pass_with_other_names(tmp_path: Path) -> None:
    """The kit-owned tests are rendered into every project and run in its gate, so they must hold
    for any names: a test whose data spells the kit's base or prefix is red there and green here.
    `render_tree` with long branch names into a repository of its own, then the harness tests
    there with this interpreter (no `uv sync`: those tests import no package)."""
    rendered = tmp_path / "rendered"
    kit.render_tree(ROOT, rendered, LONG_NAMES, kit.tracked_files(ROOT))
    kit.write_lock(rendered, LONG_NAMES)
    git(rendered, "init", "-q", "-b", LONG_NAMES.base)
    git(rendered, "add", "-A")
    git(rendered, "commit", "-q", "-m", "rendered")
    # the modules whose data names a branch or reads a knob; the guard's 600 cases and the
    # integrity tests build their own repositories and are not worth the 20 s here
    modules = [
        "test_stop_gate.py",
        "test_review.py",
        "test_knobs.py",
        "test_gate_lists.py",
        # the role skills are the same text in every project; pr.py reads the page's headings
        "test_roles.py",
        "test_pr.py",
        "test_role_skills.py",
    ]
    # with the reviewer-clone marker set, as in a reviewer's own `make check`: the fixture in the
    # rendered conftest removes it, so the Stop gate's tests there still see the gate
    env = {**os.environ, stop_gate.REVIEWER_CLONE_VARIABLE: "1"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            *(f"tests/harness/{m}" for m in modules),
            "-q",
            "-x",
            "-p",
            "no:cacheprovider",
        ],
        cwd=rendered,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-1000:]


def test_render_text_leaves_the_skills_alone_and_renders_the_roles_line() -> None:
    """Skills name no person and no project, so that they are the same text in every project and
    in the source they came from; `AGENTS.md`'s Roles section is where a project's names go, with
    the skills' two terms in backticks, which the renderer leaves alone."""
    skills = sorted(p for p in kit.tracked_files(ROOT) if p.startswith(".claude/skills/"))
    assert len(skills) > 10
    for path in skills:
        text = (ROOT / path).read_text("utf-8")
        assert kit.render_text(path, text, LONG_NAMES) == text, path
    roles = (ROOT / "AGENTS.md").read_text("utf-8").split("\n## ")[1]
    rendered = kit.render_text("AGENTS.md", roles, LONG_NAMES)
    assert "`the maintainer` is Ada Lovelace" in rendered
    assert "`the base branch` is `release/2026-stable`" in rendered
    assert "`feature/units-NNN-slug`" in rendered


@pytest.mark.parametrize("fence", ["```", "~~~"])
def test_the_maintainer_is_renamed_after_a_fenced_block_and_kept_in_backticks(fence: str) -> None:
    """A fence of three backticks must not be taken for inline code: the prose after it is prose."""
    prose = "Then ask the maintainer to merge; `the maintainer` is a term."
    text = f"{fence}\nmake check\n{fence}\n{prose}\n"

    rendered = kit.render_text("docs/x.md", text, LONG_NAMES)

    assert "Then ask Ada Lovelace to merge; `the maintainer` is a term." in rendered


def test_render_refuses_the_kit_itself_and_a_folder_without_a_repository(
    copy_of_the_kit: Path, tmp_path: Path
) -> None:
    before = files_of(copy_of_the_kit)
    into_self = kit_py(copy_of_the_kit, "render", "--package", "demo", "--into", ".")
    assert into_self.returncode == 2 and "into the kit itself" in into_self.stdout
    into_sub = kit_py(copy_of_the_kit, "render", "--package", "demo", "--into", "out")
    assert into_sub.returncode == 2 and "into the kit itself" in into_sub.stdout
    assert (
        files_of(copy_of_the_kit) == before and git(copy_of_the_kit, "status", "--porcelain") == ""
    )

    alone = tmp_path / "alone"
    alone.mkdir()
    shutil.copyfile(ROOT / "kit.py", alone / "kit.py")
    result = kit_py(alone, "render", "--package", "demo", "--into", str(tmp_path / "out"))
    assert result.returncode == 2 and "Traceback" not in result.stderr
    assert "clone of the kit" in result.stdout


def test_inits_own_lines_come_before_the_output_of_the_tools_it_runs(
    copy_of_the_kit: Path, tmp_path: Path
) -> None:
    """`say()` flushes: with stdout redirected to a file — the saved proof the PR template asks
    for — the line that names a step stands before that step's output, not after it."""
    env = path_with_only(tmp_path, "git")
    fake_uv = tmp_path / "bin" / "uv"
    fake_uv.write_text('#!/bin/sh\necho "FAKE-UV $*"\n', "utf-8")
    fake_uv.chmod(0o755)
    result = kit_py(copy_of_the_kit, "init", "--package", "demo", env=env)
    assert result.returncode == 1, result.stdout + result.stderr  # make is not installed
    out = result.stdout
    assert out.index("kit: uv lock") < out.index("FAKE-UV lock")
    assert out.index("FAKE-UV lock") < out.index("kit: uv sync")
    assert "make is not installed" in out


def test_no_sentence_points_at_a_command_this_kit_py_does_not_have(
    copy_of_the_kit: Path, tmp_path: Path
) -> None:
    """A message that names `kit.py update` while the parser has no such command sends the reader
    to an argparse error (the resolved `make prove` thread, at other sites)."""
    usage = kit_py(copy_of_the_kit, "--help").stdout  # "{init,render,labels}" in the usage line
    match = re.search(r"\{([^}]+)\}", usage)
    assert match, usage
    choices = set(match[1].split(","))
    first = kit_py(copy_of_the_kit, "init", "--package", "demo", "--no-sync")
    assert first.returncode == 0
    git(copy_of_the_kit, "commit", "-q", "-m", "init")
    again = kit_py(copy_of_the_kit, "init", "--package", "demo", "--no-sync").stdout
    labels = kit_py(copy_of_the_kit, "labels", env=path_with_only(tmp_path, "git")).stdout
    lock = (copy_of_the_kit / kit.LOCK).read_text("utf-8")
    for named in re.findall(r"kit\.py (\w+)", first.stdout + again + labels + lock):
        assert named in choices, (named, choices)
    # and the next steps say where the init commit goes: straight to the base branch, because the
    # template commit is not yet the project and a PR would show the kit's own tests as vanished
    assert "straight to `main`" in first.stdout


def test_init_and_render_work_in_a_linked_worktree(copy_of_the_kit: Path, tmp_path: Path) -> None:
    """In a worktree (what `isolation: worktree` gives an agent), a submodule or a separate git
    dir, `.git` is a file, not a directory; the check is for a repository, not for a folder."""
    worktree = tmp_path / "worktree"
    git(copy_of_the_kit, "worktree", "add", "-q", "-b", "wt", str(worktree))
    assert (worktree / ".git").is_file()
    rendered = kit_py(worktree, "render", "--package", "demo", "--into", str(tmp_path / "out"))
    assert rendered.returncode == 0, rendered.stdout + rendered.stderr
    initialised = kit_py(worktree, "init", "--package", "demo", "--no-sync")
    assert initialised.returncode == 0, initialised.stdout + initialised.stderr


# ---------------------------------------------------------------------------- update


def test_version_key_and_changelog_between() -> None:
    assert kit.version_key("v0.2.0") == (0, 2, 0) and kit.version_key("0.10.3") == (0, 10, 3)
    assert kit.version_key("main") is None and kit.version_key("v1.2") is None
    changelog = (
        "# Changelog\n\n## Unreleased\n\n- not yet\n\n## v0.3.0 — later\n\n- three\n\n"
        "## v0.2.0 — 2026-10-07\n\n### Changed\n- ruff selects C4.\n\n## v0.1.0\n\n- one\n"
    )
    assert kit.changelog_between(changelog, "0.1.0", "0.2.0") == (
        "## v0.2.0 — 2026-10-07\n\n### Changed\n- ruff selects C4."
    )
    assert "- three" in kit.changelog_between(changelog, "0.1.0", "0.3.0")
    assert "not yet" not in kit.changelog_between(changelog, "0.0.1", "0.3.0")
    assert kit.changelog_between(changelog, "0.2.0", "0.2.0") == ""


@pytest.fixture(scope="module")
def kit_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A kit repository with two releases: v0.1.0 (this tree) and v0.2.0 (a changed script, a new
    document, a removed one, a changed lint rule, a changelog entry, the version bumped)."""
    repo = tmp_path_factory.mktemp("kit") / "repo"
    for path in kit.tracked_files(ROOT):
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / path, target)
    (repo / "docs/kit/OLD.md").write_text("# Old\n\nFor kitpkg: gone in 0.2.0.\n", "utf-8")
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "v0.1.0")
    git(repo, "tag", "v0.1.0")

    fmt_hook = repo / "scripts" / "fmt_hook.py"
    fmt_hook.write_text(
        fmt_hook.read_text("utf-8") + "\n# a line the kit added in 0.2.0\n", "utf-8"
    )
    (repo / "docs/kit/NEW.md").write_text(
        "# New in 0.2.0\n\nFor kitpkg, by the maintainer.\n", "utf-8"
    )
    (repo / "docs/kit/OLD.md").unlink()
    pyproject = repo / "pyproject.toml"
    old_select = 'select = ["E", "F", "I", "UP", "B", "SIM", "RUF"]'
    assert old_select in pyproject.read_text("utf-8")
    pyproject.write_text(
        pyproject.read_text("utf-8").replace(old_select, old_select[:-1] + ', "C4"]'), "utf-8"
    )
    kit_py_file = repo / "kit.py"
    kit_py_file.write_text(
        kit_py_file.read_text("utf-8").replace('KIT_VERSION = "0.1.0"', 'KIT_VERSION = "0.2.0"'),
        "utf-8",
    )
    changelog = repo / "CHANGELOG.md"
    changelog.write_text(
        changelog.read_text("utf-8").replace(
            "## Unreleased",
            "## v0.2.0 — 2026-10-07\n\n### Changed\n- ruff selects C4.\n\n## Unreleased",
        ),
        "utf-8",
    )
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "v0.2.0")
    git(repo, "tag", "v0.2.0")

    # a branch one commit ahead of v0.2.0 (a target by name), then v0.3.0 on main: a new kit-owned
    # pattern in its own kit.py with a file under it, and an executable script
    git(repo, "switch", "-q", "-c", "feature")
    (repo / "docs/kit/FEATURE.md").write_text("# On the feature branch\n", "utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "feature")
    git(repo, "switch", "-q", "main")
    kit_py_file.write_text(
        kit_py_file.read_text("utf-8")
        .replace('KIT_VERSION = "0.2.0"', 'KIT_VERSION = "0.3.0"')
        .replace(
            '    "kit.py",\n    "Makefile",\n', '    "kit.py",\n    "Makefile",\n    "extras/*",\n'
        ),
        "utf-8",
    )
    assert '"extras/*"' in kit_py_file.read_text("utf-8")
    (repo / "extras").mkdir()
    (repo / "extras/tool.txt").write_text("a kit-owned extra for kitpkg\n", "utf-8")
    (repo / "scripts/run.sh").write_text("#!/bin/sh\necho kitpkg\n", "utf-8")
    (repo / "scripts/run.sh").chmod(0o755)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "v0.3.0")
    git(repo, "tag", "v0.3.0")
    # and one more commit after the last tag, the same version: a target the default must not undo
    fmt_hook.write_text(fmt_hook.read_text("utf-8") + "# after v0.3.0\n", "utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "after v0.3.0")
    # two branches for what an update must refuse or do: `side`, off v0.1.0 with a lower
    # KIT_VERSION (older by version, not an ancestor); `drop`, off v0.3.0, where the kit removes
    # `extras/tool.txt` and the pattern that named it
    git(repo, "switch", "-q", "-c", "side", "v0.1.0")
    kit_py_file.write_text(
        kit_py_file.read_text("utf-8").replace('KIT_VERSION = "0.1.0"', 'KIT_VERSION = "0.0.9"'),
        "utf-8",
    )
    git(repo, "commit", "-q", "-am", "side: an older version")
    git(repo, "switch", "-q", "-c", "drop", "v0.3.0")
    (repo / "extras/tool.txt").unlink()
    kit_py_file.write_text(
        kit_py_file.read_text("utf-8")
        .replace('KIT_VERSION = "0.3.0"', 'KIT_VERSION = "0.4.0"')
        .replace('    "extras/*",\n', ""),
        "utf-8",
    )
    assert '"extras/*"' not in kit_py_file.read_text("utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "drop: the extras are gone, pattern and file")
    # and a branch that is not a kit at all: kit.py removed
    git(repo, "switch", "-q", "-c", "nokit", "v0.1.0")
    git(repo, "rm", "-q", "kit.py")
    git(repo, "commit", "-q", "-m", "nokit: not a kit")
    git(repo, "switch", "-q", "main")
    return repo


def make_project(kit_repo: Path, where: Path, *answers: str) -> Path:
    """A project made from the kit at v0.1.0 (`init --no-sync`), its lock pointing at `kit_repo`,
    on a branch of its own as `update` wants it."""
    kit.export(kit_repo, "v0.1.0", where)
    git(where, "init", "-q", "-b", "main")
    git(where, "add", "-A")
    git(where, "commit", "-q", "-m", "Initial commit")
    result = kit_py(where, "init", "--package", "demo", *answers, "--no-sync")
    assert result.returncode == 0, result.stdout + result.stderr
    lock = kit.read_lock(where)
    kit.write_lock(where, lock.answers, lock.version, repo=str(kit_repo))
    git(where, "add", "-A")
    git(where, "commit", "-q", "-m", "init")
    git(where, "switch", "-q", "-c", "main-kit-update")
    return where


@pytest.fixture(scope="module")
def templates(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Where the projects the tests copy from are built: a directory of the module's own, so that
    pytest's retention policy for a test's tmp_path cannot take it away."""
    return tmp_path_factory.mktemp("templates")


def project_from(kit_repo: Path, where: Path, templates: Path, *answers: str) -> Path:
    """`make_project`, built once per set of answers and copied: `init` costs a second each time,
    a copy of the result a few milliseconds."""
    template = templates / "-".join(["project", *answers]).replace("/", "_")
    if not template.exists():
        make_project(kit_repo, template, *answers)
    shutil.copytree(template, where, symlinks=True)
    return where


def no_markers(root: Path) -> bool:
    """No conflict marker at the start of a line anywhere (prose may mention one in backticks)."""
    marker = re.compile(r"^<{7} ", re.MULTILINE)
    return not any(
        marker.search((root / p).read_text("utf-8", errors="replace")) for p in files_of(root)
    )


def test_update_merges_adds_removes_and_relocks(
    kit_repo: Path, tmp_path: Path, templates: Path
) -> None:
    project = project_from(kit_repo, tmp_path / "project", templates)
    pyproject = project / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text("utf-8").replace("dependencies = []", 'dependencies = ["httpx"]'),
        "utf-8",
    )
    git(project, "commit", "-q", "-am", "a dependency of our own")

    result = kit_py(project, "update", "--to", "v0.2.0", "--no-sync")
    assert result.returncode == 0, result.stdout + result.stderr

    assert (
        (project / "scripts/fmt_hook.py")
        .read_text("utf-8")
        .endswith("# a line the kit added in 0.2.0\n")
    )
    new = (project / "docs/kit/NEW.md").read_text("utf-8")
    assert "demo" in new and "kitpkg" not in new  # rendered with the project's answers
    assert not (project / "docs/kit/OLD.md").exists()
    merged = pyproject.read_text("utf-8")
    assert '"C4"' in merged and 'dependencies = ["httpx"]' in merged  # both sides
    assert no_markers(project)
    lock = kit.read_lock(project)
    assert lock.version == "0.2.0"
    assert lock.commit == git(kit_repo, "rev-parse", "v0.2.0").strip()
    assert git(project, "diff", "--name-only") == ""  # staged
    assert "## v0.2.0" in result.stdout and "ruff selects C4" in result.stdout
    # kit.py (the version line), fmt_hook.py and pyproject.toml merge
    assert "3 merged, 0 with conflicts, 1 added, 1 removed" in result.stdout
    assert "Next steps for the maintainer:" in result.stdout


def test_update_keeps_a_local_edit_elsewhere_in_a_merged_file(
    kit_repo: Path, tmp_path: Path, templates: Path
) -> None:
    project = project_from(kit_repo, tmp_path / "project", templates)
    fmt_hook = project / "scripts/fmt_hook.py"
    lines = fmt_hook.read_text("utf-8").splitlines(keepends=True)
    lines[0] = '"""Our own first line.\n'
    fmt_hook.write_text("".join(lines), "utf-8")
    git(project, "commit", "-q", "-am", "ours")

    assert kit_py(project, "update", "--to", "v0.2.0", "--no-sync").returncode == 0
    text = fmt_hook.read_text("utf-8")
    assert text.startswith('"""Our own first line.\n') and text.endswith(
        "# a line the kit added in 0.2.0\n"
    )
    assert "<<<<<<<" not in text


def test_update_marks_a_collision_and_still_moves_the_lock(
    kit_repo: Path, tmp_path: Path, templates: Path
) -> None:
    project = project_from(kit_repo, tmp_path / "project", templates)
    fmt_hook = project / "scripts/fmt_hook.py"
    fmt_hook.write_text(fmt_hook.read_text("utf-8") + "\n# our own last line\n", "utf-8")
    git(project, "commit", "-q", "-am", "ours, at the end too")

    result = kit_py(project, "update", "--to", "v0.2.0", "--no-sync")
    assert result.returncode == 1, result.stdout + result.stderr
    text = fmt_hook.read_text("utf-8")
    assert "<<<<<<< yours" in text and ">>>>>>> kit 0.2.0" in text
    assert "conflicts" in result.stdout and "scripts/fmt_hook.py" in result.stdout
    assert "Resolve the conflict markers" in result.stdout
    assert kit.read_lock(project).version == "0.2.0"


def test_update_keeps_a_removed_file_the_project_changed_and_says_so(
    kit_repo: Path, tmp_path: Path, templates: Path
) -> None:
    project = project_from(kit_repo, tmp_path / "project", templates)
    note = project / "docs/kit/OLD.md"
    note.write_text(note.read_text("utf-8") + "\nOur own addition.\n", "utf-8")
    git(project, "commit", "-q", "-am", "ours")

    result = kit_py(project, "update", "--to", "v0.2.0", "--no-sync")
    assert result.returncode == 0
    assert note.is_file()
    assert "kept" in result.stdout and str(note.relative_to(project)) in result.stdout


def test_update_does_not_recreate_a_kit_file_the_project_deleted(
    kit_repo: Path, tmp_path: Path, templates: Path
) -> None:
    project = project_from(kit_repo, tmp_path / "project", templates)
    git(project, "rm", "-q", "docs/kit/SETUP.md")
    git(project, "commit", "-q", "-m", "no setup doc here")

    result = kit_py(project, "update", "--to", "v0.2.0", "--no-sync")
    assert result.returncode == 0
    assert not (project / "docs/kit/SETUP.md").exists()
    assert "missing" in result.stdout and "docs/kit/SETUP.md" in result.stdout


def test_update_merges_the_rendered_trees_not_the_raw_kit(
    kit_repo: Path, tmp_path: Path, templates: Path
) -> None:
    project = project_from(
        kit_repo, tmp_path / "project", templates, "--base", "develop", "--branch-prefix", "unit"
    )
    git(project, "switch", "-q", "-c", "unit-kit-update")
    result = kit_py(project, "update", "--to", "v0.2.0", "--no-sync")
    assert result.returncode == 0, result.stdout + result.stderr
    settings = (project / ".claude/settings.json").read_text("utf-8")
    assert (
        '"Bash(git switch -c unit-:*)"' in settings
        and '"Bash(gh pr create --base develop:*)"' in settings
    )
    assert no_markers(project)
    check_all(project)


def test_update_refuses_what_cannot_be_right(
    kit_repo: Path, tmp_path: Path, copy_of_the_kit: Path, templates: Path
) -> None:
    assert kit_py(copy_of_the_kit, "update", "--no-sync").returncode == 2  # the kit, no lock
    project = project_from(kit_repo, tmp_path / "project2", templates)

    unknown = kit_py(project, "update", "--to", "v9.9.9", "--no-sync")
    assert unknown.returncode == 2 and "no ref 'v9.9.9'" in unknown.stdout

    (project / "README.md").write_text("dirty\n", "utf-8")
    dirty = kit_py(project, "update", "--to", "v0.2.0", "--no-sync")
    assert dirty.returncode == 2 and "not clean" in dirty.stdout
    git(project, "checkout", "--", "README.md")

    git(project, "switch", "-q", "main")
    on_base = kit_py(project, "update", "--to", "v0.2.0", "--no-sync")
    assert on_base.returncode == 2 and "base branch" in on_base.stdout
    git(project, "switch", "-q", "main-kit-update")

    assert kit_py(project, "update", "--to", "v0.2.0", "--no-sync").returncode == 0
    git(project, "commit", "-q", "-m", "updated")
    older = kit_py(project, "update", "--to", "v0.1.0", "--no-sync")
    assert older.returncode == 2 and "behind what this project has" in older.stdout
    again = kit_py(project, "update", "--to", "v0.2.0", "--no-sync")
    assert again.returncode == 0 and "nothing to do" in again.stdout

    lock_file = project / kit.LOCK
    lock_file.write_text(
        lock_file.read_text("utf-8").replace('package = "demo"', 'package = "other"'), "utf-8"
    )
    git(project, "commit", "-q", "-am", "an edited lock")
    mismatch = kit_py(project, "update", "--to", "v0.2.0", "--no-sync")
    assert mismatch.returncode == 2 and "pyproject.toml says" in mismatch.stdout


def test_status_names_the_versions_and_the_locally_changed_kit_files(
    kit_repo: Path, tmp_path: Path, templates: Path
) -> None:
    project = project_from(kit_repo, tmp_path / "project", templates)
    clean = kit_py(project, "status")
    assert clean.returncode == 0, clean.stdout + clean.stderr
    assert "kit version: 0.1.0" in clean.stdout and "newest: v0.3.0" in clean.stdout
    assert "as the kit rendered them" in clean.stdout

    makefile = project / "Makefile"
    makefile.write_text(makefile.read_text("utf-8") + "\n# ours\n", "utf-8")
    changed = kit_py(project, "status")  # a dirty tree is what status is for: no clean-tree check
    assert changed.returncode == 0, changed.stdout + changed.stderr
    assert "differ from the kit" in changed.stdout
    listed = [line.strip() for line in changed.stdout.splitlines() if line.startswith("  ")]
    assert listed == ["Makefile"]


# ---------------------------------------------------------------------------- update, round 2


def test_the_targets_kit_py_runs_the_update_and_its_manifest_decides(
    kit_repo: Path, tmp_path: Path, templates: Path
) -> None:
    """v0.3.0 adds a kit-owned pattern (`extras/*`) in its own kit.py and a file under it. The
    project's kit.py knows nothing of it; the target's kit.py runs the update from the export, so
    the file arrives in the same run (round 1 of the review: the first run skipped it, and the
    second said "nothing to do")."""
    project = project_from(kit_repo, tmp_path / "project", templates)
    result = kit_py(project, "update", "--to", "v0.3.0", "--no-sync")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "it runs this update" in result.stdout
    assert "unknown to" not in result.stdout
    assert (project / "extras/tool.txt").read_text("utf-8") == "a kit-owned extra for demo\n"
    assert kit.read_lock(project).version == "0.3.0"
    assert "0.3.0" in (project / "kit.py").read_text("utf-8")
    git(project, "commit", "-q", "-m", "updated")
    again = kit_py(project, "update", "--to", "v0.3.0", "--no-sync")
    assert again.returncode == 0 and "nothing to do" in again.stdout


def test_an_added_file_keeps_its_mode(kit_repo: Path, tmp_path: Path, templates: Path) -> None:
    project = project_from(kit_repo, tmp_path / "project", templates)
    assert kit_py(project, "update", "--to", "v0.3.0", "--no-sync").returncode == 0
    assert os.access(project / "scripts/run.sh", os.X_OK)
    assert "echo demo" in (project / "scripts/run.sh").read_text("utf-8")


def test_update_refuses_to_go_backwards_in_the_history(
    kit_repo: Path, tmp_path: Path, templates: Path
) -> None:
    """The newest tag is behind a commit the project already has: the default target must not
    undo it, and `--to` an ancestor is refused — order is the commits', not the version string's."""
    project = project_from(kit_repo, tmp_path / "project", templates)
    assert kit_py(project, "update", "--to", "main", "--no-sync").returncode == 0  # after v0.3.0
    git(project, "commit", "-q", "-m", "at the tip")
    assert "# after v0.3.0" in (project / "scripts/fmt_hook.py").read_text("utf-8")
    default = kit_py(project, "update", "--no-sync")  # the newest tag, v0.3.0: an ancestor
    assert default.returncode == 2 and "behind what this project has" in default.stdout
    assert "# after v0.3.0" in (project / "scripts/fmt_hook.py").read_text("utf-8")
    assert git(project, "status", "--porcelain") == ""


def test_update_reaches_a_branch_by_its_name(
    kit_repo: Path, tmp_path: Path, templates: Path
) -> None:
    project = project_from(kit_repo, tmp_path / "project", templates)
    result = kit_py(project, "update", "--to", "feature", "--no-sync")
    assert result.returncode == 0, result.stdout + result.stderr
    assert (project / "docs/kit/FEATURE.md").is_file()


def test_a_conflict_in_pyproject_leaves_a_sentence_not_a_traceback(
    kit_repo: Path, tmp_path: Path, templates: Path
) -> None:
    project = project_from(kit_repo, tmp_path / "project", templates)
    pyproject = project / "pyproject.toml"
    old = 'select = ["E", "F", "I", "UP", "B", "SIM", "RUF"]'
    pyproject.write_text(pyproject.read_text("utf-8").replace(old, old[:-1] + ', "PL"]'), "utf-8")
    git(project, "commit", "-q", "-am", "our own lint rule")
    conflict = kit_py(project, "update", "--to", "v0.2.0", "--no-sync")
    assert conflict.returncode == 1 and "pyproject.toml" in conflict.stdout
    status = kit_py(project, "status")
    assert status.returncode == 2, status.stdout + status.stderr
    assert "Traceback" not in status.stderr and "conflict markers" in status.stdout
    git(project, "commit", "-q", "-am", "with the markers")
    again = kit_py(project, "update", "--to", "v0.3.0", "--no-sync")
    assert again.returncode == 2 and "Traceback" not in again.stderr


def test_status_says_when_the_kit_it_took_cannot_be_reconstructed(
    kit_repo: Path, tmp_path: Path, templates: Path
) -> None:
    project = project_from(kit_repo, tmp_path / "project", templates)
    lock = kit.read_lock(project)
    kit.write_lock(project, lock.answers, "0.9.9", repo=lock.repo)  # no such tag, no commit
    git(project, "commit", "-q", "-am", "a lock the kit has no tag for")
    result = kit_py(project, "status")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "kit version: 0.9.9" in result.stdout and "cannot be reconstructed" in result.stdout
    with_from = kit_py(project, "status", "--from", "v0.1.0")
    assert with_from.returncode == 0 and "as the kit rendered them" in with_from.stdout


def test_a_relative_repo_is_read_from_where_the_user_stands(
    kit_repo: Path, tmp_path: Path, templates: Path
) -> None:
    project = project_from(kit_repo, tmp_path / "project", templates)
    relative = os.path.relpath(kit_repo, project)
    result = kit_py(project, "update", "--repo", relative, "--to", "v0.2.0", "--no-sync")
    assert result.returncode == 0, result.stdout + result.stderr
    assert kit.read_lock(project).repo == str(kit_repo.resolve())  # recorded absolute


def test_a_directory_where_the_kit_adds_a_file_is_not_added(
    kit_repo: Path, tmp_path: Path, templates: Path
) -> None:
    project = project_from(kit_repo, tmp_path / "project", templates)
    (project / "extras/tool.txt").mkdir(parents=True)
    (project / "extras/tool.txt/ours.txt").write_text("ours\n", "utf-8")
    git(project, "add", "-A")
    git(project, "commit", "-q", "-m", "a folder of our own")
    result = kit_py(project, "update", "--to", "v0.3.0", "--no-sync")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Traceback" not in result.stderr
    assert "not added" in result.stdout and "extras/tool.txt" in result.stdout
    assert (project / "extras/tool.txt/ours.txt").is_file()


def test_a_merge_git_cannot_do_is_a_sentence_and_names_the_way_back(tmp_path: Path) -> None:
    base, theirs, project = tmp_path / "base", tmp_path / "theirs", tmp_path / "project"
    for root, content in ((base, b"a\x00b"), (theirs, b"a\x00c"), (project, b"a\x00d")):
        root.mkdir()
        (root / "x.dat").write_bytes(content)
    with pytest.raises(kit.Refused, match=r"could not merge x\.dat.*half updated"):
        kit.apply_update(kit.UpdatePlan(merge=["x.dat"]), base, theirs, project, "0.1.0", "0.2.0")


def test_files_under_ignores_only_the_trees_own_git(tmp_path: Path) -> None:
    root = tmp_path / ".git" / "tmp" / "tree"
    root.mkdir(parents=True)
    (root / "a.txt").write_text("a\n", "utf-8")
    (root / ".git").mkdir()
    (root / ".git" / "config").write_text("x\n", "utf-8")
    assert kit.files_under(root) == ["a.txt"]


def test_python_version_problem_is_a_sentence_below_the_minimum() -> None:
    assert kit.python_version_problem(3, 10, 12) is not None
    assert "3.11.4" in (kit.python_version_problem(3, 9, 6) or "")
    assert kit.python_version_problem(3, 11, 3) is not None  # tarfile's filter came in 3.11.4
    assert kit.python_version_problem(3, 11, 4) is None
    assert kit.python_version_problem(3, 13, 12) is None


def test_kit_py_imports_the_standard_library_only() -> None:
    import ast

    tree = ast.parse((ROOT / "kit.py").read_text("utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported, "no imports found"
    assert imported <= set(sys.stdlib_module_names) | {"__future__"}, imported - set(
        sys.stdlib_module_names
    )


def test_without_option_drops_the_flag_in_both_spellings() -> None:
    argv = ["--to", "v0.2.0", "--repo", "../kit", "--no-sync", "--repo=../other"]
    assert kit.without_option(argv, "--repo") == ["--to", "v0.2.0", "--no-sync"]
    assert kit.without_option(["--repo"], "--repo") == []


# ---------------------------------------------------------------------------- update, round 3


def test_update_removes_a_file_whose_pattern_the_newer_kit_dropped(
    kit_repo: Path, tmp_path: Path, templates: Path
) -> None:
    """v0.3.0 brought `extras/tool.txt` under a pattern of its own kit.py; `drop` removes both. The
    base must be read with the manifest of the kit it came from, not the newer one (round 2 of the
    review: the file stayed, "0 removed", and `status` called the tree clean)."""
    project = project_from(kit_repo, tmp_path / "project", templates)
    assert kit_py(project, "update", "--to", "v0.3.0", "--no-sync").returncode == 0
    git(project, "commit", "-q", "-m", "at v0.3.0")
    assert (project / "extras/tool.txt").is_file()
    result = kit_py(project, "update", "--to", "drop", "--no-sync")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 removed" in result.stdout and not (project / "extras/tool.txt").exists()
    assert kit.read_lock(project).version == "0.4.0"


def test_a_refused_update_leaves_the_tree_as_it_was(
    kit_repo: Path, tmp_path: Path, templates: Path
) -> None:
    """`side` is older by version and not an ancestor: refused as "older than" before anything is
    written, so the tree stays clean (round 2: kit.py had been replaced before the refusal)."""
    project = project_from(kit_repo, tmp_path / "project", templates)
    result = kit_py(project, "update", "--to", "side", "--no-sync")
    assert result.returncode == 2, result.stdout + result.stderr
    assert "older than" in result.stdout
    assert git(project, "status", "--porcelain") == ""


def test_a_local_edit_of_kit_py_is_merged_like_any_kit_owned_file(
    kit_repo: Path, tmp_path: Path, templates: Path
) -> None:
    project = project_from(kit_repo, tmp_path / "project", templates)
    kit_py_file = project / "kit.py"
    kit_py_file.write_text(kit_py_file.read_text("utf-8") + "\n# our own note in kit.py\n", "utf-8")
    git(project, "commit", "-q", "-am", "a note in kit.py")
    result = kit_py(project, "update", "--to", "v0.2.0", "--no-sync")
    assert result.returncode == 0, result.stdout + result.stderr
    text = kit_py_file.read_text("utf-8")
    assert "# our own note in kit.py" in text and 'KIT_VERSION = "0.2.0"' in text
    assert no_markers(project)


def test_update_needs_a_git_repository_and_status_does_not(
    kit_repo: Path, tmp_path: Path, templates: Path
) -> None:
    project = project_from(kit_repo, tmp_path / "project", templates)
    shutil.rmtree(project / ".git")
    status = kit_py(project, "status")
    assert status.returncode == 0, status.stdout + status.stderr
    assert "kit version: 0.1.0" in status.stdout
    update = kit_py(project, "update", "--to", "v0.2.0", "--no-sync")
    assert update.returncode == 2 and "not a git repository" in update.stdout
    assert "Traceback" not in update.stderr


def test_status_refuses_a_from_ref_the_kit_lacks_and_names_a_lost_commit(
    kit_repo: Path, tmp_path: Path, templates: Path
) -> None:
    project = project_from(kit_repo, tmp_path / "project", templates)
    typed = kit_py(project, "status", "--from", "nosuchref")
    assert typed.returncode == 2 and "no ref 'nosuchref'" in typed.stdout
    lock = kit.read_lock(project)
    lost_commit = "0123456789abcdef0123456789abcdef01234567"
    kit.write_lock(project, lock.answers, lock.version, repo=lock.repo, commit=lost_commit)
    git(project, "commit", "-q", "-am", "a lock whose commit the kit does not hold")
    lost = kit_py(project, "status")
    assert lost.returncode == 0, lost.stdout + lost.stderr
    assert "kit version: 0.1.0 (0123456789ab)" in lost.stdout
    assert "is not in the kit" in lost.stdout and "first release" not in lost.stdout


def test_a_kit_owned_path_that_is_a_link_is_left_alone_and_listed(
    kit_repo: Path, tmp_path: Path, templates: Path
) -> None:
    """`git merge-file` would write through the link into a file outside the project, where the PR
    the update becomes does not show it."""
    project = project_from(kit_repo, tmp_path / "project", templates)
    outside = tmp_path / "outside.py"
    hook = project / "scripts/fmt_hook.py"
    outside.write_bytes(hook.read_bytes())
    hook.unlink()
    hook.symlink_to(outside)
    git(project, "add", "-A")
    git(project, "commit", "-q", "-m", "the hook is a link")
    before = outside.read_bytes()
    result = kit_py(project, "update", "--to", "v0.2.0", "--no-sync")
    assert result.returncode == 0, result.stdout + result.stderr
    assert outside.read_bytes() == before and hook.is_symlink()
    assert "not touched" in result.stdout and "scripts/fmt_hook.py" in result.stdout


def test_a_kit_owned_folder_that_is_a_link_is_left_alone_and_listed(
    kit_repo: Path, tmp_path: Path, templates: Path
) -> None:
    """The link is a folder on the way, not the file: a merge, an add and a remove under it would
    all land outside the project."""
    project = project_from(kit_repo, tmp_path / "project", templates)
    outside = tmp_path / "outside-scripts"
    shutil.move(project / "scripts", outside)
    (project / "scripts").symlink_to(outside, target_is_directory=True)
    git(project, "add", "-A")
    git(project, "commit", "-q", "-m", "scripts is a link")
    before = {p.name: p.read_bytes() for p in outside.iterdir()}
    result = kit_py(project, "update", "--to", "v0.3.0", "--no-sync")  # fmt_hook merges, run.sh new
    assert result.returncode == 0, result.stdout + result.stderr
    assert {p.name: p.read_bytes() for p in outside.iterdir()} == before
    assert "not touched" in result.stdout
    assert "scripts/fmt_hook.py" in result.stdout and "scripts/run.sh" in result.stdout


def test_a_target_without_kit_py_is_refused_in_a_sentence(
    kit_repo: Path, tmp_path: Path, templates: Path
) -> None:
    project = project_from(kit_repo, tmp_path / "project", templates)
    result = kit_py(project, "update", "--to", "nokit", "--no-sync")
    assert result.returncode == 2, result.stdout + result.stderr
    assert "has no kit.py" in result.stdout and "nokit" in result.stdout
    assert "Traceback" not in result.stderr and git(project, "status", "--porcelain") == ""


def test_a_temporary_directory_inside_the_project_is_refused(
    kit_repo: Path, tmp_path: Path, templates: Path
) -> None:
    """The first run's working folder would be an untracked path in the handed-over run's tree."""
    project = project_from(kit_repo, tmp_path / "project", templates)
    (project / "tmp").mkdir()
    env = {**os.environ, "TMPDIR": str(project / "tmp")}
    result = kit_py(project, "update", "--to", "v0.2.0", "--no-sync", env=env)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "inside the project" in result.stdout and git(project, "status", "--porcelain") == ""
