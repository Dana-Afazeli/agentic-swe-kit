"""The list of gate files lives in three places; they must name the same files.

`scripts/guard_bash.py` (the Bash guard refuses shell writes to them), the `gate-guard` job in
`.github/workflows/ci.yml` (a PR that touches one needs `gates-approved`), and the `ask` rules in
`.claude/settings.json` (the editor asks the maintainer before changing one). A comment in each
asks for them to be kept in step; this test is what notices when they are not.

One more pair with the same need: the marker expression in the Makefile's pytest recipes and the
one `scripts/integrity.py` collects with.
"""

import json
import re
import subprocess
from pathlib import Path

import guard_bash
import integrity
import review
import stop_gate

# The nearest directory above this file that holds the workflow: the repository root, also when
# mutmut runs the tests from its copy under mutants/ (which has no .github/ or .claude/).
ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / ".github" / "workflows" / "ci.yml").is_file()
)
GUARD = {*guard_bash.GATE_FILES, *(f"{directory}/" for directory in guard_bash.GATE_DIRS)}


def test_the_ci_regex_names_the_guards_gate_files() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text("utf-8")
    patterns = re.findall(r"^\s+GATE_FILES: '\^\((.+)\)'$", workflow, flags=re.MULTILINE)
    assert len(patterns) == 1

    # `Makefile$` is a file, `scripts/` a directory prefix; `\.` is a literal dot
    in_ci = {entry.replace("\\.", ".").removesuffix("$") for entry in patterns[0].split("|")}

    assert in_ci == GUARD


def test_the_ask_rules_name_the_guards_gate_files() -> None:
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text("utf-8"))
    rules: list[str] = settings["permissions"]["ask"]
    edits = [rule for rule in rules if rule.startswith(("Edit(", "Write("))]

    # `Edit(/Makefile)` is a file, `Edit(/scripts/**)` a directory; only Edit rules are matched
    # by Claude Code's file permission checks, and they cover every editing tool.
    asked = {rule.removeprefix("Edit(/").removesuffix(")").replace("/**", "/") for rule in edits}

    assert asked == GUARD


def test_a_tools_own_config_file_is_a_gate_file() -> None:
    """Each of these is read before, or instead of, `pyproject.toml` or the `Makefile` by a tool
    `make check` runs. Not on the gate list, one of them lowers a threshold with no label asked
    for (PR #5 review, round 4). None exists here: all configuration is in `pyproject.toml`."""
    overrides = {
        *("GNUmakefile", "makefile"),  # GNU make tries them before Makefile
        *("pytest.toml", ".pytest.toml", "pytest.ini", ".pytest.ini"),  # pytest
        *("ruff.toml", ".ruff.toml"),  # ruff
        "pyrightconfig.json",  # basedpyright
        *(".coveragerc", ".coveragerc.toml"),  # coverage
        ".importlinter",  # import-linter
        *("setup.cfg", "tox.ini"),  # coverage, import-linter, mutmut; pytest without the above
        "uv.toml",  # uv: `[tool.uv]` in pyproject.toml is then ignored
    }

    assert overrides == guard_bash.CONFIG_OVERRIDES
    assert overrides <= guard_bash.GATE_FILES
    assert overrides <= stop_gate.GATED_FILES
    # The Stop hook keeps its own copy of the names: importing the guard would let a broken
    # guard_bash.py end the hook with exit 1, which does not block (PR #5 review, round 7).
    assert not hasattr(stop_gate, "guard_bash")
    assert not [name for name in overrides if (ROOT / name).exists() and name != "makefile"]


def test_gate_guard_sees_a_gate_path_that_git_would_quote(tmp_path: Path) -> None:
    """git puts a path in double quotes when it holds a non-ASCII character, a `"` or a `\\`;
    the line then starts with `"`, and the job's `^(…)` never matches (PR #5 review, round 8).
    The job's own `git diff` options and regex are run here on three such paths."""
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text("utf-8")
    listings = re.findall(r"=\$\((git [^)]*diff --name-only [^)]*)\)", workflow)
    assert len(listings) == 3  # the mutation job, and gate-guard's two
    assert all(each.startswith("git -c core.quotePath=false diff ") for each in listings)
    # the quotes that a `"` or a `\` in a name still brings are taken off, for both lists
    assert 'changed=${changed//\\"/}' in workflow
    assert 'pushed=${pushed//\\"/}' in workflow
    patterns = re.findall(r"^\s+GATE_FILES: '(\^\(.+\))'$", workflow, flags=re.MULTILINE)

    paths = [".github/workflows/é.yml", "scripts/naïve.py", '.claude/agents/a"b.md']
    git = ["git", "-C", str(tmp_path), "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
    quiet = ["-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null"]
    subprocess.run([*git, "init", "-q"], check=True, capture_output=True)
    subprocess.run(
        [*git, *quiet, "commit", "-q", "--allow-empty", "-m", "base"],
        check=True,
        capture_output=True,
    )
    for path in paths:
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_text("x\n", "utf-8")
    subprocess.run([*git, "add", "."], check=True, capture_output=True)
    subprocess.run([*git, *quiet, "commit", "-q", "-m", "head"], check=True, capture_output=True)
    options = listings[1].split()[1 : listings[1].split().index("--no-renames") + 1]
    listed = subprocess.run(
        [*git, *options, "HEAD~1...HEAD"], check=True, capture_output=True, text=True
    ).stdout

    lines = listed.replace('"', "").splitlines()

    assert len(lines) == 3
    assert all(re.match(patterns[0], line) for line in lines)


def test_integrity_collects_with_the_marker_expression_make_check_runs() -> None:
    """`integrity.py` lists the tests the gate runs, so it must deselect what the Makefile's
    `test` and `cov` recipes deselect."""
    makefile = (ROOT / "Makefile").read_text("utf-8")
    runs = [line for line in makefile.splitlines() if line.startswith("\tuv run pytest")]

    assert len(runs) == 2
    assert all(f' -m "{integrity.GATE_MARKERS}"' in line for line in runs)


def test_the_reviewer_clone_marker_is_one_name_in_both_scripts() -> None:
    """`scripts/review.py` sets it, `scripts/stop_gate.py` reads it; neither imports the other.
    A change to one string alone would send the reviewers back to running into the time limit."""
    assert review.REVIEWER_CLONE_VARIABLE == stop_gate.REVIEWER_CLONE_VARIABLE
