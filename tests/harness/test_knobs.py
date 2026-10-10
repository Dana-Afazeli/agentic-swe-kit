"""Every site of a knob names the same value.

The knobs (docs/kit/HARNESS.md, "Knobs") are rewritten by `kit.py init` at sites spread over
Python constants, JSON rules, YAML, TOML and prose. A site that was missed, or edited by hand on
one side only, is what this module notices — in the kit, and in every project after `init`.

The checks read files, never import the scripts, so the same functions run against the kit and
against a project `init` just rendered (`tests/harness/test_kit.py` does that).
"""

import json
import re
import tomllib
from pathlib import Path

import kit

from conftest import REPO_ROOT


def knob(root: Path, path: str, name: str) -> str:
    """The quoted value on the line of `path` that carries `# knob: <name>`."""
    for line in (root / path).read_text("utf-8").splitlines():
        if f"# knob: {name}" in line:
            match = re.search(r'"([^"]*)"', line)
            assert match, f"{path}: the knob line has no quoted value: {line}"
            return match[1]
    raise AssertionError(f"{path}: no line carries '# knob: {name}'")


def rules(root: Path, kind: str) -> list[str]:
    settings = json.loads((root / ".claude" / "settings.json").read_text("utf-8"))
    return list(settings["permissions"][kind])


def check_base(root: Path) -> None:
    base = knob(root, "scripts/stop_gate.py", "base")
    assert knob(root, "scripts/guard_bash.py", "base") == base
    ci = (root / ".github/workflows/ci.yml").read_text("utf-8")
    # quoted, so that YAML reads a branch named `1.10` or `true` as a string
    assert re.findall(r'branches: \["([^"\]]+)"\] # knob: base', ci) == [base, base]
    assert f"Bash(gh pr create --base {base}:*)" in rules(root, "allow")
    for denied in (
        f"git push origin {base}",
        f"git push -u origin {base}",
        f"git push origin HEAD:{base}",
    ):
        assert f"Bash({denied})" in rules(root, "deny")
    assert f"Never commit or push to `{base}`." in (root / "AGENTS.md").read_text("utf-8")


def check_prefix(root: Path) -> None:
    prefix = knob(root, "scripts/review.py", "prefix")
    for allowed in (
        f"git switch {prefix}-:*",
        f"git switch -c {prefix}-:*",
        f"git push -u origin {prefix}-:*",
        f"git push origin {prefix}-:*",
    ):
        assert f"Bash({allowed})" in rules(root, "allow")
    assert f"`{prefix}-NNN-slug`" in (root / "AGENTS.md").read_text("utf-8")
    template = (root / "docs/briefs/000-TEMPLATE.md").read_text("utf-8")
    assert f"`{prefix}-NNN-<slug>`" in template


def check_package(root: Path) -> None:
    pyproject = tomllib.loads((root / "pyproject.toml").read_text("utf-8"))
    name = pyproject["project"]["name"]
    packages = [p.name for p in (root / "src").iterdir() if p.is_dir()]
    assert name in packages, packages  # a project may hold more than one package
    assert pyproject["tool"]["hatch"]["version"]["path"] == f"src/{name}/__init__.py"
    assert pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == [f"src/{name}"]
    assert pyproject["tool"]["coverage"]["run"]["source"] == [name]
    assert pyproject["tool"]["importlinter"]["root_package"] == name
    assert pyproject["tool"]["mutmut"]["source_paths"] == [f"src/{name}"]
    for contract in pyproject["tool"]["importlinter"]["contracts"]:
        for module in contract["source_modules"]:
            assert module.split(".")[0] == name, module
        # forbidden modules may name external packages (httpx, sqlalchemy, …); what they may not
        # name is a module of the kit's placeholder package
        placeholder = kit.PLACEHOLDER.package
        for module in contract["forbidden_modules"]:
            assert not module.startswith(placeholder) or name == placeholder, module
    ci = (root / ".github/workflows/ci.yml").read_text("utf-8")
    assert f"-- src/{name}/core) # knob: package" in ci
    assert knob(root, "scripts/review.py", "package") == f"{name}-review"


def check_python(root: Path) -> None:
    version = (root / ".python-version").read_text("utf-8").strip()
    major, minor = version.split(".")[:2]
    pyproject = tomllib.loads((root / "pyproject.toml").read_text("utf-8"))
    bounds = f">={major}.{minor},<{major}.{int(minor) + 1}"
    assert pyproject["project"]["requires-python"] == bounds
    assert pyproject["tool"]["basedpyright"]["pythonVersion"] == f"{major}.{minor}"


def check_gate_file_lists(root: Path) -> None:
    """`kit.py` rewrites gate files, so it is one: in the guard, the CI regex and the ask rules."""
    guard = (root / "scripts/guard_bash.py").read_text("utf-8")
    assert re.search(r'^\s+"kit\.py",', guard, flags=re.MULTILINE), "guard_bash.GATE_FILES"
    ci = (root / ".github/workflows/ci.yml").read_text("utf-8")
    assert r"kit\.py$" in ci, "the GATE_FILES regex of gate-guard"
    assert "Edit(/kit.py)" in rules(root, "ask")


def check_all(root: Path) -> None:
    check_base(root)
    check_prefix(root)
    check_package(root)
    check_python(root)
    check_gate_file_lists(root)


def test_the_base_branch_sites_agree() -> None:
    check_base(REPO_ROOT)


def test_the_branch_prefix_sites_agree() -> None:
    check_prefix(REPO_ROOT)


def test_the_package_sites_agree() -> None:
    check_package(REPO_ROOT)


def test_the_python_sites_agree() -> None:
    check_python(REPO_ROOT)


def test_kit_py_is_a_gate_file_in_all_three_lists() -> None:
    check_gate_file_lists(REPO_ROOT)
