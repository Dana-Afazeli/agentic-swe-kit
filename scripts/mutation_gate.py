"""Fail when mutation testing left mutants that no test is known to catch.

`mutmut run` exits 0 even when mutants survive, so `make mutate` runs this after
`mutmut export-cicd-stats`. A mutant passes only when a test killed it or it timed out (the
mutation made the tests hang, which is a detection). Everything else fails the gate: it survived,
no test reaches it, or its run crashed or was cut short and so proved nothing.

Exit codes: 0 clean, 1 offending mutants or no mutants at all, 2 the stats could not be read
(the gate fails closed: no stats is never a pass).
"""

import json
import subprocess
import sys
from pathlib import Path

STATS_PATH = Path("mutants/mutmut-cicd-stats.json")
# stats key -> the status `mutmut results` prints for a mutant in that state
FAILING = {
    "survived": "survived",
    "no_tests": "no tests",
    "suspicious": "suspicious",
    "segfault": "segfault",
    "check_was_interrupted_by_user": "check was interrupted by user",
}


def read_counts(stats_path: Path) -> dict[str, int]:
    try:
        stats = json.loads(stats_path.read_text("utf-8"))
        return {key: int(stats[key]) for key in ("total", "killed", "timeout", *FAILING)}
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"mutation gate: cannot read {stats_path}: {error!r}", file=sys.stderr)
        print("run `mutmut run` and `mutmut export-cicd-stats` first", file=sys.stderr)
        raise SystemExit(2) from error


def parse_offenders(results_output: str) -> list[str]:
    """Keep the lines of `mutmut results` whose status fails the gate."""
    suffixes = tuple(f": {status}" for status in FAILING.values())
    return [line.strip() for line in results_output.splitlines() if line.strip().endswith(suffixes)]


def offending_mutants() -> list[str]:
    results = subprocess.run(
        [sys.executable, "-m", "mutmut", "results"], capture_output=True, text=True, check=False
    )
    return parse_offenders(results.stdout)


def main(stats_path: Path = STATS_PATH) -> int:
    counts = read_counts(stats_path)
    summary = ", ".join(f"{key}={value}" for key, value in counts.items())
    if counts["total"] == 0:
        print(f"mutation gate: FAIL ({summary}): no mutants were generated", file=sys.stderr)
        return 1
    if not any(counts[key] for key in FAILING):
        print(f"mutation gate: PASS ({summary})")
        return 0
    print(f"mutation gate: FAIL ({summary})", file=sys.stderr)
    for mutant in offending_mutants():
        print(f"  {mutant}", file=sys.stderr)
    print(
        "kill each mutant with a test that asserts on the behaviour, or mark the line "
        "`# pragma: no mutate` with a one-line reason; inspect one with "
        "`uv run mutmut show <name>`",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
