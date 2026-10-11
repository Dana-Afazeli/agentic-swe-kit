"""The integrity check lists vanished tests, new skips and new escape hatches, and fails closed.

The diff cases and the end-to-end repository live in `fixtures/integrity_cases.toml`: this module
is scanned by the gate it tests, so the markers it looks for cannot be written out here.
"""

import subprocess
import tomllib
from pathlib import Path
from typing import Any

import pytest

import integrity

CASES: dict[str, Any] = tomllib.loads(
    (Path(__file__).parent / "fixtures" / "integrity_cases.toml").read_text("utf-8")
)


def case_name(case: dict[str, Any]) -> str:
    return str(case["name"])


def test_vanished_lists_base_ids_missing_now() -> None:
    assert integrity.vanished(
        frozenset({"t/a.py::test_x", "t/a.py::test_y"}), frozenset({"t/a.py::test_x"})
    ) == ["t/a.py::test_y"]


def test_vanished_is_empty_for_the_same_ids() -> None:
    ids = frozenset({"t/a.py::test_x", "t/a.py::test_y"})
    assert integrity.vanished(ids, ids) == []


def test_vanished_ignores_new_ids() -> None:
    assert (
        integrity.vanished(frozenset({"t/a.py::test_x"}), frozenset({"t/a.py::test_x", "n"})) == []
    )


def test_vanished_is_sorted() -> None:
    assert integrity.vanished(frozenset({"b", "c", "a"}), frozenset()) == ["a", "b", "c"]


@pytest.mark.parametrize("case", CASES["new_skips"], ids=case_name)
def test_new_skips(case: dict[str, Any]) -> None:
    assert integrity.new_skips(case["diff"]) == case["findings"]


@pytest.mark.parametrize("case", CASES["new_escapes"], ids=case_name)
def test_new_escapes(case: dict[str, Any]) -> None:
    assert integrity.new_escapes(case["diff"]) == case["findings"]


def test_the_case_file_covers_both_functions() -> None:
    """A typo in a table name would silently parametrize a test over nothing."""
    assert len(CASES["new_skips"]) >= 5
    assert len(CASES["new_escapes"]) >= 5


TREE_TEST = """\
import pytest


def test_a() -> None:
    assert True


@pytest.mark.parametrize("n", [1, 2])
def test_p(n: int) -> None:
    assert n
"""


def test_collect_ids_counts_every_parametrized_case(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_t.py").write_text(TREE_TEST, "utf-8")

    assert integrity.collect_ids(tmp_path) == {
        "tests/test_t.py::test_a",
        "tests/test_t.py::test_p[1]",
        "tests/test_t.py::test_p[2]",
    }
    assert not (tmp_path / ".pytest_cache").exists()
    assert not (tmp_path / "tests" / "__pycache__").exists()


def test_collect_ids_keeps_an_id_with_a_space_whole(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_t.py").write_text(
        'import pytest\n\n\n@pytest.mark.parametrize("s", ["a b"])\n'
        "def test_p(s: str) -> None: ...\n",
        "utf-8",
    )

    assert integrity.collect_ids(tmp_path) == {"tests/test_t.py::test_p[a b]"}


def test_collect_ids_uses_the_trees_own_configuration(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\npython_functions = ["check_*"]\n', "utf-8"
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_t.py").write_text(
        "def check_one() -> None: ...\n\n\ndef test_ignored() -> None: ...\n", "utf-8"
    )

    assert integrity.collect_ids(tmp_path) == {"tests/test_t.py::check_one"}


def test_collect_ids_keeps_a_module_that_fails_to_import_as_one_entry(tmp_path: Path) -> None:
    """Its tests cannot be listed, so the module itself stands in for them."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_ok.py").write_text("def test_a() -> None: ...\n", "utf-8")
    (tmp_path / "tests" / "test_bad.py").write_text(
        'raise RuntimeError("not::an::id")\n\n\ndef test_b() -> None: ...\n', "utf-8"
    )

    assert integrity.collect_ids(tmp_path) == {
        "tests/test_ok.py::test_a",
        "tests/test_bad.py (cannot be collected)",
    }


def test_collect_ids_reports_a_broken_module_when_nothing_else_collects(tmp_path: Path) -> None:
    """With no test ID at all pytest prints no listing; the module must not be lost."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_bad.py").write_text('raise RuntimeError("x")\n', "utf-8")

    assert integrity.collect_ids(tmp_path) == {"tests/test_bad.py (cannot be collected)"}


