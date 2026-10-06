"""The mutation gate turns mutmut's stats file into an exit code, and fails closed."""

import json
from pathlib import Path

import pytest

import mutation_gate

CLEAN = {
    "total": 4,
    "killed": 4,
    "survived": 0,
    "no_tests": 0,
    "skipped": 0,
    "suspicious": 0,
    "timeout": 0,
    "check_was_interrupted_by_user": 0,
    "segfault": 0,
}


def write_stats(directory: Path, **changes: int) -> Path:
    path = directory / "mutmut-cicd-stats.json"
    path.write_text(json.dumps(CLEAN | changes), "utf-8")
    return path


@pytest.fixture(autouse=True)
def no_mutmut_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    def offenders() -> list[str]:
        return ["kitpkg.core.probe.x_add__mutmut_1: survived"]

    monkeypatch.setattr(mutation_gate, "offending_mutants", offenders)


def test_all_killed_passes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert mutation_gate.main(write_stats(tmp_path)) == 0
    assert capsys.readouterr().out.startswith("mutation gate: PASS (total=4, killed=4, timeout=0,")


def test_timeout_counts_as_caught(tmp_path: Path) -> None:
    assert mutation_gate.main(write_stats(tmp_path, killed=3, timeout=1)) == 0


@pytest.mark.parametrize("status", sorted(mutation_gate.FAILING))
def test_each_failing_status_fails(
    status: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert mutation_gate.main(write_stats(tmp_path, killed=3, **{status: 1})) == 1
    err = capsys.readouterr().err
    assert err.startswith("mutation gate: FAIL (")
    assert f"{status}=1" in err
    assert "  kitpkg.core.probe.x_add__mutmut_1: survived\n" in err


def test_failing_statuses_are_the_five_unverified_ones() -> None:
    assert set(mutation_gate.FAILING) == {
        "survived",
        "no_tests",
        "suspicious",
        "segfault",
        "check_was_interrupted_by_user",
    }


def test_no_mutants_at_all_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert mutation_gate.main(write_stats(tmp_path, total=0, killed=0)) == 1
    assert "no mutants were generated" in capsys.readouterr().err


def test_missing_stats_file_exits_2(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as raised:
        mutation_gate.main(tmp_path / "absent.json")
    assert raised.value.code == 2


@pytest.mark.parametrize("content", ["not json", "[]", '{"total": 4}', '{"total": "many"}'])
def test_unreadable_stats_exit_2(content: str, tmp_path: Path) -> None:
    path = tmp_path / "stats.json"
    path.write_text(content, "utf-8")
    with pytest.raises(SystemExit) as raised:
        mutation_gate.main(path)
    assert raised.value.code == 2


def test_parse_offenders_keeps_only_failing_statuses() -> None:
    output = (
        "    kitpkg.main.x_main__mutmut_1: killed\n"
        "    kitpkg.core.a.x_f__mutmut_1: survived\n"
        "    kitpkg.core.a.x_g__mutmut_1: no tests\n"
        "    kitpkg.core.a.x_h__mutmut_1: timeout\n"
        "    kitpkg.core.a.x_i__mutmut_1: segfault\n"
        "    kitpkg.core.a.x_j__mutmut_1: not checked\n"
    )
    assert mutation_gate.parse_offenders(output) == [
        "kitpkg.core.a.x_f__mutmut_1: survived",
        "kitpkg.core.a.x_g__mutmut_1: no tests",
        "kitpkg.core.a.x_i__mutmut_1: segfault",
    ]
