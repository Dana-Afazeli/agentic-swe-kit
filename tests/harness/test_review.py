"""The review launcher: which reviewers run, with which flags, and what it reads off a run."""

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from subprocess import CompletedProcess

import pytest

import review
from review import PullRequest, Record, Spec

HEAD = "a" * 40
ORIGIN = "git@github.com:o/r.git"
PR = PullRequest(
    number=10,
    repo="o/r",
    head=HEAD,
    base="main",
    branch="main-skill-x",
    url="https://github.com/o/r/pull/10",
)
BRIEF = "docs/briefs/000-TEMPLATE.md"  # a file the fake GitHub has at the PR's head
SONNET = "claude-sonnet-5-5"
OPUS = "claude-opus-5-5"


# --- model/effort ---------------------------------------------------------------------------------


def test_a_spec_is_model_slash_effort() -> None:
    assert review.parse_spec("opus/high") == Spec("opus", "high")
    assert review.parse_spec("claude-fable-5-1/xhigh") == Spec("claude-fable-5-1", "xhigh")


@pytest.mark.parametrize("text", ["opus", "opus/", "/high", "opus/extreme", "a/b/high", ""])
def test_a_malformed_spec_is_refused(text: str) -> None:
    with pytest.raises(ValueError, match="MODEL/EFFORT"):
        review.parse_spec(text)


def test_there_is_no_default_model_or_effort() -> None:
    # Decided 2026-10-06: the call names the model and effort of each reviewer, as the brief does.
    call = review.parse_call(["10"])
    assert call.specs == {"plan": None, "code": None}
    assert not hasattr(review, "DEFAULTS")


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["10"], "--plan and --code MODEL/EFFORT are needed: name the model and effort of"),
        (["10", "--plan", "sonnet/medium"], "--code MODEL/EFFORT is needed: name the model"),
        (["10", "--only", "code"], "--code MODEL/EFFORT is needed: name the model and effort of"),
    ],
)
def test_a_reviewer_that_would_run_without_a_named_model_is_refused(
    args: list[str], message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    hub = Hub()
    claude = Claude(hub)
    assert review.main([*args, "--brief", BRIEF], run=hub, launch=claude) == 2
    assert claude.calls == []
    assert hub.clones == {}
    assert message in capsys.readouterr().err


def test_a_reviewer_that_will_not_run_needs_no_model(capsys: pytest.CaptureFixture[str]) -> None:
    earlier = [review.marker(Record("plan", 1, HEAD, "green"))]
    hub = Hub(comments=earlier)
    claude = Claude(hub, code=[turn(OPUS, sub=True), result("VERDICT: GREEN")])
    assert review.main(["10", "--code", "opus/xhigh"], run=hub, launch=claude) == 0
    assert [call[0] for call in claude.calls] == ["code"]


# --- the brief ------------------------------------------------------------------------------------


def test_the_brief_is_found_from_the_branch_number() -> None:
    # the names are those of `docs/briefs` at the PR's head, as GitHub lists them
    names = ["000-TEMPLATE.md", "006-dm-live.md", "007-other.md", "006-notes.txt"]
    assert review.find_brief("main-006-dm-live", names) == Path("docs/briefs/006-dm-live.md")
    assert review.find_brief("main-008-none", names) is None
    assert review.find_brief("main-skill-review-loop", names) is None


def test_two_briefs_with_one_number_is_no_answer() -> None:
    assert review.find_brief("main-006-a", ["006-a.md", "006-b.md"]) is None


# --- records on the PR: the memory between rounds ----------------------------------------------


def test_a_record_marker_reads_back() -> None:
    record = Record("code", 2, HEAD, "findings:3")
    body = review.marker(record) + "\n**[code-review]** text"
    assert review.read_records(["a comment by the maintainer", body]) == [record]


def test_a_marker_counts_only_at_the_start_of_a_comment() -> None:
    quoted = "the maintainer wrote:\n" + review.marker(Record("plan", 1, HEAD, "green"))
    assert review.read_records([quoted]) == []


def records(*items: tuple[str, int, str]) -> list[Record]:
    return [Record(reviewer, round_, HEAD, verdict) for reviewer, round_, verdict in items]


def test_round_one_runs_both_reviewers_plan_first() -> None:
    to_run = [("plan", 1), ("code", 1)]
    assert review.select([], ["plan", "code"], expired=[], rounds=3, head=HEAD) == (to_run, [])


def test_a_green_reviewer_is_not_run_again() -> None:
    seen = records(("plan", 1, "green"), ("code", 1, "findings:2"))
    to_run, notes = review.select(seen, ["plan", "code"], expired=[], rounds=3, head=HEAD)
    assert to_run == [("code", 2)]
    assert notes == ["plan-reviewer: green in round 1, not run again"]


def test_a_green_from_an_older_head_is_kept_and_said_to_be_older() -> None:
    # PR #11 review, round 1: a green is not tied to a head. It still stops the reviewer (the
    # loop's rule), but the call now says that commits have landed since, and how to run it again.
    seen = [Record("code", 1, "b" * 40, "green")]
    to_run, notes = review.select(seen, ["code"], expired=[], rounds=3, head=HEAD)
    assert to_run == []
    assert notes == [
        "code-review: green in round 1 at bbbbbbb, not run again; the head has moved since: "
        "decide whether that changed what it reviewed, and if so pass --expire code"
    ]


def test_a_record_with_a_short_head_is_not_taken_for_an_older_one() -> None:
    # PR #11 review, round 2: a marker may carry 7 digits of the head, and 7 never equal 40.
    seen = [Record("code", 1, "a" * 7, "green")]
    notes = review.select(seen, ["code"], expired=[], rounds=3, head=HEAD)[1]
    assert notes == ["code-review: green in round 1, not run again"]


def test_of_two_records_for_one_round_the_later_comment_counts() -> None:
    # PR #11 review, round 1: on a tie the older record won.
    seen = records(("code", 1, "findings:2"), ("code", 1, "green"))
    assert review.select(seen, ["code"], expired=[], rounds=3, head=HEAD)[0] == []
    seen = records(("code", 1, "green"), ("code", 1, "findings:2"))
    assert review.select(seen, ["code"], expired=[], rounds=3, head=HEAD)[0] == [("code", 2)]


def test_the_latest_round_decides_not_the_order_of_the_comments() -> None:
    seen = records(("code", 2, "green"), ("code", 1, "findings:2"))
    assert review.select(seen, ["code"], expired=[], rounds=3, head=HEAD)[0] == []


@pytest.mark.parametrize("verdict", ["findings:1", "unknown", "failed"])
def test_a_reviewer_that_used_its_rounds_is_not_run(verdict: str) -> None:
    seen = records(("code", 1, "findings:4"), ("code", 2, "findings:1"), ("code", 3, verdict))
    to_run, notes = review.select(seen, ["code"], expired=[], rounds=3, head=HEAD)
    assert to_run == []
    assert notes == [
        "code-review: 3 of 3 rounds used and not green: stop and report to the maintainer"
    ]


def test_the_number_of_rounds_is_what_the_call_says() -> None:
    seen = records(("code", 1, "findings:4"), ("code", 2, "findings:1"))
    assert review.select(seen, ["code"], expired=[], rounds=5, head=HEAD) == ([("code", 3)], [])
    to_run, notes = review.select(seen, ["code"], expired=[], rounds=2, head=HEAD)
    assert to_run == []
    assert notes == [
        "code-review: 2 of 2 rounds used and not green: stop and report to the maintainer"
    ]
    assert review.select([], ["code"], expired=[], rounds=1, head=HEAD) == ([("code", 1)], [])


def test_three_rounds_is_only_the_default() -> None:
    assert review.DEFAULT_ROUNDS == 3
    assert review.parse_call(["10"]).rounds == 3
    assert review.parse_call(["10", "--rounds", "5"]).rounds == 5


@pytest.mark.parametrize("rounds", ["0", "-1", "two"])
def test_a_number_of_rounds_below_one_is_refused(rounds: str) -> None:
    with pytest.raises(SystemExit) as stop:
        review.parse_call(["10", "--rounds", rounds])
    assert stop.value.code == 2


@pytest.mark.parametrize("option", ["--timeout-min", "--budget-usd"])
@pytest.mark.parametrize("value", ["0", "-5", "none", "nan", "inf"])
def test_a_limit_of_zero_or_less_is_refused(option: str, value: str) -> None:
    # PR #11 review, round 1: 0 was taken as "not given" and became the default; -5 was accepted.
    # Round 2: nothing pinned that "not a number" and "no limit at all" are refused too.
    with pytest.raises(SystemExit) as stop:
        review.parse_call(["10", option, value])
    assert stop.value.code == 2


def test_limits_are_kept_as_given() -> None:
    call = review.parse_call(["10", "--timeout-min", "1", "--budget-usd", "0.5"])
    assert (call.timeout_min, call.budget_usd) == (1, 0.5)
    assert (review.parse_call(["10"]).timeout_min, review.parse_call(["10"]).budget_usd) == (
        None,
        None,
    )


def test_an_expired_green_does_not_stop_the_reviewer() -> None:
    # Decided 2026-10-06: whether the commits since a green changed what that reviewer reviewed is
    # the implementer's judgment, and `--expire <reviewer>` is how it tells the launcher.
    seen = records(("plan", 1, "green"), ("code", 1, "green"))
    to_run, notes = review.select(seen, ["plan", "code"], expired=["code"], rounds=3, head=HEAD)
    assert to_run == [("code", 2)]
    assert notes == ["plan-reviewer: green in round 1, not run again"]


def test_expiring_a_green_does_not_lift_the_round_limit() -> None:
    seen = records(("code", 3, "green"))
    to_run, notes = review.select(seen, ["code"], expired=["code"], rounds=3, head=HEAD)
    assert to_run == []
    assert notes == [
        "code-review: green in round 3, expired, and 3 of 3 rounds used: --rounds N allows more"
    ]
    assert review.select(seen, ["code"], expired=["code"], rounds=4, head=HEAD)[0] == [("code", 4)]


def test_expiring_a_reviewer_that_is_not_green_changes_nothing() -> None:
    seen = records(("code", 1, "findings:2"))
    assert review.select(seen, ["code"], expired=["code"], rounds=3, head=HEAD) == (
        [("code", 2)],
        [],
    )


# --- the verdict line -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("report", "expected"),
    [
        ("No gaps.\n\nVERDICT: GREEN", "green"),
        ("1. a\n2. b\nVERDICT: FINDINGS 2\n", "findings:2"),
        ("VERDICT: FINDINGS 1\nlater text\nVERDICT: GREEN\n", "green"),  # the last one counts
        ("  VERDICT: GREEN  ", "green"),
        ("the line `VERDICT: GREEN` is quoted in prose", "unknown"),
        ("VERDICT: FINDINGS", "unknown"),
        ("VERDICT: FINDINGS 0", "unknown"),  # nothing found is GREEN, so this is neither
        ("", "unknown"),
    ],
)
def test_the_verdict_is_the_last_verdict_line(report: str, expected: str) -> None:
    assert review.parse_verdict(report) == expected