def test_collect_ids_names_a_broken_module_relative_to_the_tree(tmp_path: Path) -> None:
    """A tree reached through a symlink (macOS temp directories are) is named the same way."""
    tree = tmp_path / "real"
    (tree / "tests").mkdir(parents=True)
    (tree / "tests" / "test_bad.py").write_text('raise RuntimeError("x")\n', "utf-8")
    (tmp_path / "link").symlink_to(tree)

    assert integrity.collect_ids(tmp_path / "link") == {"tests/test_bad.py (cannot be collected)"}


def test_collect_ids_imports_the_trees_own_package_not_the_installed_one(tmp_path: Path) -> None:
    """The base tree's tests import the base tree's `src/`: a module the PR renamed or removed
    must not turn every test that used it into a "vanished" one."""
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "__init__.py").write_text("", "utf-8")
    (tmp_path / "src" / "pkg" / "only_in_this_tree.py").write_text("VALUE = 1\n", "utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_uses_it.py").write_text(
        "from pkg.only_in_this_tree import VALUE\n\n\ndef test_it() -> None:\n    assert VALUE\n",
        "utf-8",
    )

    assert integrity.collect_ids(tmp_path) == {"tests/test_uses_it.py::test_it"}


@pytest.mark.parametrize("addopts", ["-q", "-v", "-ra -q", "-rN -qq", "--strict-markers -vv"])
def test_collect_ids_does_not_depend_on_what_the_tree_makes_pytest_print(
    addopts: str, tmp_path: Path
) -> None:
    """One word in `addopts` changes what pytest prints; it must not empty the set."""
    (tmp_path / "pyproject.toml").write_text(
        f'[tool.pytest.ini_options]\naddopts = "{addopts}"\n', "utf-8"
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_t.py").write_text(TREE_TEST, "utf-8")
    (tmp_path / "tests" / "test_bad.py").write_text('raise RuntimeError("x")\n', "utf-8")

    assert integrity.collect_ids(tmp_path) == {
        "tests/test_t.py::test_a",
        "tests/test_t.py::test_p[1]",
        "tests/test_t.py::test_p[2]",
        "tests/test_bad.py (cannot be collected)",
    }


def test_collect_ids_follows_a_deselection_in_the_trees_options(tmp_path: Path) -> None:
    """A test switched off through `addopts` is no longer collected, so it counts as vanished."""
    (tmp_path / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\naddopts = "-k test_a"\n', "utf-8"
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_t.py").write_text(TREE_TEST, "utf-8")

    assert integrity.collect_ids(tmp_path) == {"tests/test_t.py::test_a"}


MARKED_TEST = """\
import pytest


def test_in_the_gate() -> None: ...


@pytest.mark.eval
def test_behind_eval() -> None: ...


@pytest.mark.live
def test_behind_live() -> None: ...
"""


def test_collect_ids_leaves_out_what_make_check_does_not_run(tmp_path: Path) -> None:
    """`make check` runs pytest with a marker expression. A test moved behind `eval` or `live`
    is still collected without it, and no longer run: it must leave the set."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_t.py").write_text(MARKED_TEST, "utf-8")

    assert integrity.collect_ids(tmp_path) == {"tests/test_t.py::test_in_the_gate"}


def test_collect_ids_puts_the_gates_markers_after_the_trees_own(tmp_path: Path) -> None:
    """As in `make check`, where the `-m` on the command line replaces one in `addopts`."""
    (tmp_path / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\naddopts = "-m eval"\n', "utf-8"
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_t.py").write_text(MARKED_TEST, "utf-8")

    assert integrity.collect_ids(tmp_path) == {"tests/test_t.py::test_in_the_gate"}


def test_collect_ids_is_not_fooled_by_a_module_of_the_same_name_in_the_tree(tmp_path: Path) -> None:
    """The tree puts its own scripts/ on the import path; the collector is not found by name."""
    (tmp_path / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\npythonpath = ["scripts"]\n', "utf-8"
    )
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "integrity.py").write_text('raise RuntimeError("decoy")\n', "utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_t.py").write_text("def test_a() -> None: ...\n", "utf-8")

    assert integrity.collect_ids(tmp_path) == {"tests/test_t.py::test_a"}


def test_collect_ids_cannot_determine_when_pytest_itself_fails(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\naddopts = "--no-such-option"\n', "utf-8"
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_t.py").write_text("def test_a() -> None: ...\n", "utf-8")

    with pytest.raises(integrity.CannotDetermine, match="exit 4"):
        integrity.collect_ids(tmp_path)


def test_collect_ids_is_empty_without_tests(tmp_path: Path) -> None:
    assert integrity.collect_ids(tmp_path) == frozenset()
    (tmp_path / "tests").mkdir()
    assert integrity.collect_ids(tmp_path) == frozenset()


def git(repo: Path, *args: str) -> None:
    identity = ["-c", "user.name=t", "-c", "user.email=t@example.invalid"]
    quiet = ["-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null"]
    subprocess.run(
        ["git", "-C", str(repo), *identity, *quiet, *args], check=True, capture_output=True
    )


def write_files(repo: Path, files: dict[str, str]) -> None:
    for name, content in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, "utf-8")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Branch main holds `base`; the feature branch commits `head`, leaving `untracked` unadded."""
    root = tmp_path / "repo"
    root.mkdir()
    files: dict[str, dict[str, str]] = CASES["end_to_end"]
    git(root, "init", "-q", "-b", "main")
    write_files(root, files["base"])
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "base")
    git(root, "switch", "-q", "-c", "main-999-probe")
    write_files(root, files["head"])
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "head")
    write_files(root, files["untracked"])
    return root


