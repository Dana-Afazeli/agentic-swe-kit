"""The permission rules of `.claude/settings.json` that keep a tree on its branch.

A brief's work happens in its own tree, and the main checkout stays on the base branch, so a
session has no reason to switch a branch: `git switch` and `git checkout` are denied. A deny rule
is a prefix match on the command a session types. It stops the plain spelling; `git -C . switch`
and a script that calls git are not seen by it.
"""

import json
from pathlib import Path

import tree

# The nearest directory above this file that holds the workflow: the repository root, also when
# mutmut runs the tests from its copy under mutants/ (which has no .github/ or .claude/).
ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / ".github" / "workflows" / "ci.yml").is_file()
)


def rules(kind: str) -> list[str]:
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text("utf-8"))
    return settings["permissions"][kind]


def test_a_session_is_not_allowed_to_switch_or_check_out_a_branch() -> None:
    allowed = [
        rule for rule in rules("allow") if rule.startswith(("Bash(git switch", "Bash(git checkout"))
    ]

    assert allowed == []


def test_git_switch_and_git_checkout_are_denied() -> None:
    denied = rules("deny")

    assert "Bash(git switch:*)" in denied
    assert "Bash(git checkout:*)" in denied


def test_the_other_git_rules_a_brief_needs_are_still_allowed() -> None:
    allowed = rules("allow")

    for rule in (
        "Bash(git add:*)",
        "Bash(git commit:*)",
        f"Bash(git push -u origin {tree.BRANCH_PREFIX}-:*)",
    ):
        assert rule in allowed