# --- reading a run's record -----------------------------------------------------------------------


def turn(model: str, *, sub: bool = False, tool: str | None = None) -> str:
    content: list[dict[str, object]] = [{"type": "text", "text": "x"}]
    if tool is not None:
        content.append({"type": "tool_use", "name": tool, "input": {}})
    return json.dumps(
        {
            "type": "assistant",
            "parent_tool_use_id": "toolu_1" if sub else None,
            "message": {"model": model, "content": content},
        }
    )


def result(report: str, **over: object) -> str:
    line: dict[str, object] = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "total_cost_usd": 0.5,
        "duration_ms": 30500,
        "permission_denials": [],
        "result": report,
    }
    return json.dumps({**line, **over})


PLAN_GREEN = [turn(SONNET), turn(SONNET), result("No gaps.\nVERDICT: GREEN")]
CODE_FINDINGS = [
    turn("<synthetic>"),
    turn(OPUS, sub=True),
    turn(OPUS, sub=True),
    result("1. a\n2. b\nVERDICT: FINDINGS 2"),
]


def test_a_plan_run_is_read_from_the_main_turns() -> None:
    outcome = review.read_outcome(PLAN_GREEN, "plan")
    assert outcome.answered == {SONNET: 2}
    assert (outcome.verdict, outcome.problem) == ("green", None)
    assert (outcome.cost_usd, outcome.duration_s) == (0.5, 30.5)
    assert (outcome.advisor_calls, outcome.denied) == (0, [])
    assert outcome.report == "No gaps.\nVERDICT: GREEN"


def test_a_code_run_is_read_from_the_subagent_turns() -> None:
    outcome = review.read_outcome(CODE_FINDINGS, "code")
    assert outcome.answered == {OPUS: 2}
    assert (outcome.verdict, outcome.problem) == ("findings:2", None)


def test_the_other_role_does_not_count_as_the_reviewer() -> None:
    lines = [turn(SONNET), turn(OPUS, sub=True), result("VERDICT: GREEN")]
    assert review.read_outcome(lines, "plan").answered == {SONNET: 1}
    assert review.read_outcome(lines, "code").answered == {OPUS: 1}


def test_the_models_that_answered_are_reported_and_judged_by_nobody() -> None:
    # Decided 2026-10-06: the implementer names the reviewer's model when it starts it, and that is
    # the requirement met. The record says which models answered; no run fails over it.
    lines = [turn(OPUS, sub=True), turn(OPUS, sub=True), turn(SONNET, sub=True)]
    outcome = review.read_outcome([*lines, result("VERDICT: GREEN")], "code")
    assert outcome.answered == {OPUS: 2, SONNET: 1}
    assert (outcome.verdict, outcome.problem) == ("green", None)
    assert f"answered {OPUS} x2, {SONNET} x1" in review.stats(Spec("opus", "xhigh"), outcome)


def test_advisor_calls_are_counted_in_every_role() -> None:
    lines = [turn(SONNET, tool="advisor"), turn(SONNET, sub=True, tool="advisor"), turn(SONNET)]
    assert review.read_outcome([*lines, result("VERDICT: GREEN")], "plan").advisor_calls == 2


def test_denied_tool_calls_are_listed() -> None:
    denials = [
        {"tool_name": "Bash", "tool_input": {"command": "git commit -m x"}},
        {"tool_name": "Write", "tool_input": {"file_path": "/repo/a.py"}},
    ]
    lines = [turn(SONNET), result("VERDICT: GREEN", permission_denials=denials)]
    outcome = review.read_outcome(lines, "plan")
    assert outcome.denied == ["Bash: git commit -m x", "Write: /repo/a.py"]


def test_a_record_without_a_result_line_is_a_failed_run() -> None:
    outcome = review.read_outcome([turn(SONNET)], "plan")
    assert outcome.verdict == "failed"
    assert outcome.problem == "the record has no result line: the process ended early"


def test_an_error_result_is_a_failed_run() -> None:
    lines = [turn(SONNET), result("", is_error=True, subtype="error_max_budget_usd")]
    outcome = review.read_outcome(lines, "plan")
    assert outcome.verdict == "failed"
    assert outcome.problem == "the run ended with an error (error_max_budget_usd)"


def test_a_result_with_no_reviewer_turn_is_a_failed_run() -> None:
    outcome = review.read_outcome([turn("<synthetic>"), result("VERDICT: GREEN")], "code")
    assert outcome.verdict == "failed"
    assert outcome.problem == "the record holds no turn by the reviewer"


def test_lines_that_are_not_json_objects_are_skipped() -> None:
    lines = ["", "not json", "[1, 2]", '{"type": "assistant"', *PLAN_GREEN]
    assert review.read_outcome(lines, "plan").verdict == "green"


# --- the command line for each reviewer -----------------------------------------------------------


def flag(argv: list[str], name: str) -> str:
    return argv[argv.index(name) + 1]


def values(argv: list[str], name: str) -> list[str]:
    start = argv.index(name) + 1
    stop = next((i for i in range(start, len(argv)) if argv[i].startswith("--")), len(argv))
    return argv[start:stop]


def test_the_plan_reviewer_runs_as_its_agent_with_the_model_and_effort_named() -> None:
    argv = review.claude_argv("plan", Spec("opus", "low"), PR, 2, budget=1.5, root=Path("/repo"))
    assert argv[:4] == ["claude", "-p", "--agent", "plan-reviewer"]
    assert (flag(argv, "--model"), flag(argv, "--effort")) == ("opus", "low")
    assert flag(argv, "--max-budget-usd") == "1.5"
    assert flag(argv, "-n") == "review-loop: plan-reviewer, PR 10, round 2"
    assert "--append-subagent-system-prompt-file" not in argv


