"""Every site of a knob names the same value.

The knobs (docs/kit/HARNESS.md, "Knobs") are rewritten by `kit.py init` at sites spread over
Python constants, JSON rules, YAML, TOML and prose. A site that was missed, or edited by hand on
one side only, is what this module notices — in the kit, and in every project after `init`.
"""

import json
import re
import tomllib

import guard_bash
import review
import stop_gate
from conftest import REPO_ROOT

ROOT = REPO_ROOT


def read(path: str) -> str:
    return (ROOT / path).read_text("utf-8")


def rules(kind: str) -> list[str]:
    settings = json.loads(read(".claude/settings.json"))
    return list(settings["permissions"][kind])


def test_the_base_branch_sites_agree() -> None:
    base = stop_gate.BASE_BRANCH
    assert base == guard_bash.BASE_BRANCH
    assert re.findall(r"branches: \[([^\]]+)\] # knob: base", read(".github/workflows/ci.yml")) == [
        base,
        base,
    ]
    assert f"Bash(gh pr create --base {base}:*)" in rules("allow")
    for denied in (
        f"git push origin {base}",
        f"git push -u origin {base}",
        f"git push origin HEAD:{base}",
    ):
        assert f"Bash({denied})" in rules("deny")
    assert f"Never commit or push to `{base}`." in read("AGENTS.md")


def test_the_branch_prefix_sites_agree() -> None:
    prefix = review.BRANCH_PREFIX
    for allowed in (
        f"git switch {prefix}-:*",
        f"git switch -c {prefix}-:*",
        f"git push -u origin {prefix}-:*",
        f"git push origin {prefix}-:*",
    ):
        assert f"Bash({allowed})" in rules("allow")
    assert f"`{prefix}-NNN-slug`" in read("AGENTS.md")
    assert f"`{prefix}-NNN-<slug>`" in read("docs/briefs/000-TEMPLATE.md")


def test_the_package_sites_agree() -> None:
    pyproject = tomllib.loads(read("pyproject.toml"))
    name = pyproject["project"]["name"]
    packages = sorted(
        p.name for p in (ROOT / "src").iterdir() if p.is_dir() and not p.name.endswith(".egg-info")
    )
    assert packages == [name]
    assert pyproject["tool"]["hatch"]["version"]["path"] == f"src/{name}/__init__.py"
    assert pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == [f"src/{name}"]
    assert pyproject["tool"]["coverage"]["run"]["source"] == [name]
    assert pyproject["tool"]["importlinter"]["root_package"] == name
    assert pyproject["tool"]["mutmut"]["source_paths"] == [f"src/{name}"]
    for contract in pyproject["tool"]["importlinter"]["contracts"]:
        for module in [*contract["source_modules"], *contract["forbidden_modules"]]:
            assert module.split(".")[0] == name
    assert f"-- src/{name}/core) # knob: package" in read(".github/workflows/ci.yml")
    assert review.WORK.name == f"{name}-review"
    assert f"{name.upper()}_EVAL_BUDGET_USD" in read("project.mk")
    assert f"from {name}.main import main" in read("project.mk")


def test_the_python_sites_agree() -> None:
    version = read(".python-version").strip()
    major, minor = version.split(".")[:2]
    pyproject = tomllib.loads(read("pyproject.toml"))
    assert pyproject["project"]["requires-python"] == f">={major}.{minor},<{major}.{int(minor) + 1}"
    assert pyproject["tool"]["basedpyright"]["pythonVersion"] == f"{major}.{minor}"
