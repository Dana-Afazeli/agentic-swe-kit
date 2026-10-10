"""A project made from the kit holds none of the kit's records, no pointer to one, and no date.

Kit-only: it renders the kit's own tree as a project and scans what the project would receive. The
kit's tree itself names every id and every path on purpose (its decision records, its briefs, its
changelog), so a scan of the repository would be red for ever.
"""

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

import kit
import pytest

from conftest import REPO_ROOT

ANSWERS = kit.Answers(
    package="acme", base="main", prefix="main", maintainer="Ada Lovelace", python="3.13.12"
)


RECORD_ID = re.compile(r"ADR-[0-9]{4}")
DATE = re.compile(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}")
NOT_PROSE = ("kit.lock", "uv.lock")


def lines_of(root: Path) -> Iterator[tuple[str, int, str]]:
    """Every line of every file under `root`: its path from `root`, its number, its text."""
    for path in sorted(root.rglob("*")):
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            text = path.read_text("utf-8", errors="replace")
            for number, line in enumerate(text.splitlines(), 1):
                yield relative, number, line


def record_ids(root: Path) -> list[str]:
    """`<file>:<line>: ADR-NNNN` for each decision record id in any file."""
    return sorted(
        f"{name}:{number}: {found}"
        for name, number, line in lines_of(root)
        for found in RECORD_ID.findall(line)
    )


def record_pointers(root: Path, kit_only: Iterable[str]) -> list[str]:
    """`<file>:<line>: <path>` for each path of `kit_only` that a file other than `kit.py` names.
    `kit.py` is the manifest: it names the kit's tree."""
    paths = list(kit_only)
    return sorted(
        f"{name}:{number}: {path}"
        for name, number, line in lines_of(root)
        if name != "kit.py"
        for path in paths
        if path in line
    )


def dates(root: Path) -> list[str]:
    """`<file>:<line>: YYYY-MM-DD` outside `tests/` and the lock files."""
    return sorted(
        f"{name}:{number}: {found}"
        for name, number, line in lines_of(root)
        if not name.startswith("tests/") and name not in NOT_PROSE
        for found in DATE.findall(line)
    )


def tree(root: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, "utf-8")
    return root


@dataclass(frozen=True)
class Project:
    root: Path
    kit_only_docs: list[str]  # the kit's own records: tracked, kit-only, and not in the project


@pytest.fixture(scope="module")
def project(tmp_path_factory: pytest.TempPathFactory) -> Project:
    root = tmp_path_factory.mktemp("stateless") / "project"
    tracked = kit.tracked_files(REPO_ROOT)
    written = set(kit.render_tree(REPO_ROOT, root, ANSWERS, tracked))
    records = [
        path
        for path in tracked
        if path.startswith("docs/") and kit.category(path) == "kit-only" and path not in written
    ]
    return Project(root, records)


def files_under(root: Path, folder: str) -> list[str]:
    return sorted(str(p.relative_to(root)) for p in (root / folder).rglob("*") if p.is_file())


# ---------------------------------------------------------------------------- the places


def test_a_project_gets_the_places_and_none_of_the_records(project: Project) -> None:
    assert files_under(project.root, "docs") == sorted(
        [
            "docs/BACKLOG.md",
            "docs/DELTAS.md",
            "docs/FRICTION.md",
            "docs/ROADMAP.md",
            "docs/briefs/.gitkeep",
            "docs/decisions/0000-TEMPLATE.md",
            "docs/kit/HARNESS.md",
            "docs/kit/LICENSE",
            "docs/kit/PHILOSOPHY.md",
            "docs/kit/SETUP.md",
            "docs/kit/WORKFLOW.md",
            "docs/research/.gitkeep",
        ]
    )
    for place in ("docs/briefs/.gitkeep", "docs/research/.gitkeep"):
        assert (project.root / place).stat().st_size == 0, place


def test_the_places_are_the_projects_and_what_the_kit_keeps_there_is_not() -> None:
    assert kit.category("docs/research/2026-10-05-review-model-and-effort.md") == "kit-only"
    # each sits under a kit-only `*` pattern: the first match wins
    assert kit.category("docs/research/.gitkeep") == "project-owned"
    assert kit.category("docs/briefs/.gitkeep") == "project-owned"
    assert kit.category("docs/MAINTAINING.md") == "kit-only"
    assert not kit.is_managed("docs/research/2026-11-01-ours.md")


# ---------------------------------------------------------------------------- the scans


def test_no_file_of_a_project_names_a_decision_record(project: Project, tmp_path: Path) -> None:
    assert record_ids(tree(tmp_path / "a", {"scripts/x.py": "# see ADR-0008\n"})) == [
        "scripts/x.py:1: ADR-0008"
    ]
    # the template's placeholder, another three-letter token, three digits
    assert record_ids(tree(tmp_path / "b", {"t.md": "ADR-NNNN\nRFC-2119\nADR-008\n"})) == []
    assert record_ids(project.root) == []


def test_no_file_of_a_project_points_at_a_record_of_the_kit(
    project: Project, tmp_path: Path
) -> None:
    named = "docs/decisions/0008-stop-hook-keeps-make-check-only.md"
    kit_only = [named]
    assert record_pointers(
        tree(tmp_path / "a", {"AGENTS.md": f"one\ntwo\nsee {named}\n"}), kit_only
    ) == [f"AGENTS.md:3: {named}"]
    # `kit.py` is the manifest: it names the kit's tree
    assert record_pointers(tree(tmp_path / "b", {"kit.py": f"x\ny\n# {named}\n"}), kit_only) == []
    # a line that names the folder
    assert (
        record_pointers(tree(tmp_path / "c", {"AGENTS.md": "see docs/decisions/\n"}), kit_only)
        == []
    )

    # an empty list would pass: the records are there
    under = project.kit_only_docs
    assert len([p for p in under if p.startswith("docs/research/")]) >= 5
    assert len([p for p in under if p.startswith("docs/decisions/")]) >= 10
    assert len([p for p in under if p.startswith("docs/briefs/")]) >= 5
    assert record_pointers(project.root, under) == []


def test_no_file_of_a_project_carries_a_date(project: Project, tmp_path: Path) -> None:
    text = "tested (2026-10-06)\n"
    assert dates(tree(tmp_path / "a", {"docs/kit/HARNESS.md": text})) == [
        "docs/kit/HARNESS.md:1: 2026-10-06"
    ]
    left_out = {"tests/harness/test_review.py": text, "kit.lock": text, "uv.lock": text}
    assert dates(tree(tmp_path / "b", left_out)) == []
    assert dates(tree(tmp_path / "c", {"docs/kit/HARNESS.md": "on 2026-1-6\n"})) == []
    assert dates(project.root) == []


def test_no_file_of_a_project_names_where_the_notes_were(project: Project) -> None:
    named = sorted(
        str(p.relative_to(project.root))
        for p in project.root.rglob("*")
        if p.is_file() and "docs/kit/research" in p.read_text("utf-8", errors="replace")
    )
    assert named == []