def test_the_code_review_is_the_bundled_skill_with_the_effort_as_its_level() -> None:
    argv = review.claude_argv(
        "code",
        Spec("opus", "xhigh"),
        PR,
        1,
        budget=10,
        root=Path("/repo"),
        protocol=Path("/work/protocol.md"),
        probes=Path("/work/probes"),
    )
    assert argv[:3] == ["claude", "-p", "/code-review xhigh --comment 10"]
    assert (flag(argv, "--model"), flag(argv, "--effort")) == ("opus", "xhigh")
    assert flag(argv, "--append-subagent-system-prompt-file") == "/work/protocol.md"
    assert flag(argv, "--add-dir") == "/work/probes"
    assert values(argv, "--allowedTools") == ["Bash(gh api:*)", "Write(//work/probes/**)"]
    assert "--agent" not in argv


@pytest.mark.parametrize("reviewer", ["plan", "code"])
def test_every_reviewer_process_gets_the_same_controls(reviewer: str) -> None:
    argv = review.claude_argv(
        reviewer,
        Spec("opus", "high"),
        PR,
        1,
        budget=2,
        root=Path("/repo"),
        protocol=Path("/work/protocol.md"),
        probes=Path("/work/probes"),
    )
    # the project pin on subagent models is overridden for this process, and the advisor is off
    assert json.loads(flag(argv, "--settings")) == {
        "env": {"CLAUDE_CODE_SUBAGENT_MODEL": "opus", "CLAUDE_CODE_DISABLE_ADVISOR_TOOL": "1"}
    }
    assert flag(argv, "--permission-mode") == "auto"
    assert flag(argv, "--permission-prompts") == "none"
    assert "--strict-mcp-config" in argv
    assert flag(argv, "--output-format") == "stream-json"
    assert "--verbose" in argv
    denied = values(argv, "--disallowedTools")
    for rule in (
        "Bash(git commit:*)",
        "Bash(git switch:*)",
        "Bash(git push:*)",
        "Bash(gh pr merge:*)",
        "Bash(claude:*)",  # a process the reviewer starts itself is outside the spending cap
    ):
        assert rule in denied
    assert "Edit(//repo/**)" in denied  # the edit tools, inside the repository


# --- what the reviewers are told ------------------------------------------------------------------


def test_the_plan_prompt_names_the_brief_the_pr_and_the_verdict_line() -> None:
    prompt = review.plan_prompt(PR, Path("docs/briefs/006-dm-live.md"), 1, 3)
    assert "Brief: docs/briefs/006-dm-live.md" in prompt
    # the base is named as the clone has it: a local `main` may be missing or stale (PR #11 review)
    assert f"PR: 10 (head {HEAD}, base origin/main)" in prompt
    assert "VERDICT: GREEN" in prompt
    assert "VERDICT: FINDINGS <number of findings>" in prompt
    assert "earlier" not in prompt


def test_from_round_two_the_plan_prompt_points_at_the_earlier_reports() -> None:
    prompt = review.plan_prompt(PR, Path("docs/briefs/006-dm-live.md"), 2, 5)
    assert "Round 2 of at most 5" in prompt
    assert "gh pr view 10 --comments" in prompt


def test_the_protocol_file_has_every_placeholder_and_none_is_left_after_filling() -> None:
    template = review.PROTOCOL.read_text("utf-8")
    for name in review.PLACEHOLDERS:
        assert "{{" + name + "}}" in template, name
    text = review.render_protocol(template, PR, 2, 5, Path("/work/probes"))
    assert "{{" not in text
    assert "round 2 of at most 5" in text
    assert "repos/o/r/pulls/10/comments" in text
    assert 'repository(owner:"o", name:"r")' in text
    assert "/work/probes" in text
    assert f"at head `{HEAD}` (base `origin/main`)" in text


# --- the record comment ---------------------------------------------------------------------------


def test_the_record_comment_starts_with_the_marker_and_carries_the_report() -> None:
    outcome = review.read_outcome(CODE_FINDINGS, "code")
    record = Record("code", 1, HEAD, outcome.verdict)
    body = review.record_body(record, Spec("opus", "high"), outcome)
    assert review.read_records([body]) == [record]
    assert "**[code-review · round 1 · head `aaaaaaa`] FINDINGS 2**" in body
    assert f"asked opus/high · answered {OPUS} x2 · $0.50 · 30 s" in body
    assert "advisor calls 0 · denied tool calls 0" in body
    assert body.rstrip().endswith("VERDICT: FINDINGS 2")


def test_a_failed_run_says_why_in_its_record() -> None:
    outcome = review.read_outcome([turn(SONNET)], "plan")
    body = review.record_body(Record("plan", 1, HEAD, "failed"), Spec("sonnet", "medium"), outcome)
    assert "] FAILED**" in body
    assert "the record has no result line: the process ended early" in body


def test_a_report_too_long_for_a_comment_is_cut_and_marked() -> None:
    outcome = review.read_outcome([turn(SONNET), result("x" * 70000)], "plan")
    body = review.record_body(Record("plan", 1, HEAD, "unknown"), Spec("sonnet", "medium"), outcome)
    assert len(body) < 65536
    assert body.rstrip().endswith("[…] (cut: the whole report is in the run's folder)")


# --- running a process ----------------------------------------------------------------------------


def test_a_process_writes_its_record_and_returns_its_exit_code(tmp_path: Path) -> None:
    code = (
        "import sys; print(sys.stdin.read().upper()); print('oops', file=sys.stderr); sys.exit(3)"
    )
    assert review.launch_claude([sys.executable, "-c", code], "hello", tmp_path, tmp_path, 30) == 3
    assert (tmp_path / review.RECORD).read_text() == "HELLO\n"
    assert (tmp_path / review.STDERR).read_text() == "oops\n"


def test_a_process_with_no_prompt_gets_an_empty_stdin(tmp_path: Path) -> None:
    code = "import sys; print(repr(sys.stdin.read()))"
    assert review.launch_claude([sys.executable, "-c", code], "", tmp_path, tmp_path, 30) == 0
    assert (tmp_path / review.RECORD).read_text() == "''\n"


def test_a_process_that_runs_past_its_time_is_stopped(tmp_path: Path) -> None:
    code = "import time; print('started', flush=True); time.sleep(30)"
    assert review.launch_claude([sys.executable, "-c", code], "", tmp_path, tmp_path, 1) is None
    assert (tmp_path / review.RECORD).read_text() == "started\n"


def test_a_process_runs_in_its_clone_and_not_in_the_launchers_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clone = tmp_path / "clone"
    clone.mkdir()
    monkeypatch.setenv("VIRTUAL_ENV", str(review.ROOT / ".venv"))
    code = "import os; print(os.getcwd()); print(os.environ.get('VIRTUAL_ENV'))"
    assert review.launch_claude([sys.executable, "-c", code], "", tmp_path, clone, 30) == 0
    assert (tmp_path / review.RECORD).read_text().splitlines() == [str(clone), "None"]


def test_the_reviewers_environment_leaves_out_the_launchers_virtual_environment() -> None:
    # The launcher runs under `uv run`, so its environment names its own .venv and puts that
    # first on the PATH. In a clone, a bare `python` would then import the launcher's checkout.
    environ = {
        "VIRTUAL_ENV": "/work/checkout/.venv",
        "PATH": "/work/checkout/.venv/bin:/usr/bin:/bin",
        "HOME": "/home/x",
    }
    assert review.reviewer_env(environ, Path("/work/checkout")) == {
        "PATH": "/usr/bin:/bin",
        "HOME": "/home/x",
    }
    assert review.reviewer_env({"HOME": "/home/x"}, Path("/work")) == {"HOME": "/home/x"}
    # only that environment's own entries go: a folder that merely starts with its name stays
    neighbours = {"PATH": "/work/checkout/.venv:/work/checkout/.venv-other/bin:/bin"}
    assert review.reviewer_env(neighbours, Path("/work/checkout")) == {
        "PATH": "/work/checkout/.venv-other/bin:/bin"
    }