def test_check_reports_all_three_kinds(repo: Path) -> None:
    expected: dict[str, list[str]] = CASES["end_to_end"]["expected"]

    report = integrity.check("main", repo)

    assert report.vanished == expected["vanished"]
    assert report.skips == expected["skips"]
    assert report.escapes == expected["escapes"]
    assert report.findings == len(report.vanished) + len(report.skips) + len(report.escapes) == 10


@pytest.mark.parametrize("attributes", ["*.py -diff\n", "*.py binary\n", "*.py diff=none\n"])
def test_check_reads_the_lines_whatever_gitattributes_says(repo: Path, attributes: str) -> None:
    """With such a line git prints "Binary files differ" and no lines: nothing would be listed,
    and `.gitattributes` is no gate file."""
    expected: dict[str, list[str]] = CASES["end_to_end"]["expected"]
    (repo / ".gitattributes").write_text(attributes, "utf-8")

    report = integrity.check("main", repo)

    assert report.skips == expected["skips"]
    assert report.escapes == expected["escapes"]


def test_check_tests_only_leaves_escape_hatches_to_ci(repo: Path) -> None:
    expected: dict[str, list[str]] = CASES["end_to_end"]["expected"]

    report = integrity.check("main", repo, tests_only=True)

    assert report.vanished == expected["vanished"]
    assert report.skips == expected["skips"]
    assert report.escapes == []


def test_check_compares_with_the_fork_point_not_the_base_tip(repo: Path) -> None:
    """A test added on main after the branch forked has not vanished from the branch."""
    git(repo, "stash", "-q", "--include-untracked")
    git(repo, "switch", "-q", "main")
    write_files(repo, {"tests/test_later.py": "def test_added_on_v2() -> None: ...\n"})
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "main moved on")
    git(repo, "switch", "-q", "main-999-probe")

    assert "tests/test_later.py::test_added_on_v2" not in integrity.check("main", repo).vanished