def test_a_command_that_does_not_come_back_is_stopped(monkeypatch: pytest.MonkeyPatch) -> None:
    # PR #11 review, round 3: `git clone`, `uv sync` and `gh` ran with no limit of their own,
    # outside the two reviewers' time limits.
    monkeypatch.setattr(review, "COMMAND_TIMEOUT_S", 1)
    hung = review.run_in_root([sys.executable, "-c", "import time; time.sleep(30)"])
    assert hung.returncode == 124
    assert hung.stderr == "no answer after 1 s"
    assert review.run_in_root([sys.executable, "-c", "print('ok')"]).stdout == "ok\n"


# --- the reviewer's clone -------------------------------------------------------------------------


def git(*args: str, cwd: Path) -> str:
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)
    return done.stdout.strip()


IDENTITY = ("-c", "user.name=t", "-c", "user.email=t@example.invalid")


@pytest.fixture
def origin(tmp_path: Path) -> tuple[Path, PullRequest]:
    """A bare repository with a base branch and the PR's branch, and the PR as GitHub gives it."""
    seed = tmp_path / "seed"
    seed.mkdir()
    git("init", "--quiet", "--initial-branch", "main", cwd=seed)
    git(*IDENTITY, "commit", "--quiet", "--allow-empty", "-m", "base", cwd=seed)
    git("switch", "--quiet", "-c", PR.branch, cwd=seed)
    git(*IDENTITY, "commit", "--quiet", "--allow-empty", "-m", "the work", cwd=seed)
    bare = tmp_path / "origin.git"
    git("clone", "--quiet", "--bare", str(seed), str(bare), cwd=tmp_path)
    return bare, replace(PR, head=git("rev-parse", PR.branch, cwd=bare))


def test_a_clone_is_the_prs_branch_at_the_prs_head(origin: tuple[Path, PullRequest]) -> None:
    bare, pr = origin
    clone = bare.parent / "run" / "clone"
    review.make_clone(review.run_in_root, str(bare), pr, clone)
    assert git("rev-parse", "HEAD", cwd=clone) == pr.head
    assert git("branch", "--show-current", cwd=clone) == pr.branch
    assert git("rev-parse", "--verify", "origin/main", cwd=clone)  # the base, to diff against


def test_a_commit_in_a_clone_does_not_get_out_by_an_ordinary_push(
    origin: tuple[Path, PullRequest],
) -> None:
    # A reviewer may commit in its clone; that reaches nobody. Two things stand between the clone
    # and the origin: `origin` has no push address, and a pre-push hook refuses every push, also
    # one to an address typed out (PR #11 review, round 3: that one got through).
    bare, pr = origin
    clone = bare.parent / "run" / "clone"
    review.make_clone(review.run_in_root, str(bare), pr, clone)
    git(*IDENTITY, "commit", "--quiet", "--allow-empty", "-m", "by the reviewer", cwd=clone)
    for spelling in (
        ["push"],
        ["push", "origin", "HEAD"],
        ["-C", ".", "push", "origin", f"HEAD:{pr.branch}"],
        ["push", "--force", "origin", f"HEAD:refs/heads/{pr.base}"],
        ["push", str(bare), f"HEAD:{pr.branch}"],
        ["push", "--force", str(bare), f"HEAD:refs/heads/{pr.base}"],
    ):
        pushed = subprocess.run(["git", *spelling], cwd=clone, capture_output=True, check=False)
        assert pushed.returncode != 0, spelling
    assert git("rev-parse", pr.branch, cwd=bare) == pr.head
    assert git("log", "--format=%s", "-1", pr.base, cwd=bare) == "base"
    assert git("fetch", "--quiet", "origin", cwd=clone) == ""  # reading the origin still works


def test_a_push_made_on_purpose_still_gets_out_of_a_clone(
    origin: tuple[Path, PullRequest],
) -> None:
    # The limit, pinned so that no text calls the clone a wall for pushes: the reviewer process
    # has the user's credentials, and a push with the address typed out and the hook switched off
    # is a push like any other. The docs say so.
    bare, pr = origin
    clone = bare.parent / "run" / "clone"
    review.make_clone(review.run_in_root, str(bare), pr, clone)
    git(*IDENTITY, "commit", "--quiet", "--allow-empty", "-m", "by the reviewer", cwd=clone)
    git("push", "--quiet", "--no-verify", str(bare), f"HEAD:{pr.branch}", cwd=clone)
    assert git("log", "--format=%s", "-1", pr.branch, cwd=bare) == "by the reviewer"


def test_a_clone_without_the_prs_base_is_refused(origin: tuple[Path, PullRequest]) -> None:
    # PR #11 review, round 3: only the head was checked. The reviewers are told `origin/<base>`,
    # and the Stop hook in the clone needs it too.
    bare, pr = origin
    clone = bare.parent / "run" / "clone"
    with pytest.raises(review.Refused, match="the clone has no origin/v9"):
        review.make_clone(review.run_in_root, str(bare), replace(pr, base="v9"), clone)


def test_a_clone_replaces_what_an_earlier_run_left_in_its_place(
    origin: tuple[Path, PullRequest],
) -> None:
    bare, pr = origin
    clone = bare.parent / "run" / "clone"
    clone.mkdir(parents=True)
    (clone / "left-over.txt").write_text("from a run that was stopped")
    review.make_clone(review.run_in_root, str(bare), pr, clone)
    assert not (clone / "left-over.txt").exists()
    assert git("rev-parse", "HEAD", cwd=clone) == pr.head


def test_a_clone_that_is_not_at_the_prs_head_is_refused(origin: tuple[Path, PullRequest]) -> None:
    bare, pr = origin
    clone = bare.parent / "run" / "clone"
    with pytest.raises(review.Refused, match="the PR's head moved while the clone was made"):
        review.make_clone(review.run_in_root, str(bare), replace(pr, head="0" * 40), clone)


# --- the whole call -------------------------------------------------------------------------------


def done(args: list[str], out: str = "", code: int = 0, err: str = "") -> CompletedProcess[str]:
    return CompletedProcess(args, code, stdout=out, stderr=err)


class Hub:
    """Stands in for git, gh and uv: one pull request on GitHub, the launcher's checkout, and the
    clones made for the reviewers."""

    def __init__(
        self,
        *,
        state: str = "OPEN",
        branch: str = PR.branch,
        local_head: str = HEAD,
        dirty: str = "",
        comments: list[str] | None = None,
        post_fails: bool = False,
        inline_fails_from: int | None = None,
        briefs: tuple[str, ...] = ("000-TEMPLATE.md",),
        contents_error: str | None = None,
        origin: str = ORIGIN,
        clone_fails_from: int | None = None,
        clone_head: str = HEAD,
        base_missing: bool = False,
        sync_fails: bool = False,
        changed_files: list[str] | None = None,
    ) -> None:
        # what GitHub lists as changed between an older head and the PR's head
        self.changed_files = (
            ["docs/x.md", "src/a.py", "tests/t.py"] if changed_files is None else changed_files
        )
        self.state = state
        self.branch = branch  # of the launcher's checkout
        self.local_head = local_head
        self.dirty = dirty
        self.briefs = briefs  # the names in docs/briefs at the PR's head
        self.contents_error = contents_error  # what gh says when GitHub cannot be asked
        self.origin = origin  # of the launcher's checkout
        self.clone_fails_from = clone_fails_from  # the n-th clone fails, and those after it
        self.clone_head = clone_head  # where a fresh clone ends up
        self.base_missing = base_missing  # a clone has no origin/<base>
        self.sync_fails = sync_fails
        self.clones: dict[str, str] = {}  # clone -> its HEAD
        self.clone_changes: dict[str, str] = {}  # clone -> `git status --porcelain`
        self.push_urls: dict[str, str] = {}
        self.synced: list[str] = []
        self.comments = list(comments or [])
        self.post_fails = post_fails
        self.inline_fails_from = inline_fails_from  # the n-th count of inline comments fails
        self.inline_counts = 0
        self.posted: list[str] = []
        self.inline = 0
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str]) -> CompletedProcess[str]:
        self.calls.append(args)
        if args[:3] == ["gh", "pr", "view"]:
            pr = {
                "number": PR.number,
                "state": self.state,
                "headRefOid": PR.head,
                "headRefName": PR.branch,
                "baseRefName": PR.base,
                "url": PR.url,
            }
            return done(args, json.dumps(pr))
        if args[:2] == ["git", "-C"]:
            return self.in_clone(args[2], args[3:], args)
        if args == ["git", "branch", "--show-current"]:
            return done(args, self.branch + "\n")
        if args[:2] == ["git", "rev-parse"]:
            return done(args, self.local_head + "\n")
        if args[:2] == ["git", "status"]:
            return done(args, self.dirty)
        if args == ["git", "remote", "get-url", "origin"]:
            return done(args, self.origin + "\n")
        if args[:2] == ["git", "clone"]:
            assert args[2:-1] == ["--quiet", "--branch", PR.branch, self.origin], args
            if self.clone_fails_from is not None and len(self.clones) + 1 >= self.clone_fails_from:
                return done(args, code=128, err="fatal: Could not read from remote repository.")
            Path(args[-1]).mkdir(parents=True)
            self.clones[args[-1]] = self.clone_head
            return done(args)
        if args[:2] == ["gh", "api"] and args[2].startswith("repos/o/r/compare/"):
            older, _, newer = args[2].removeprefix("repos/o/r/compare/").partition("...")
            assert (len(older), newer) == (40, PR.head), args
            assert args[3:] == ["--jq", ".files[].filename"], args
            return done(args, "".join(f"{name}\n" for name in self.changed_files))
        if args[:2] == ["uv", "sync"]:
            assert args[2:-1] == ["--locked", "--all-groups", "--quiet", "--project"], args
            if self.sync_fails:
                return done(args, code=2, err="error: the lockfile needs to be updated")
            self.synced.append(args[-1])
            return done(args)
        if args[:2] == ["gh", "api"] and args[2].startswith("repos/o/r/contents/"):
            path, _, ref = args[2].removeprefix("repos/o/r/contents/").partition("?ref=")
            assert ref == PR.head, args
            if self.contents_error:
                return done(args, code=1, err=self.contents_error)
            if path == "docs/briefs":
                return done(args, "".join(f"{name}\n" for name in self.briefs))
            if path.removeprefix("docs/briefs/") in self.briefs:
                return done(args, path + "\n")
            return done(args, code=1, err="gh: Not Found (HTTP 404)")
        if args[:3] == ["gh", "api", "repos/o/r/pulls/10/comments"]:
            # Findings only: a reply has `in_reply_to_id`, and the author may answer while a
            # review runs (PR #11 review, round 3: of 30 inline comments 15 were replies).
            top_level = ".[] | select(.in_reply_to_id == null) | .id"
            assert args[3:] == ["--paginate", "--jq", top_level], args
            self.inline_counts += 1
            if self.inline_fails_from is not None and self.inline_counts >= self.inline_fails_from:
                return done(args, code=1, err="HTTP 503")
            return done(args, "".join(f"{number}\n" for number in range(self.inline)))
        if args[:3] == ["gh", "api", "repos/o/r/issues/10/comments"]:
            bodies = [arg.removeprefix("body=@") for arg in args if arg.startswith("body=@")]
            if not bodies:
                return done(args, "".join(json.dumps(body) + "\n" for body in self.comments))
            if self.post_fails:
                return done(args, code=1, err="HTTP 502")
            body = Path(bodies[0]).read_text("utf-8")
            self.posted.append(body)
            self.comments.append(body)
            return done(args, f"{PR.url}#issuecomment-{len(self.posted)}\n")
        raise AssertionError(f"unexpected command: {args}")

    def in_clone(self, clone: str, rest: list[str], args: list[str]) -> CompletedProcess[str]:
        if clone not in self.clones:
            return done(args, code=128, err="fatal: not a git repository")
        if rest == ["rev-parse", "HEAD"]:
            return done(args, self.clones[clone] + "\n")
        if rest == ["rev-parse", "--verify", "--quiet", f"origin/{PR.base}"]:
            return done(args, code=1) if self.base_missing else done(args, "b" * 40 + "\n")
        if rest == ["status", "--porcelain"]:
            return done(args, self.clone_changes.get(clone, ""))
        if rest[:4] == ["remote", "set-url", "--push", "origin"]:
            self.push_urls[clone] = rest[4]
            return done(args)
        raise AssertionError(f"unexpected command in a clone: {args}")


class Claude:
    """Stands in for the reviewer processes: writes a canned record for each."""

    def __init__(
        self,
        hub: Hub,
        *,
        plan: list[str] | None = None,
        code: list[str] | None = None,
        exit_code: int | None = 0,
        inline_added: int = 0,
        moves_head: dict[str, str] | None = None,
        leaves: dict[str, str] | None = None,
    ) -> None:
        self.hub = hub
        self.records = {"plan": plan or PLAN_GREEN, "code": code or CODE_FINDINGS}
        self.exit_code = exit_code
        self.inline_added = inline_added
        self.moves_head = moves_head or {}  # reviewer -> the commit its clone is on afterwards
        self.leaves = leaves or {}  # reviewer -> `git status --porcelain` of its clone afterwards
        self.calls: list[tuple[str, list[str], str, Path, int, Path]] = []

    def __call__(
        self, argv: list[str], prompt: str, run_dir: Path, cwd: Path, timeout_s: int
    ) -> int | None:
        reviewer = "plan" if "--agent" in argv else "code"
        assert cwd.is_dir(), "the reviewer starts in a clone that exists"
        self.calls.append((reviewer, argv, prompt, run_dir, timeout_s, cwd))
        (run_dir / review.RECORD).write_text("\n".join(self.records[reviewer]) + "\n", "utf-8")
        if reviewer == "code":
            self.hub.inline += self.inline_added
        if reviewer in self.moves_head:
            self.hub.clones[str(cwd)] = self.moves_head[reviewer]
        if reviewer in self.leaves:
            self.hub.clone_changes[str(cwd)] = self.leaves[reviewer]
        return self.exit_code