def test_check_is_clean_on_the_base_itself(repo: Path) -> None:
    git(repo, "stash", "-q", "--include-untracked")
    git(repo, "switch", "-q", "main")

    report = integrity.check("main", repo)

    assert report == integrity.Report(vanished=[], skips=[], escapes=[])
    assert report.findings == 0
    assert not (repo / ".pytest_cache").exists()


def test_check_cannot_determine_an_unknown_base(repo: Path) -> None:
    with pytest.raises(integrity.CannotDetermine, match="no-such-ref"):
        integrity.check("no-such-ref", repo)


def test_main_exits_2_when_the_base_cannot_be_read(capsys: pytest.CaptureFixture[str]) -> None:
    assert integrity.main(["--base", "no-such-ref-for-the-integrity-test"]) == 2
    err = capsys.readouterr().err
    assert err.startswith("integrity: cannot determine: ")
    assert "no-such-ref-for-the-integrity-test" in err


def test_main_exits_2_when_the_check_crashes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A traceback would exit 1, and 1 means "findings": a label could then turn a crash green."""

    def check(
        base: str, root: Path = integrity.ROOT, *, tests_only: bool = False
    ) -> integrity.Report:
        raise IndexError("boom")

    monkeypatch.setattr(integrity, "check", check)

    assert integrity.main(["--base", "origin/main"]) == 2
    assert capsys.readouterr().err == "integrity: cannot determine: IndexError('boom')\n"


def fake_check(monkeypatch: pytest.MonkeyPatch, report: integrity.Report) -> list[tuple[str, bool]]:
    asked: list[tuple[str, bool]] = []

    def check(
        base: str, root: Path = integrity.ROOT, *, tests_only: bool = False
    ) -> integrity.Report:
        assert root == integrity.ROOT
        asked.append((base, tests_only))
        return report

    monkeypatch.setattr(integrity, "check", check)
    return asked


def test_main_exits_0_and_says_so_when_nothing_is_listed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    asked = fake_check(monkeypatch, integrity.Report(vanished=[], skips=[], escapes=[]))

    assert integrity.main(["--base", "origin/main"]) == 0

    assert asked == [("origin/main", False)]
    assert capsys.readouterr().out == "integrity: clean against origin/main\n"


def test_main_exits_1_and_lists_each_finding_under_its_kind(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    report = integrity.Report(
        vanished=["tests/a.py::test_x"],
        skips=["tests/a.py:3: a skip line"],
        escapes=["src/a.py:1: an escape line", "src/a.py:2: another"],
    )
    asked = fake_check(monkeypatch, report)

    assert integrity.main(["--base", "origin/main", "--tests-only"]) == 1

    assert asked == [("origin/main", True)]
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith("integrity: 4 findings against origin/main")
    assert out[1].startswith("vanished tests (1)")
    assert out[2] == "  tests/a.py::test_x"
    assert out[3].startswith("new skip or xfail markers (1)")
    assert out[4] == "  tests/a.py:3: a skip line"
    assert out[5].startswith("new escape-hatch comments (2)")
    assert "moved" in out[5]
    assert out[6:] == ["  src/a.py:1: an escape line", "  src/a.py:2: another"]


def test_main_leaves_out_the_kinds_with_no_finding(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_check(monkeypatch, integrity.Report(vanished=["tests/a.py::test_x"], skips=[], escapes=[]))

    assert integrity.main(["--base", "main"]) == 1

    out = capsys.readouterr().out
    assert out.startswith("integrity: 1 finding against main")
    assert "skip" not in out
    assert "escape" not in out


def test_main_exits_2_without_a_base() -> None:
    with pytest.raises(SystemExit) as raised:
        integrity.main([])
    assert raised.value.code == 2