@pytest.fixture(autouse=True)
def work(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(review, "WORK", tmp_path / "work")
    return tmp_path / "work"


SPECS = ["--plan", "sonnet/medium", "--code", "opus/high"]
ARGS = ["10", "--brief", BRIEF, *SPECS]
CODE_ONLY = ["10", "--only", "code", "--code", "opus/xhigh"]


def test_one_call_runs_plan_then_code_and_posts_a_record_for_each(
    capsys: pytest.CaptureFixture[str], work: Path
) -> None:
    hub = Hub()
    claude = Claude(hub, inline_added=2)
    assert review.main(ARGS, run=hub, launch=claude) == 0

    assert [call[0] for call in claude.calls] == ["plan", "code"]
    plan_call, code_call = claude.calls
    assert (flag(plan_call[1], "--model"), flag(plan_call[1], "--effort")) == ("sonnet", "medium")
    assert f"Brief: {BRIEF}" in plan_call[2]
    assert (flag(code_call[1], "--model"), flag(code_call[1], "--effort")) == ("opus", "high")
    assert code_call[2] == ""
    # the default limits of each reviewer: minutes, and dollars
    assert (plan_call[4], code_call[4]) == (8 * 60, 20 * 60)
    assert flag(plan_call[1], "--max-budget-usd") == "2.0"
    assert flag(code_call[1], "--max-budget-usd") == "10.0"
    protocol = Path(flag(code_call[1], "--append-subagent-system-prompt-file"))
    assert "{{" not in protocol.read_text("utf-8")
    assert Path(flag(code_call[1], "--add-dir")).is_dir()

    # Each reviewer ran in a clone of its own: of the PR's branch, unable to push, with its
    # environment installed, and with the edit tools denied inside it. The clones are gone again.
    plan_clone = work / "pr-10" / "plan-round-1" / "clone"
    code_clone = work / "pr-10" / "code-round-1" / "clone"
    assert (plan_call[5], code_call[5]) == (plan_clone, code_clone)
    assert hub.push_urls == {str(plan_clone): review.NO_PUSH, str(code_clone): review.NO_PUSH}
    assert hub.synced == [str(plan_clone), str(code_clone)]
    assert f"Edit(/{code_clone}/**)" in values(code_call[1], "--disallowedTools")
    assert not plan_clone.exists()
    assert not code_clone.exists()

    assert review.read_records(hub.posted) == [
        Record("plan", 1, HEAD, "green"),
        Record("code", 1, HEAD, "findings:2"),
    ]
    out = capsys.readouterr().out
    assert "plan-reviewer · round 1 · GREEN" in out
    assert "code-review · round 1 · FINDINGS 2" in out
    assert f"asked opus/high · answered {OPUS} x2 · $0.50 · 30 s" in out
    assert "  inline comments added: 2\n" in out  # as many as findings: nothing more to say
    assert out.count("inline comments added") == 1  # plan-reviewer posts none: no such line
    assert f"record: {PR.url}#issuecomment-2" in out
    assert f"report: {work / 'pr-10' / 'code-round-1' / 'report.md'}" in out
    assert "next: validate each finding" in out
    # resolving is the caller's judgment (decided 2026-10-05): the line asks for it, no tool does it
    assert "push, resolve the threads whose fix you have seen work and leave the others open" in out
    assert not any("resolveReviewThread" in " ".join(call) for call in hub.calls)
    report = (work / "pr-10" / "code-round-1" / "report.md").read_text("utf-8")
    assert report == "1. a\n2. b\nVERDICT: FINDINGS 2\n"


def test_the_next_call_runs_only_the_reviewer_that_is_not_green(
    capsys: pytest.CaptureFixture[str],
) -> None:
    earlier = [
        review.marker(Record("plan", 1, "b" * 40, "green")) + "\nreport",
        review.marker(Record("code", 1, "b" * 40, "findings:2")) + "\nreport",
    ]
    hub = Hub(comments=earlier)
    claude = Claude(hub, code=[turn(OPUS, sub=True), result("VERDICT: GREEN")])
    assert review.main(ARGS, run=hub, launch=claude) == 0
    assert [call[0] for call in claude.calls] == ["code"]
    assert review.read_records(hub.posted) == [Record("code", 2, HEAD, "green")]
    out = capsys.readouterr().out
    assert "plan-reviewer: green in round 1 at bbbbbbb, not run again; the head has moved" in out
    # the facts for the judgment (decided 2026-10-06): what changed since that green
    assert "  since bbbbbbb, 3 files changed: docs/x.md, src/a.py, tests/t.py" in out
    assert "code-review · round 2 · GREEN" in out
    assert "next: every reviewer is green" in out


def test_an_expired_green_is_run_again_and_the_files_line_names_many_briefly(
    capsys: pytest.CaptureFixture[str],
) -> None:
    earlier = [
        review.marker(Record("plan", 1, "b" * 40, "green")) + "\nreport",
        review.marker(Record("code", 1, "b" * 40, "green")) + "\nreport",
    ]
    hub = Hub(comments=earlier, changed_files=[f"f{n}.py" for n in range(12)])
    claude = Claude(hub, code=[turn(OPUS, sub=True), result("VERDICT: GREEN")])
    assert review.main([*ARGS, "--expire", "code"], run=hub, launch=claude) == 0
    assert [call[0] for call in claude.calls] == ["code"]
    assert review.read_records(hub.posted) == [Record("code", 2, HEAD, "green")]
    out = capsys.readouterr().out
    assert "plan-reviewer: green in round 1 at bbbbbbb, not run again; the head has moved" in out
    eight = "f0.py, f1.py, f2.py, f3.py, f4.py, f5.py, f6.py, f7.py"
    assert f"  since bbbbbbb, 12 files changed: {eight} and 4 more" in out
    assert "code-review: green" not in out


def test_with_everything_green_nothing_is_launched(capsys: pytest.CaptureFixture[str]) -> None:
    earlier = [
        review.marker(Record("plan", 1, HEAD, "green")),
        review.marker(Record("code", 2, HEAD, "green")),
    ]
    hub = Hub(comments=earlier)
    claude = Claude(hub)
    assert review.main(ARGS, run=hub, launch=claude) == 0
    assert claude.calls == []
    assert hub.posted == []
    # the loop's last act is a comment on the PR, the one the maintainer reads at the end
    assert (
        "next: every reviewer is green: close out with the closing comment on the PR "
        "(SKILL.md, step 5)."
    ) in capsys.readouterr().out


def test_out_of_rounds_says_stop_and_launches_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    earlier = [
        review.marker(Record("plan", 1, HEAD, "green")),
        review.marker(Record("code", 3, HEAD, "findings:1")),
    ]
    hub = Hub(comments=earlier)
    claude = Claude(hub)
    assert review.main(ARGS, run=hub, launch=claude) == 0
    assert claude.calls == []
    out = capsys.readouterr().out
    assert "code-review: 3 of 3 rounds used and not green: stop and report to the maintainer" in out
    assert (
        "next: stop. Resolve the threads whose fix you have seen work, leave the others open, "
        "then post the closing comment on the PR and report to the maintainer (SKILL.md, step 5)."
    ) in out
    assert "next: every reviewer is green" not in out


def test_a_call_that_names_more_rounds_goes_on_and_tells_the_reviewer(work: Path) -> None:
    earlier = [
        review.marker(Record("plan", 1, HEAD, "green")),
        review.marker(Record("code", 3, HEAD, "findings:1")),
    ]
    hub = Hub(comments=earlier)
    claude = Claude(hub)
    assert review.main([*ARGS, "--rounds", "5"], run=hub, launch=claude) == 0
    assert [call[0] for call in claude.calls] == ["code"]
    assert review.read_records(hub.posted) == [Record("code", 4, HEAD, "findings:2")]
    protocol = (work / "pr-10" / "code-round-4" / "protocol.md").read_text("utf-8")
    assert "round 4 of at most 5" in protocol


def test_only_limits_the_call_to_one_reviewer_and_needs_no_brief() -> None:
    hub = Hub()
    claude = Claude(hub, code=[turn(OPUS, sub=True), result("VERDICT: GREEN")])
    assert review.main(CODE_ONLY, run=hub, launch=claude) == 0
    assert [call[0] for call in claude.calls] == ["code"]
    assert claude.calls[0][1][2] == "/code-review xhigh --comment 10"
    assert (flag(claude.calls[0][1], "--model"), flag(claude.calls[0][1], "--effort")) == (
        "opus",
        "xhigh",
    )


def test_with_only_the_close_out_does_not_wait_for_a_reviewer_that_was_left_out(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # PR #11 review, round 2: on a PR without a brief a green code review said "run this command
    # without --only", and that call is refused with "or --only code": the loop never closed.
    hub = Hub()
    claude = Claude(hub, code=[turn(OPUS, sub=True), result("VERDICT: GREEN")])
    assert review.main(CODE_ONLY, run=hub, launch=claude) == 0
    out = capsys.readouterr().out
    assert (
        "next: code-review is green; plan-reviewer has no brief to check this PR against and "
        "was not run: close out with the closing comment on the PR (SKILL.md, step 5) and say "
        "so in it."
    ) in out
    assert "without --only" not in out


def test_a_reviewer_that_was_left_out_and_can_run_is_waited_for(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # PR #11 review, round 3: the fix above let go of every reviewer that had never run, so
    # `--only plan` with a green plan-reviewer closed the loop without a code review, and
    # `--only code` on a PR that has a brief closed it without plan-reviewer.
    hub = Hub()
    assert review.main([*ARGS, "--only", "plan"], run=hub, launch=Claude(hub)) == 0
    out = capsys.readouterr().out
    assert "plan-reviewer · round 1 · GREEN" in out
    assert "next: code-review has not run yet: run this command without --only." in out

    hub = Hub()
    green = Claude(hub, code=[turn(OPUS, sub=True), result("VERDICT: GREEN")])
    assert review.main([*ARGS, "--only", "code"], run=hub, launch=green) == 0
    out = capsys.readouterr().out
    assert "code-review · round 1 · GREEN" in out
    assert "next: plan-reviewer has not run yet: run this command without --only." in out


def test_with_only_a_reviewer_that_has_open_findings_is_still_waited_for(
    capsys: pytest.CaptureFixture[str],
) -> None:
    earlier = [review.marker(Record("code", 1, HEAD, "findings:2"))]
    hub = Hub(comments=earlier)
    claude = Claude(hub)
    assert review.main([*ARGS, "--only", "plan"], run=hub, launch=claude) == 0
    out = capsys.readouterr().out
    assert "plan-reviewer · round 1 · GREEN" in out
    assert "next: code-review is not green yet: run this command without --only." in out


def test_the_inline_comments_are_counted_before_anything_is_launched(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # PR #11 review, round 1: the count was taken after plan-reviewer had run, so a failing `gh`
    # ended the call with exit 2, which says that nothing was launched.
    hub = Hub(inline_fails_from=1)
    claude = Claude(hub)
    assert review.main(ARGS, run=hub, launch=claude) == 2
    assert claude.calls == []
    assert hub.posted == []
    assert "HTTP 503" in capsys.readouterr().err


def test_a_count_that_fails_after_the_run_does_not_lose_the_record(
    capsys: pytest.CaptureFixture[str],
) -> None:
    hub = Hub(inline_fails_from=2)
    claude = Claude(hub, inline_added=2)
    assert review.main(ARGS, run=hub, launch=claude) == 0
    assert [call[0] for call in claude.calls] == ["plan", "code"]
    assert review.read_records(hub.posted)[-1] == Record("code", 1, HEAD, "findings:2")
    out = capsys.readouterr().out
    assert "code-review · round 1 · FINDINGS 2" in out
    assert "inline comments added" not in out


def test_a_dry_run_prints_the_commands_and_launches_nothing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    hub = Hub()
    claude = Claude(hub)
    assert review.main([*ARGS, "--dry-run"], run=hub, launch=claude) == 0
    assert claude.calls == []
    assert hub.posted == []
    assert hub.clones == {}
    out = capsys.readouterr().out
    assert "claude -p --agent plan-reviewer --model sonnet --effort medium" in out
    assert "claude -p '/code-review high --comment 10' --model opus --effort high" in out


def test_budget_and_time_can_be_set_for_the_call() -> None:
    hub = Hub()
    claude = Claude(hub)
    args = [*ARGS, "--only", "code", "--budget-usd", "25", "--timeout-min", "40"]
    assert review.main(args, run=hub, launch=claude) == 0
    assert flag(claude.calls[0][1], "--max-budget-usd") == "25.0"
    assert claude.calls[0][4] == 40 * 60


@pytest.mark.parametrize(
    ("hub", "args", "message"),
    [
        (Hub(state="MERGED"), ARGS, "PR 10 is MERGED, not open"),
        (Hub(local_head="c" * 40), ARGS, "push first"),
        (Hub(dirty=" M src/a.py\n"), ARGS, "the working tree is not clean"),
        (Hub(), ["10", *SPECS], "no brief found for branch main-skill-x"),
        (
            Hub(),
            ["10", "--brief", "docs/briefs/missing.md", *SPECS],
            "docs/briefs/missing.md does not exist at the PR's head",
        ),
        (
            Hub(contents_error="gh: Service Unavailable (HTTP 503)"),
            ["10", "--brief", BRIEF, *SPECS],
            f"{BRIEF} could not be read at the PR's head: gh: Service Unavailable (HTTP 503)",
        ),
        (
            Hub(origin="/home/x/a-copy-of-the-checkout"),
            ARGS,
            "this checkout's origin (/home/x/a-copy-of-the-checkout) is not the PR's "
            "repository o/r",
        ),
        (Hub(clone_fails_from=1), ARGS, "Could not read from remote repository"),
        # the second clone: plan-reviewer's is made, and still nothing may have been launched
        (Hub(clone_fails_from=2), ARGS, "Could not read from remote repository"),
        (Hub(base_missing=True), ARGS, "the clone has no origin/main"),
        (Hub(clone_head="d" * 40), ARGS, "the PR's head moved while the clone was made"),
        (Hub(sync_fails=True), ARGS, "the lockfile needs to be updated"),
    ],
)
def test_a_call_that_cannot_be_right_launches_nothing(
    hub: Hub, args: list[str], message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    claude = Claude(hub)
    assert review.main(args, run=hub, launch=claude) == 2
    assert claude.calls == []
    assert hub.posted == []
    assert not any(Path(clone).exists() for clone in hub.clones)
    assert message in capsys.readouterr().err


def test_a_checkout_on_another_branch_does_not_stand_in_the_way(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # 2026-10-05: another session switched this folder to another branch during a review. The
    # reviewers read a clone of what GitHub has, so the state of this checkout is not theirs.
    hub = Hub(branch="main-005-offline-core", local_head="c" * 40, dirty=" M docs/x.md\n")
    claude = Claude(hub, inline_added=2)
    assert review.main(ARGS, run=hub, launch=claude) == 0
    assert [call[0] for call in claude.calls] == ["plan", "code"]
    out = capsys.readouterr().out
    assert (
        "this checkout is on main-005-offline-core, not on main-skill-x: "
        "the reviewers get what GitHub has for the PR (aaaaaaa)"
    ) in out


def test_a_checkout_on_no_branch_is_said_in_words(capsys: pytest.CaptureFixture[str]) -> None:
    hub = Hub(branch="")
    claude = Claude(hub, code=[turn(OPUS, sub=True), result("VERDICT: GREEN")])
    assert review.main(CODE_ONLY, run=hub, launch=claude) == 0
    assert "this checkout is on a detached head, not on main-skill-x:" in capsys.readouterr().out


def test_the_clones_are_removed_also_when_the_call_breaks_off(work: Path) -> None:
    # PR #11 review, round 3: nothing pinned that a clone is removed on every way out.
    hub = Hub()

    def launch(
        argv: list[str], prompt: str, run_dir: Path, cwd: Path, timeout_s: int
    ) -> int | None:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        review.main(ARGS, run=hub, launch=launch)
    assert len(hub.clones) == 2
    assert not any(Path(clone).exists() for clone in hub.clones)
    assert not list(work.rglob(review.LOCK))


def test_a_second_call_for_a_reviewer_that_is_running_is_refused(
    capsys: pytest.CaptureFixture[str], work: Path
) -> None:
    # PR #11 review, round 3: two calls at once shared one folder and one clone path; the second
    # removed the clone under the first reviewer, and both posted a record for the same round.
    hub = Hub()
    claude = Claude(hub, code=[turn(OPUS, sub=True), result("VERDICT: GREEN")])
    inner: list[int] = []

    def launch(
        argv: list[str], prompt: str, run_dir: Path, cwd: Path, timeout_s: int
    ) -> int | None:
        inner.append(review.main(CODE_ONLY, run=hub, launch=claude))
        assert cwd.is_dir(), "the running reviewer's clone is still there"
        return claude(argv, prompt, run_dir, cwd, timeout_s)

    assert review.main(CODE_ONLY, run=hub, launch=launch) == 0
    assert inner == [2]
    assert len(claude.calls) == 1
    assert review.read_records(hub.posted) == [Record("code", 1, HEAD, "green")]
    assert "another call is running code-review for PR 10 (process " in capsys.readouterr().err
    assert not list(work.rglob(review.LOCK))


@pytest.mark.parametrize("left_behind", ["999999999", "not a process number", ""])
def test_a_lock_left_by_a_call_that_died_does_not_stand_in_the_way(
    left_behind: str, work: Path
) -> None:
    folder = work / "pr-10" / "code-round-1"
    folder.mkdir(parents=True)
    (folder / review.LOCK).write_text(left_behind)  # no such process, or no number at all
    hub = Hub()
    claude = Claude(hub, code=[turn(OPUS, sub=True), result("VERDICT: GREEN")])
    assert review.main(CODE_ONLY, run=hub, launch=claude) == 0
    assert len(claude.calls) == 1
    assert not (folder / review.LOCK).exists()


def test_a_lock_held_by_another_living_process_is_respected(
    capsys: pytest.CaptureFixture[str], work: Path
) -> None:
    # The test above this pair uses one process and a double. Here the holder is a second, real
    # process: its lock stands while it lives and is taken over once it is gone.
    folder = work / "pr-10" / "code-round-1"
    folder.mkdir(parents=True)
    holder = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    hub = Hub()
    claude = Claude(hub, code=[turn(OPUS, sub=True), result("VERDICT: GREEN")])
    try:
        (folder / review.LOCK).write_text(str(holder.pid))
        assert review.main(CODE_ONLY, run=hub, launch=claude) == 2
        assert claude.calls == []
        assert hub.clones == {}
        assert (folder / review.LOCK).read_text() == str(holder.pid)  # not touched
        expected = f"another call is running code-review for PR 10 (process {holder.pid})"
        assert expected in capsys.readouterr().err
    finally:
        holder.kill()
        holder.wait()
    assert review.main(CODE_ONLY, run=hub, launch=claude) == 0
    assert len(claude.calls) == 1
    assert not (folder / review.LOCK).exists()


def test_the_checkout_may_change_while_a_review_runs(capsys: pytest.CaptureFixture[str]) -> None:
    hub = Hub()
    claude = Claude(hub, code=[turn(OPUS, sub=True), result("VERDICT: GREEN")])

    def launch(
        argv: list[str], prompt: str, run_dir: Path, cwd: Path, timeout_s: int
    ) -> int | None:
        hub.local_head = "d" * 40  # the implementer commits and edits while the reviewer works
        hub.dirty = " M src/a.py\n"
        return claude(argv, prompt, run_dir, cwd, timeout_s)

    assert review.main(CODE_ONLY, run=hub, launch=launch) == 0
    assert review.read_records(hub.posted) == [Record("code", 1, HEAD, "green")]
    out = capsys.readouterr().out
    assert "warning:" not in out
    assert "problem:" not in out


def test_a_command_that_fails_stops_the_call_with_its_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    def run(args: list[str]) -> CompletedProcess[str]:
        return done(args, code=1, err="gh: not logged in")

    assert review.main(ARGS, run=run, launch=Claude(Hub())) == 2
    assert "gh: not logged in" in capsys.readouterr().err


def test_a_run_past_its_time_is_recorded_as_failed(capsys: pytest.CaptureFixture[str]) -> None:
    hub = Hub()
    claude = Claude(hub, code=[turn(OPUS, sub=True)], exit_code=None)
    assert review.main([*ARGS, "--only", "code"], run=hub, launch=claude) == 1
    assert review.read_records(hub.posted) == [Record("code", 1, HEAD, "failed")]
    out = capsys.readouterr().out
    assert "code-review · round 1 · FAILED" in out
    assert "problem: stopped after 20 minutes (the time limit)" in out
    assert "next: a reviewer run failed" in out


def test_a_run_on_another_model_is_said_in_the_record_and_stands(
    capsys: pytest.CaptureFixture[str],
) -> None:
    hub = Hub()
    claude = Claude(hub, code=[turn(SONNET, sub=True), result("VERDICT: GREEN")])
    assert review.main([*ARGS, "--only", "code"], run=hub, launch=claude) == 0
    assert review.read_records(hub.posted) == [Record("code", 1, HEAD, "green")]
    out = capsys.readouterr().out
    assert f"asked opus/high · answered {SONNET} x1" in out
    assert "problem:" not in out


def test_a_process_that_exits_with_an_error_is_a_failed_run(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # PR #11 review, round 2: nothing pinned this, nor the next five behaviours.
    hub = Hub()
    claude = Claude(hub, code=[turn(OPUS, sub=True), result("VERDICT: GREEN")], exit_code=3)
    assert review.main(CODE_ONLY, run=hub, launch=claude) == 1
    assert review.read_records(hub.posted) == [Record("code", 1, HEAD, "failed")]
    out = capsys.readouterr().out
    assert "problem: claude exited with 3" in out
    assert "inline comments added" not in out  # a failed run's count would mean nothing


def test_a_run_that_failed_twice_over_says_both(capsys: pytest.CaptureFixture[str]) -> None:
    hub = Hub()
    record = [turn(OPUS, sub=True), result("VERDICT: GREEN")]
    claude = Claude(hub, code=record, exit_code=3, moves_head={"code": "c" * 40})
    assert review.main(CODE_ONLY, run=hub, launch=claude) == 1
    assert (
        "problem: claude exited with 3; the reviewer's clone is no longer at the PR's head "
        "(HEAD is ccccccc"
    ) in capsys.readouterr().out


def test_the_first_five_denied_tool_calls_are_shown_with_the_run(
    capsys: pytest.CaptureFixture[str],
) -> None:
    denials = [
        {"tool_name": "Bash", "tool_input": {"command": f"git commit -m {number}"}}
        for number in range(7)
    ]
    record = [turn(OPUS, sub=True), result("VERDICT: GREEN", permission_denials=denials)]
    hub = Hub()
    assert review.main(CODE_ONLY, run=hub, launch=Claude(hub, code=record)) == 0
    out = capsys.readouterr().out
    assert "denied tool calls 7" in out
    assert out.count("  denied: Bash: git commit -m ") == 5


def test_a_clone_that_cannot_be_looked_at_afterwards_is_said_and_the_verdict_stands(
    capsys: pytest.CaptureFixture[str],
) -> None:
    hub = Hub()
    claude = Claude(hub, code=[turn(OPUS, sub=True), result("VERDICT: GREEN")])

    def launch(
        argv: list[str], prompt: str, run_dir: Path, cwd: Path, timeout_s: int
    ) -> int | None:
        code = claude(argv, prompt, run_dir, cwd, timeout_s)
        del hub.clones[str(cwd)]  # the reviewer removed its clone
        return code

    assert review.main(CODE_ONLY, run=hub, launch=launch) == 0
    assert review.read_records(hub.posted) == [Record("code", 1, HEAD, "green")]
    out = capsys.readouterr().out
    assert "warning: the reviewer's clone could not be looked at after the run (" in out
    assert "not a git repository" in out


def test_findings_that_were_not_posted_inline_are_pointed_out(
    capsys: pytest.CaptureFixture[str],
) -> None:
    hub = Hub()
    claude = Claude(hub, inline_added=0)
    assert review.main([*ARGS, "--only", "code"], run=hub, launch=claude) == 0
    out = capsys.readouterr().out
    assert "inline comments added: 0 of 2 findings: answer the others under the record" in out


def test_a_clone_that_left_the_prs_head_fails_that_run_and_not_the_next(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A reviewer that switches or commits in its clone has read something else than the PR's
    # head. Each reviewer has a clone of its own, so the next one is not touched by it.
    hub = Hub()
    claude = Claude(hub, inline_added=2, moves_head={"plan": "c" * 40})
    assert review.main(ARGS, run=hub, launch=claude) == 1
    assert [call[0] for call in claude.calls] == ["plan", "code"]
    assert review.read_records(hub.posted) == [
        Record("plan", 1, HEAD, "failed"),
        Record("code", 1, HEAD, "findings:2"),
    ]
    out = capsys.readouterr().out
    assert "plan-reviewer · round 1 · FAILED" in out
    assert (
        "problem: the reviewer's clone is no longer at the PR's head (HEAD is ccccccc, the PR's "
        "head is aaaaaaa): what the reviewer read is not known"
    ) in out
    assert "code-review · round 1 · FINDINGS 2" in out
    assert "next: a reviewer run failed" in out


def test_changes_a_reviewer_left_in_its_clone_are_pointed_out_and_harm_nothing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    hub = Hub()
    green = [turn(OPUS, sub=True), result("VERDICT: GREEN")]
    claude = Claude(hub, code=green, leaves={"code": " M src/a.py\n?? x.txt\n"})
    assert review.main(CODE_ONLY, run=hub, launch=claude) == 0
    assert review.read_records(hub.posted) == [Record("code", 1, HEAD, "green")]
    out = capsys.readouterr().out
    assert "code-review · round 1 · GREEN" in out
    warning = (
        "the reviewer left 2 changed paths in its clone, which is thrown away; "
        "it was asked to stay read-only"
    )
    assert f"  warning: {warning}\n" in out
    # PR #11 review, round 2: the record on the PR read like that of a clean run
    assert f"Warning: {warning}\n" in hub.posted[0]


def test_one_changed_path_is_one_path(capsys: pytest.CaptureFixture[str]) -> None:
    hub = Hub()
    green = [turn(OPUS, sub=True), result("VERDICT: GREEN")]
    claude = Claude(hub, code=green, leaves={"code": "?? x.txt\n"})
    assert review.main(CODE_ONLY, run=hub, launch=claude) == 0
    assert "the reviewer left 1 changed path in its clone" in capsys.readouterr().out


def test_a_clone_left_as_it_was_draws_no_remark(capsys: pytest.CaptureFixture[str]) -> None:
    hub = Hub()
    claude = Claude(hub, code=[turn(OPUS, sub=True), result("VERDICT: GREEN")])
    assert review.main(CODE_ONLY, run=hub, launch=claude) == 0
    out = capsys.readouterr().out
    assert "warning:" not in out
    assert "problem:" not in out


def test_a_record_that_cannot_be_posted_fails_the_call(capsys: pytest.CaptureFixture[str]) -> None:
    hub = Hub(post_fails=True)
    claude = Claude(hub)
    assert review.main([*ARGS, "--only", "code"], run=hub, launch=claude) == 1
    out = capsys.readouterr().out
    assert "record: NOT POSTED (HTTP 502)" in out
    assert "the round will not be counted" in out
