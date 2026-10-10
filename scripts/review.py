"""Run the PR reviewers as headless Claude Code processes, each on a named model and effort.

    uv run python scripts/review.py <pr> --plan sonnet/medium --code opus/xhigh
    uv run python scripts/review.py <pr> --only code --code opus/xhigh
    uv run python scripts/review.py <pr> --plan sonnet/medium --code opus/xhigh --expire code
    uv run python scripts/review.py <pr> --plan sonnet/medium --code opus/xhigh --rounds 5

The first runs every reviewer that is not green yet; the model and effort of a reviewer that runs
must be named, there is no default. `--expire` says that a reviewer's green no longer counts:
whether the commits since it changed what that reviewer reviewed is the caller's judgment.

Why a process of its own: inside a session `/code-review` runs as a subagent whose model falls
through to `CLAUDE_CODE_SUBAGENT_MODEL` (pinned to Sonnet in `.claude/settings.json`), and the Skill
tool takes no model. `claude -p` takes `--model` and `--effort`, and `--settings` overrides the pin
for that one process (docs/kit/research/2026-10-05-review-model-and-effort.md).

One call reads the PR's record comments, then runs each reviewer that is not green and has rounds
left: plan-reviewer first, then `/code-review <effort> --comment <pr>`. For each run it reads off
the run's record which model answered, posts one record comment on the PR, and prints the verdict
and what to do next. The record comments are the memory between rounds: nothing is kept locally.

Each reviewer works in a clone of its own: of the PR's branch as GitHub has it, at the PR's head,
with its own environment, made for the call and removed after it. So a review does not depend on
what any session does to this checkout meanwhile (on 2026-10-05 another session switched its branch
37 s into a review), what a reviewer writes, commits or switches in its working tree stays in the
clone, and the caller may go on working while a review runs.

A reviewer process has no advisor and no MCP servers, and is stopped at a spending cap and a time
limit. The rest are nets, not walls, because the process runs as the user, with the user's
credentials. The edit tools are denied inside the clone, and the plain spelling of each command in
`DENIED` is refused; another spelling (`git -C . commit`) gets through (the round 1 review of PR
#11), which in a clone harms nothing. The clone's `origin` has no push address and a pre-push hook
refuses every push; a push with the address typed out and `--no-verify` gets out (round 3). `gh`
and a `claude` process started another way are not held by the clone at all; the Bash guard, which
runs in the clone too, keeps labels and the base branches out of reach.

Exit codes: 0 the reviewers ran, or nothing was left to run; 1 a run failed or its record could not
be posted; 2 the call could not be right (PR not open; on the PR's branch with a head that is not
pushed or a tree that is not clean; no brief; a clone that could not be made) and nothing was
launched.
"""

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from subprocess import CompletedProcess
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
# What the code reviewer is told on top of the bundled skill's own instructions.
PROTOCOL = ROOT / ".claude" / "skills" / "reviewer" / "references" / "correctness.md"
# All the tools the conformance reviewer starts with: it reads files, and reads git and the PR
# through Bash. Edit and Write are not among them; Bash is, and a shell can write: that the
# reviewer only reads is asked of it, and its clone keeps a write away from everyone else
# (docs/kit/research/2026-10-10-the-conformance-reviewer-without-an-agent-file.md).
PLAN_TOOLS = "Read,Grep,Glob,Bash"
PLACEHOLDERS = ("PR", "REPO", "OWNER", "NAME", "HEAD", "BASE", "ROUND", "ROUNDS", "PROBES")
WORK = Path(tempfile.gettempdir()) / "kitpkg-review"  # knob: package
BRANCH_PREFIX = "main"  # knob: prefix — unit branches are `<prefix>-NNN-slug`
RECORD = "record.jsonl"
STDERR = "stderr.txt"

REVIEWERS = ("plan", "code")
NAMES = {"plan": "plan-reviewer", "code": "code-review"}
EFFORTS = ("low", "medium", "high", "xhigh", "max")
DEFAULT_ROUNDS = 3  # per reviewer, when the call names no number (--rounds)
# One call is at most 28 minutes, inside the Bash tool's default background limit of 30.
TIMEOUT_MIN = {"plan": 8, "code": 20}
BUDGET_USD = {"plan": 2.0, "code": 10.0}
REPORT_LIMIT = 60000  # a GitHub comment holds 65,536 characters
CUT = "[…] (cut: the whole report is in the run's folder)"
# The push address of a reviewer's clone: a scheme git has no transport for, so a push to
# `origin` fails. The hook refuses a push to any other address.
NO_PUSH = "no-push://a-reviewers-clone-does-not-push"
PRE_PUSH = '#!/bin/sh\necho "a reviewer\'s clone does not push" >&2\nexit 1\n'
LOCK = "running.pid"  # in a run's folder while a call is running that reviewer for that round
COMMAND_TIMEOUT_S = 300  # for one git, gh or uv command; a clone and its sync take seconds

# Commands a reviewer has no business running: they move its clone off the PR's head, change the
# PR or the lockfile, or start a Claude process whose cost the spending cap does not count. Each
# becomes a prefix deny rule, which stops the plain spelling and nothing else. It catches a
# reviewer that means no harm; it is not a wall, and is not to be patched spelling by spelling.
# What keeps a reviewer's writes and commits away from everyone else is its clone.
DENIED = (
    *("git add", "git commit", "git switch", "git checkout", "git push", "git pull", "git merge"),
    *("git rebase", "git reset", "git restore", "git stash", "git clean", "git tag"),
    *("gh pr checkout", "gh pr create", "gh pr ready", "gh pr merge", "gh pr edit", "gh pr close"),
    *("uv add", "uv remove", "uv lock", "uv sync"),
    *("make fmt", "make install", "make mutate", "make eval"),
    "claude",
)

MARKER = re.compile(
    r"<!-- review-loop reviewer=(plan|code) round=(\d+) head=([0-9a-f]{7,40}) "
    r"verdict=([a-z]+(?::\d+)?) -->"
)
VERDICT = re.compile(r"^[ \t]*VERDICT: (GREEN|FINDINGS ([1-9]\d*))[ \t]*$", re.MULTILINE)
LABELS = {"green": "GREEN", "unknown": "NO VERDICT (read the report)", "failed": "FAILED"}

Runner = Callable[[list[str]], CompletedProcess[str]]
# (command, prompt on stdin, the run's folder, the clone to work in, seconds allowed)
# -> exit code, or None when stopped
Launcher = Callable[[list[str], str, Path, Path, int], int | None]


class Refused(Exception):
    """The call cannot be right; nothing is launched."""


@dataclass(frozen=True)
class Spec:
    model: str
    effort: str


@dataclass(frozen=True)
class PullRequest:
    number: int
    repo: str  # owner/name
    head: str
    base: str
    branch: str
    url: str


@dataclass(frozen=True)
class Record:
    """One run of one reviewer, as its record comment on the PR states it."""

    reviewer: str
    round: int
    head: str
    verdict: str  # green | findings:<n> | unknown | failed


@dataclass(frozen=True)
class Outcome:
    answered: dict[str, int]  # model -> turns by the reviewer
    cost_usd: float | None
    duration_s: float | None
    advisor_calls: int
    denied: list[str]
    report: str
    verdict: str
    problem: str | None


@dataclass(frozen=True)
class Call:
    pr: int
    only: str | None
    expired: list[str]  # reviewers whose green no longer counts: the caller's judgment
    rounds: int
    specs: dict[str, Spec | None]  # no default: a reviewer that runs must have been given one
    brief: Path | None
    budget_usd: float | None
    timeout_min: int | None
    dry_run: bool


def parse_spec(text: str) -> Spec:
    model, slash, effort = text.partition("/")
    if not model or not slash or effort not in EFFORTS:
        raise ValueError(f"expected MODEL/EFFORT, effort one of {', '.join(EFFORTS)}; got {text!r}")
    return Spec(model, effort)


def find_brief(branch: str, names: Iterable[str]) -> Path | None:
    """`<prefix>-006-slug` -> `docs/briefs/006-*.md`, when exactly one of `names` has that number.

    `names` are the files of `docs/briefs` at the PR's head.
    """
    number = re.match(rf"{re.escape(BRANCH_PREFIX)}-(\d{{3}})-", branch)
    if number is None:
        return None
    found = [name for name in names if name.startswith(f"{number[1]}-") and name.endswith(".md")]
    return Path("docs/briefs") / found[0] if len(found) == 1 else None


def marker(record: Record) -> str:
    return (
        f"<!-- review-loop reviewer={record.reviewer} round={record.round} "
        f"head={record.head} verdict={record.verdict} -->"
    )


def read_records(bodies: Iterable[str]) -> list[Record]:
    """The record comments among a PR's top-level comments: those that start with a marker."""
    found = (MARKER.match(body) for body in bodies)
    return [Record(m[1], int(m[2]), m[3], m[4]) for m in found if m is not None]


def latest(records: Iterable[Record], reviewer: str) -> Record | None:
    """A reviewer's record with the highest round; of two for one round, the later comment."""
    last: Record | None = None
    for record in records:
        if record.reviewer == reviewer and (last is None or record.round >= last.round):
            last = record
    return last


def latest_verdict(records: Iterable[Record], reviewer: str) -> str | None:
    last = latest(records, reviewer)
    return last.verdict if last is not None else None


def select(
    records: Sequence[Record],
    wanted: Sequence[str],
    *,
    expired: Sequence[str],
    rounds: int,
    head: str,
) -> tuple[list[tuple[str, int]], list[str]]:
    """Which reviewers run now, each with its round number, and why the others do not.

    A reviewer stops when it is green or has used `rounds` rounds. A green stands when commits
    land after it, and the note then says that the head has moved: whether those commits changed
    what the reviewer reviewed is the caller's judgment (decided 2026-10-06), and `expired` names
    the reviewers for which it decided so. The round limit stands either way.
    """
    to_run: list[tuple[str, int]] = []
    notes: list[str] = []
    for reviewer in wanted:
        last = latest(records, reviewer)
        used = last.round if last is not None else 0
        green = last is not None and last.verdict == "green"
        if green and reviewer not in expired:
            note = f"{NAMES[reviewer]}: green in round {used}, not run again"
            if last is not None and not head.startswith(last.head):  # a marker may be short
                note = (
                    f"{NAMES[reviewer]}: green in round {used} at {last.head[:7]}, not run "
                    "again; the head has moved since: decide whether that changed what it "
                    f"reviewed, and if so pass --expire {reviewer}"
                )
            notes.append(note)
            continue
        if used >= rounds and green:
            notes.append(
                f"{NAMES[reviewer]}: green in round {used}, expired, and {used} of {rounds} "
                "rounds used: --rounds N allows more"
            )
            continue
        if used >= rounds:
            notes.append(
                f"{NAMES[reviewer]}: {used} of {rounds} rounds used and not green: "
                "stop and report to the maintainer"
            )
            continue
        to_run.append((reviewer, used + 1))
    return to_run, notes


def parse_verdict(report: str) -> str:
    """The last `VERDICT:` line of a report, as `green`, `findings:<n>` or `unknown`."""
    found = VERDICT.findall(report)
    if not found:
        return "unknown"
    word, count = cast("tuple[str, str]", found[-1])
    return "green" if word == "GREEN" else f"findings:{count}"


def label(verdict: str) -> str:
    return LABELS.get(verdict) or f"FINDINGS {verdict.partition(':')[2]}"


def _obj(value: object) -> dict[str, object]:
    return cast("dict[str, object]", value) if isinstance(value, dict) else {}


def _list(value: object) -> list[object]:
    return cast("list[object]", value) if isinstance(value, list) else []


def _events(lines: Iterable[str]) -> Iterable[dict[str, object]]:
    for line in lines:
        try:
            event = json.loads(line)
        except ValueError:  # an empty line, or the last line of a process that was stopped
            continue
        if isinstance(event, dict):
            yield _obj(cast("object", event))


def _denied(result: Mapping[str, object]) -> list[str]:
    denied: list[str] = []
    for item in _list(result.get("permission_denials")):
        tool_input = _obj(_obj(item).get("tool_input"))
        detail = tool_input.get("command") or tool_input.get("file_path") or ""
        denied.append(f"{_obj(item).get('tool_name')}: {str(detail)[:120]}")
    return denied


def read_outcome(lines: Iterable[str], reviewer: str) -> Outcome:
    """What a run's record (`--output-format stream-json`) says happened.

    The plan reviewer is the session itself, so its turns are the main ones; the code review runs
    as the bundled skill's subagent, so its turns are the ones with a parent. The models that
    answered are counted and reported, and judged by nobody: the caller named the model when it
    started the reviewer, and that is the requirement (decided 2026-10-06).
    """
    answered: Counter[str] = Counter()
    advisor_calls = 0
    result: dict[str, object] | None = None
    for event in _events(lines):
        if event.get("type") == "result":
            result = event
        if event.get("type") != "assistant":
            continue
        message = _obj(event.get("message"))
        advisor_calls += sum(
            _obj(block).get("name") == "advisor" for block in _list(message.get("content"))
        )
        by_subagent = event.get("parent_tool_use_id") is not None
        name = message.get("model")
        if by_subagent == (reviewer == "code") and isinstance(name, str) and name != "<synthetic>":
            answered[name] += 1

    result = result or {}
    report = result.get("result")
    report = report if isinstance(report, str) else ""
    cost = result.get("total_cost_usd")
    duration = result.get("duration_ms")
    problem: str | None = None
    if not result:
        problem = "the record has no result line: the process ended early"
    elif result.get("is_error"):
        problem = f"the run ended with an error ({result.get('subtype')})"
    elif not answered:
        problem = "the record holds no turn by the reviewer"
    return Outcome(
        answered=dict(answered),
        cost_usd=float(cost) if isinstance(cost, int | float) else None,
        duration_s=duration / 1000 if isinstance(duration, int | float) else None,
        advisor_calls=advisor_calls,
        denied=_denied(result),
        report=report,
        verdict="failed" if problem else parse_verdict(report),
        problem=problem,
    )


def claude_argv(
    reviewer: str,
    spec: Spec,
    pr: PullRequest,
    round_: int,
    *,
    budget: float,
    root: Path,
    protocol: Path | None = None,
    probes: Path | None = None,
) -> list[str]:
    """The command line of one reviewer process. Model and effort are always named."""
    if reviewer == "plan":
        # No agent file says who runs: the tools are named here (PLAN_TOOLS). What the process
        # does is the reviewer skill, which its prompt starts.
        start = ["claude", "-p", "--tools", PLAN_TOOLS]
        extra: list[str] = []
    else:
        start = ["claude", "-p", f"/code-review {spec.effort} --comment {pr.number}"]
        extra = [
            *("--append-subagent-system-prompt-file", str(protocol)),
            *("--add-dir", str(probes)),
            *("--allowedTools", "Bash(gh api:*)", f"Write(/{probes}/**)"),
        ]
    # The project pins subagents to Sonnet; --settings ranks above the project file, a shell
    # variable does not. The advisor is switched off for this process only.
    env = {"CLAUDE_CODE_SUBAGENT_MODEL": spec.model, "CLAUDE_CODE_DISABLE_ADVISOR_TOOL": "1"}
    return [
        *start,
        *("--model", spec.model, "--effort", spec.effort),
        *("-n", f"review-loop: {NAMES[reviewer]}, PR {pr.number}, round {round_}"),
        *("--settings", json.dumps({"env": env})),
        *("--permission-mode", "auto", "--permission-prompts", "none"),
        "--strict-mcp-config",
        *("--max-budget-usd", str(budget)),
        *("--output-format", "stream-json", "--verbose"),
        *extra,
        "--disallowedTools",
        *(f"Bash({command}:*)" for command in DENIED),
        f"Edit(/{root}/**)",
    ]


def plan_prompt(pr: PullRequest, brief: Path, round_: int, rounds: int) -> str:
    # The base as the clone has it: there is no local branch of that name to be missing or stale.
    parts = [
        "/reviewer conformance",
        f"Brief: {brief}",
        f"PR: {pr.number} (head {pr.head}, base origin/{pr.base})",
    ]
    if round_ > 1:
        parts.append(
            f"Round {round_} of at most {rounds}. Your reports from the rounds before are "
            "top-level comments on the PR that begin `**[plan-reviewer · round`, and the author's "
            f"answers follow them: read them first (`gh pr view {pr.number} --comments`). Do not "
            "report again what the author fixed or answered with evidence, unless the diff still "
            "shows the gap; then say what is still missing."
        )
    parts.append(
        "After your normal output, end with exactly one line: `VERDICT: GREEN` if there are no "
        "gaps, otherwise `VERDICT: FINDINGS <number of findings>`."
    )
    return "\n\n".join(parts) + "\n"


def render_protocol(template: str, pr: PullRequest, round_: int, rounds: int, probes: Path) -> str:
    owner, _, name = pr.repo.partition("/")
    numbers = (str(round_), str(rounds))
    values = (str(pr.number), pr.repo, owner, name, pr.head, pr.base, *numbers, str(probes))
    for placeholder, value in zip(PLACEHOLDERS, values, strict=True):
        template = template.replace("{{" + placeholder + "}}", value)
    return template


def stats(spec: Spec, outcome: Outcome) -> str:
    answered = ", ".join(f"{name} x{count}" for name, count in outcome.answered.items())
    cost = "cost unknown" if outcome.cost_usd is None else f"${outcome.cost_usd:.2f}"
    time = "time unknown" if outcome.duration_s is None else f"{outcome.duration_s:.0f} s"
    return (
        f"asked {spec.model}/{spec.effort} · answered {answered or 'nothing'} · {cost} · {time} · "
        f"advisor calls {outcome.advisor_calls} · denied tool calls {len(outcome.denied)}"
    )


def record_body(record: Record, spec: Spec, outcome: Outcome, warning: str | None = None) -> str:
    """The comment that records a run on the PR: the marker, the figures, the report as it came."""
    title = (
        f"**[{NAMES[record.reviewer]} · round {record.round} · head `{record.head[:7]}`] "
        f"{label(record.verdict)}**"
    )
    head = [marker(record), title, stats(spec, outcome)]
    if outcome.problem:
        head.append(f"Problem: {outcome.problem}")
    if warning:
        head.append(f"Warning: {warning}")
    report = outcome.report.strip() or "(no report)"
    if len(report) > REPORT_LIMIT:
        report = f"{report[:REPORT_LIMIT]}\n\n{CUT}"
    return "\n".join(head) + f"\n\n{report}\n"


def next_step(
    verdicts: Mapping[str, str | None],
    ran: Sequence[str],
    stopped: Sequence[str],
    unable: Sequence[str],
) -> str:
    """One line that says what the caller does now. `verdicts` holds each reviewer's latest.

    A reviewer the call left out (`--only`) is still waited for. The one exception is a reviewer
    that cannot run at all, `unable`: on a PR without a brief plan-reviewer has nothing to check,
    and asking for it would send the caller round in a circle (PR #11 review, rounds 2 and 3).
    """
    if any(verdicts[reviewer] == "failed" for reviewer in ran):
        return (
            "next: a reviewer run failed (its `problem` line above, and stderr.txt in its folder). "
            "If the cause is yours to fix, fix it and run this command once more; if it fails "
            "again, stop and report to the maintainer."
        )
    if any(verdicts[reviewer] != "green" for reviewer in ran):
        return (
            "next: validate each finding by reproducing it, fix what is true with a failing test "
            "first, answer every finding on the PR, push, resolve the threads whose fix you have "
            "seen work and leave the others open for the maintainer, then run this same "
            "command again (SKILL.md, steps 2 to 4)."
        )
    if stopped:
        return (
            "next: stop. Resolve the threads whose fix you have seen work, leave the others open, "
            "then post the closing comment on the PR and report to the maintainer "
            "(SKILL.md, step 5)."
        )
    waiting = [r for r in REVIEWERS if verdicts[r] != "green" and r not in unable]
    not_green = " and ".join(NAMES[r] for r in waiting if verdicts[r] is not None)
    if not_green:
        return f"next: {not_green} is not green yet: run this command without --only."
    if waiting:
        never_ran = " and ".join(NAMES[r] for r in waiting)
        return f"next: {never_ran} has not run yet: run this command without --only."
    if unable:
        green = " and ".join(NAMES[r] for r in REVIEWERS if r not in unable)
        without = " and ".join(NAMES[r] for r in unable)
        return (
            f"next: {green} is green; {without} has no brief to check this PR against and was "
            "not run: close out with the closing comment on the PR (SKILL.md, step 5) and say "
            "so in it."
        )
    return (
        "next: every reviewer is green: close out with the closing comment on the PR "
        "(SKILL.md, step 5)."
    )


def run_in_root(args: list[str]) -> CompletedProcess[str]:
    """Run git, gh or uv from the launcher's checkout; a command that does not answer is stopped."""
    try:
        return subprocess.run(
            args, cwd=ROOT, capture_output=True, text=True, check=False, timeout=COMMAND_TIMEOUT_S
        )
    except subprocess.TimeoutExpired:
        return CompletedProcess(
            args, 124, stdout="", stderr=f"no answer after {COMMAND_TIMEOUT_S} s"
        )


# The Stop hook (scripts/stop_gate.py) reads this: a reviewer changes nothing, so the branch's own
# red — a renamed test awaiting the label — must not keep it from stopping (PR 1 of the kit).
REVIEWER_CLONE_VARIABLE = "KIT_REVIEWER_CLONE"


def reviewer_env(environ: Mapping[str, str], root: Path) -> dict[str, str]:
    """The environment of a reviewer process: the launcher's, without its virtual environment,
    plus the marker the Stop hook reads.

    The launcher runs under `uv run`, which names the launcher's own `.venv` and puts it first on
    the PATH. A reviewer works in a clone with an environment of its own; with the launcher's on
    its PATH, a bare `python` there would import the launcher's checkout.
    """
    venv = root / ".venv"
    env = {name: value for name, value in environ.items() if name != "VIRTUAL_ENV"}
    env[REVIEWER_CLONE_VARIABLE] = "1"
    if "PATH" in env:
        entries = env["PATH"].split(os.pathsep)
        kept = [
            entry for entry in entries if venv != Path(entry) and venv not in Path(entry).parents
        ]
        env["PATH"] = os.pathsep.join(kept)
    return env


def launch_claude(
    argv: list[str], prompt: str, run_dir: Path, cwd: Path, timeout_s: int
) -> int | None:
    """Run one reviewer process in `cwd` to its end, or stop it at the time limit (then: None)."""
    with (run_dir / RECORD).open("w") as record, (run_dir / STDERR).open("w") as errors:
        try:
            done = subprocess.run(
                argv,
                cwd=cwd,
                env=reviewer_env(os.environ, ROOT),
                input=prompt,
                stdout=record,
                stderr=errors,
                text=True,
                timeout=timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return None
    return done.returncode


def _call(run: Runner, args: list[str]) -> str:
    done = run(args)
    if done.returncode != 0:
        reason = (done.stderr or done.stdout).strip()
        raise Refused(f"`{shlex.join(args[:4])}` failed: {reason}")
    return done.stdout


def read_pr(run: Runner, number: int) -> PullRequest:
    fields = "number,state,headRefOid,headRefName,baseRefName,url"
    data = _obj(json.loads(_call(run, ["gh", "pr", "view", str(number), "--json", fields])))
    if data.get("state") != "OPEN":
        raise Refused(f"PR {number} is {data.get('state')}, not open")
    url = str(data.get("url"))
    repo = re.search(r"github\.com/([^/]+/[^/]+)/pull/", url)
    if repo is None:
        raise Refused(f"cannot read the repository from the PR's address {url!r}")
    return PullRequest(
        number=number,
        repo=repo[1],
        head=str(data.get("headRefOid")),
        base=str(data.get("baseRefName")),
        branch=str(data.get("headRefName")),
        url=url,
    )


def check_checkout(run: Runner, pr: PullRequest) -> str | None:
    """Refuse when this checkout holds work on the PR's branch that the review would not see.

    The reviewers read clones of what GitHub has, so only that matters: on the PR's branch, a
    commit that is not pushed or a change that is not committed. On any other branch the state of
    this checkout is nobody's business here, and a note says what is reviewed.
    """
    branch = _call(run, ["git", "branch", "--show-current"]).strip()
    if branch != pr.branch:
        return (
            f"this checkout is on {branch or 'a detached head'}, not on {pr.branch}: "
            f"the reviewers get what GitHub has for the PR ({pr.head[:7]})"
        )
    local = _call(run, ["git", "rev-parse", "HEAD"]).strip()
    if local != pr.head:
        raise Refused(f"local HEAD {local[:7]} is not the PR's head {pr.head[:7]}: push first")
    if _call(run, ["git", "status", "--porcelain"]).strip():
        raise Refused(
            "the working tree is not clean: commit and push what is there, or the review "
            "will not see it"
        )
    return None


def make_clone(run: Runner, origin: str, pr: PullRequest, clone: Path) -> None:
    """A clone of the PR's branch for one reviewer: at the PR's head, with the base to diff
    against, and with nothing an ordinary push could use.

    What the reviewer writes, commits or switches stays in the clone, which is thrown away: that
    much is a fact about where it runs. For pushes the clone is two nets, not a wall: `origin` has
    no push address, and a pre-push hook refuses every push, also one to an address typed out.
    The reviewer process has the user's credentials all the same, so a push with the address
    typed out and `--no-verify` still gets out (pinned by a test, so that no text says otherwise).
    """
    shutil.rmtree(clone, ignore_errors=True)  # left by a run that was stopped
    _call(run, ["git", "clone", "--quiet", "--branch", pr.branch, origin, str(clone)])
    head = _call(run, ["git", "-C", str(clone), "rev-parse", "HEAD"]).strip()
    if head != pr.head:
        raise Refused(
            f"the PR's head moved while the clone was made (it is {head[:7]}, and this call "
            f"began at {pr.head[:7]}): run the command again"
        )
    base = f"origin/{pr.base}"
    if run(["git", "-C", str(clone), "rev-parse", "--verify", "--quiet", base]).returncode != 0:
        raise Refused(f"the clone has no {base}: {origin} does not hold the PR's base branch")
    _call(run, ["git", "-C", str(clone), "remote", "set-url", "--push", "origin", NO_PUSH])
    hook = clone / ".git" / "hooks" / "pre-push"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text(PRE_PUSH, "utf-8")
    hook.chmod(0o755)


def sync_clone(run: Runner, clone: Path) -> None:
    """The clone's own environment, so that hooks and probes there do not build it mid-review."""
    _call(run, ["uv", "sync", "--locked", "--all-groups", "--quiet", "--project", str(clone)])


def clone_after(run: Runner, pr: PullRequest, clone: Path) -> tuple[str | None, str | None]:
    """What a reviewer did to its clone, as (a problem, a warning).

    Off the PR's head: it switched or committed, and what it then read is not known, so the run
    fails. Changed paths harm nothing, the clone is thrown away, but the reviewer was asked to
    stay read-only and the caller should know.
    """
    try:
        head = _call(run, ["git", "-C", str(clone), "rev-parse", "HEAD"]).strip()
        changed = _call(run, ["git", "-C", str(clone), "status", "--porcelain"]).splitlines()
    except Refused as refusal:
        return None, f"the reviewer's clone could not be looked at after the run ({refusal})"
    problem = warning = None
    if head != pr.head:
        problem = (
            f"the reviewer's clone is no longer at the PR's head (HEAD is {head[:7]}, the PR's "
            f"head is {pr.head[:7]}): what the reviewer read is not known"
        )
    if changed:
        paths = "1 changed path" if len(changed) == 1 else f"{len(changed)} changed paths"
        warning = (
            f"the reviewer left {paths} in its clone, which is thrown away; "
            "it was asked to stay read-only"
        )
    return problem, warning


def read_bodies(run: Runner, pr: PullRequest) -> list[str]:
    endpoint = f"repos/{pr.repo}/issues/{pr.number}/comments"
    out = _call(run, ["gh", "api", endpoint, "--paginate", "--jq", ".[].body | @json"])
    return [str(json.loads(line)) for line in out.splitlines() if line.strip()]


def count_inline(run: Runner, pr: PullRequest) -> int:
    """The inline comments that open a thread. Replies are left out: the author may answer
    findings while a review runs, and an answer is not a finding the reviewer posted."""
    endpoint = f"repos/{pr.repo}/pulls/{pr.number}/comments"
    top_level = ".[] | select(.in_reply_to_id == null) | .id"
    return len(_call(run, ["gh", "api", endpoint, "--paginate", "--jq", top_level]).split())


def lookup_brief(run: Runner, given: Path | None, pr: PullRequest) -> Path | None:
    """The brief of the PR, as GitHub has it at the PR's head (this checkout may be elsewhere).

    None when the branch has none. A path that was named and is not there, or a GitHub that
    cannot be asked, is refused with the reason, not taken for "no brief".
    """
    contents = f"repos/{pr.repo}/contents"
    if given is not None:
        found = run(["gh", "api", f"{contents}/{given.as_posix()}?ref={pr.head}", "--jq", ".path"])
        reason = (found.stderr or found.stdout).strip()
        if found.returncode != 0 and "404" in reason:
            raise Refused(f"{given} does not exist at the PR's head")
        if found.returncode != 0:
            raise Refused(f"{given} could not be read at the PR's head: {reason}")
        return given
    listing = ["gh", "api", f"{contents}/docs/briefs?ref={pr.head}", "--jq", ".[].name"]
    return find_brief(pr.branch, _call(run, listing).split())


def the_brief(run: Runner, given: Path | None, pr: PullRequest) -> Path:
    brief = lookup_brief(run, given, pr)
    if brief is None:
        raise Refused(
            f"no brief found for branch {pr.branch}: pass --brief docs/briefs/NNN-slug.md, "
            "or --only code to run the code review alone"
        )
    return brief


@dataclass(frozen=True)
class Run:
    """One reviewer run that is about to start: its command, its prompt, where its files go."""

    reviewer: str
    round: int
    spec: Spec
    argv: list[str]
    prompt: str  # on stdin: the plan reviewer's task
    protocol: str  # appended to the code reviewer's instructions
    folder: Path  # the run's record, report and probes
    clone: Path  # where the reviewer works; made for the run, removed after it
    minutes: int


def prepare(reviewer: str, round_: int, call: Call, pr: PullRequest, brief: Path | None) -> Run:
    """Work out a run without changing anything, so that a dry run can show it."""
    spec = call.specs[reviewer]
    if spec is None:  # `review` refuses the call before this; here for the type
        raise Refused(f"--{reviewer} MODEL/EFFORT is needed")
    folder = (WORK / f"pr-{pr.number}" / f"{reviewer}-round-{round_}").resolve()
    prompt = protocol = ""
    if reviewer == "plan" and brief is not None:
        prompt = plan_prompt(pr, brief, round_, call.rounds)
    if reviewer == "code":
        template = PROTOCOL.read_text("utf-8")
        protocol = render_protocol(template, pr, round_, call.rounds, folder / "probes")
    argv = claude_argv(
        reviewer,
        spec,
        pr,
        round_,
        budget=BUDGET_USD[reviewer] if call.budget_usd is None else call.budget_usd,
        root=folder / "clone",
        protocol=folder / "protocol.md",
        probes=folder / "probes",
    )
    minutes = TIMEOUT_MIN[reviewer] if call.timeout_min is None else call.timeout_min
    return Run(reviewer, round_, spec, argv, prompt, protocol, folder, folder / "clone", minutes)


def execute(job: Run, launch: Launcher) -> Outcome:
    """Run one reviewer in its clone to its end and read what its record says."""
    (job.folder / "probes").mkdir(parents=True, exist_ok=True)
    if job.protocol:
        (job.folder / "protocol.md").write_text(job.protocol, "utf-8")
    exit_code = launch(job.argv, job.prompt, job.folder, job.clone, job.minutes * 60)
    record = job.folder / RECORD
    record.touch()  # a launcher that never started the process leaves no file
    with record.open(encoding="utf-8", errors="replace") as lines:  # line by line: it can be large
        outcome = read_outcome(lines, job.reviewer)
    if exit_code is None:
        problem = f"stopped after {job.minutes} minutes (the time limit)"
        outcome = replace(outcome, verdict="failed", problem=problem)
    elif exit_code != 0 and outcome.problem is None:
        outcome = replace(outcome, verdict="failed", problem=f"claude exited with {exit_code}")
    (job.folder / "report.md").write_text(f"{outcome.report}\n" if outcome.report else "", "utf-8")
    return outcome


def inline_added(run: Runner, pr: PullRequest, before: int) -> int | None:
    try:
        return count_inline(run, pr) - before
    except Refused:  # the run itself is done: its record must still be posted
        return None


def report(
    job: Run,
    outcome: Outcome,
    pr: PullRequest,
    added: int | None,
    run: Runner,
    warning: str | None = None,
) -> bool:
    """Post the run's record on the PR and print its block. False when the record was not posted."""
    record = Record(job.reviewer, job.round, pr.head, outcome.verdict)
    body = job.folder / "record-comment.md"
    body.write_text(record_body(record, job.spec, outcome, warning), "utf-8")
    endpoint = f"repos/{pr.repo}/issues/{pr.number}/comments"
    posted = run(["gh", "api", endpoint, "-F", f"body=@{body}", "--jq", ".html_url"])

    print(f"\n{NAMES[job.reviewer]} · round {job.round} · {label(outcome.verdict)}")
    print(f"  {stats(job.spec, outcome)}")
    if outcome.problem:
        print(f"  problem: {outcome.problem}")
    if warning:
        print(f"  warning: {warning}")
    for denied in outcome.denied[:5]:
        print(f"  denied: {denied}")
    if added is not None and outcome.verdict != "failed":
        found = int(outcome.verdict.partition(":")[2] or 0)
        rest = f" of {found} findings: answer the others under the record" if added < found else ""
        print(f"  inline comments added: {added}{rest}")
    if posted.returncode == 0:
        print(f"  record: {posted.stdout.strip()}")
    else:
        reason = (posted.stderr or posted.stdout).strip()
        print(
            f"  record: NOT POSTED ({reason}): the round will not be counted. Post it yourself: "
            f"gh api {endpoint} -F body=@{body}"
        )
    print(f"  report: {job.folder / 'report.md'}")
    return posted.returncode == 0


def make_clones(run: Runner, pr: PullRequest, jobs: Sequence[Run]) -> None:
    """A clone with its environment for every run, all before anything is launched: a failure
    here ends the call with exit 2, and exit 2 has to mean that nothing ran."""
    if not jobs:
        return
    origin = _call(run, ["git", "remote", "get-url", "origin"]).strip()
    if pr.repo.lower() not in origin.lower():  # a copy of a checkout has a folder as its origin
        raise Refused(
            f"this checkout's origin ({origin}) is not the PR's repository {pr.repo}: "
            "run the command from a checkout that was cloned from GitHub"
        )
    try:
        for job in jobs:
            make_clone(run, origin, pr, job.clone)
            sync_clone(run, job.clone)
    except Refused:
        remove_clones(jobs)
        raise


def remove_clones(jobs: Sequence[Run]) -> None:
    for job in jobs:
        shutil.rmtree(job.clone, ignore_errors=True)


def _alive(process: int) -> bool:
    try:
        os.kill(process, 0)
    except ProcessLookupError:
        return False
    except PermissionError:  # it exists and is another user's
        return True
    return True


def take_locks(jobs: Sequence[Run], pr: PullRequest) -> list[Path]:
    """One call at a time per reviewer and round: two would share the run's folder and clone.

    The lock is a file with the holder's process number, created in one step (a file that is
    already there is never overwritten unseen). One whose process is gone, a call that was
    stopped, is taken over.
    """
    held: list[Path] = []
    try:
        for job in jobs:
            job.folder.mkdir(parents=True, exist_ok=True)
            lock = job.folder / LOCK
            holder = _lock_holder(lock)
            if holder is not None:
                raise Refused(
                    f"another call is running {NAMES[job.reviewer]} for PR {pr.number} "
                    f"(process {holder}): wait for it to return"
                )
            held.append(lock)
    except Refused:
        release(held)
        raise
    return held


def _lock_holder(lock: Path) -> int | None:
    """Take the lock for this process (then: None), or name the living process that holds it."""
    for _ in range(2):
        try:
            with lock.open("x", encoding="utf-8") as file:
                file.write(str(os.getpid()))
            return None
        except FileExistsError:
            try:
                holder = int(lock.read_text("utf-8"))
            except (OSError, ValueError):
                holder = None
            if holder is not None and _alive(holder):
                return holder
            lock.unlink(missing_ok=True)  # left by a call that is gone: remove it, try once more
    raise Refused(f"{lock} came back after it was removed: another call is starting; run again")


def release(locks: Sequence[Path]) -> None:
    for lock in locks:
        lock.unlink(missing_ok=True)


def moved_since(run: Runner, pr: PullRequest, records: Sequence[Record], reviewer: str) -> str:
    """The files changed since a reviewer's green: the facts for the caller's judgment.

    Empty when the green is at the PR's head or there is none.
    """
    last = latest(records, reviewer)
    if last is None or last.verdict != "green" or pr.head.startswith(last.head):
        return ""
    endpoint = f"repos/{pr.repo}/compare/{last.head}...{pr.head}"
    files = _call(run, ["gh", "api", endpoint, "--jq", ".files[].filename"]).split()
    shown = ", ".join(files[:8]) + (f" and {len(files) - 8} more" if len(files) > 8 else "")
    plural = "file" if len(files) == 1 else "files"
    return f"  since {last.head[:7]}, {len(files)} {plural} changed: {shown}"


def review(call: Call, run: Runner, launch: Launcher) -> int:
    pr = read_pr(run, call.pr)
    elsewhere = check_checkout(run, pr)
    records = read_records(read_bodies(run, pr))
    wanted = [call.only] if call.only else list(REVIEWERS)
    to_run, notes = select(records, wanted, expired=call.expired, rounds=call.rounds, head=pr.head)
    unnamed = [reviewer for reviewer, _ in to_run if call.specs[reviewer] is None]
    if unnamed:
        options = " and ".join(f"--{reviewer}" for reviewer in unnamed)
        verb = "is" if len(unnamed) == 1 else "are"
        raise Refused(
            f"{options} MODEL/EFFORT {verb} needed: name the model and effort of each reviewer "
            "that runs (the brief's Sessions line has them; there is no default)"
        )
    needs_brief = any(reviewer == "plan" for reviewer, _ in to_run)
    brief = the_brief(run, call.brief, pr) if needs_brief else None
    # plan-reviewer cannot run on a PR that has no brief. Asked here, before anything is launched,
    # so that a GitHub that cannot be asked ends the call while exit 2 is still true.
    unable: list[str] = []
    left_out = "plan" not in wanted and latest(records, "plan") is None
    if left_out and lookup_brief(run, call.brief, pr) is None:
        unable = ["plan"]
    jobs = [prepare(reviewer, round_, call, pr, brief) for reviewer, round_ in to_run]

    print(f"review-loop · PR #{pr.number} · head {pr.head[:7]} · {pr.url}")
    if elsewhere:
        print(elsewhere)
    planned_now = {reviewer for reviewer, _ in to_run}
    for note in notes:
        print(note)
        reviewer = note.split(":")[0]
        for name, short in NAMES.items():
            if short == reviewer and name not in planned_now:
                print(moved_since(run, pr, records, name))
    if call.dry_run:
        for job in jobs:
            print(f"\n{NAMES[job.reviewer]} · round {job.round} · would run:")
            print(f"  {shlex.join(job.argv)}")
        return 0

    verdicts = {reviewer: latest_verdict(records, reviewer) for reviewer in REVIEWERS}
    planned = [job.reviewer for job in jobs]
    stopped = [r for r in wanted if r not in planned and verdicts[r] != "green"]
    # Counted before anything is launched: a `gh` that fails here ends the call with exit 2, and
    # exit 2 has to mean that nothing ran. plan-reviewer posts no inline comments, so the count
    # still holds when the code review starts.
    before = count_inline(run, pr) if "code" in planned else None
    locks = take_locks(jobs, pr)  # before the clones: a refused call must not touch another's
    all_posted = True
    try:
        make_clones(run, pr, jobs)
        for job in jobs:
            outcome = execute(job, launch)
            moved, warning = clone_after(run, pr, job.clone)
            if moved:
                problem = f"{outcome.problem}; {moved}" if outcome.problem else moved
                outcome = replace(outcome, verdict="failed", problem=problem)
            added = None
            if before is not None and job.reviewer == "code":
                added = inline_added(run, pr, before)
            all_posted &= report(job, outcome, pr, added, run, warning)
            verdicts[job.reviewer] = outcome.verdict
    finally:
        remove_clones(jobs)
        release(locks)
    print(f"\n{next_step(verdicts, planned, stopped, unable)}")
    failed = any(verdicts[reviewer] == "failed" for reviewer in planned)
    return 1 if failed or not all_posted else 0


def _spec_argument(text: str) -> Spec:
    try:
        return parse_spec(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def _whole_number_above_zero(text: str) -> int:
    number = int(text)
    if number < 1:
        raise argparse.ArgumentTypeError(f"expected a whole number of at least 1; got {text!r}")
    return number


def _amount_above_zero(text: str) -> float:
    amount = float(text)
    if not 0 < amount < float("inf"):  # also refuses nan; inf would be no cap at all
        raise argparse.ArgumentTypeError(f"expected an amount above 0; got {text!r}")
    return amount


def parse_call(argv: Sequence[str] | None) -> Call:
    parser = argparse.ArgumentParser(
        prog="review.py", description="Run the PR reviewers, each on a named model and effort."
    )
    parser.add_argument("pr", type=int, help="the pull request number")
    for reviewer in REVIEWERS:
        parser.add_argument(
            f"--{reviewer}",
            type=_spec_argument,
            metavar="MODEL/EFFORT",
            help=f"{NAMES[reviewer]}'s model and effort; needed when it runs (no default)",
        )
    parser.add_argument("--only", choices=REVIEWERS, help="run this reviewer only")
    parser.add_argument(
        "--expire",
        action="append",
        choices=REVIEWERS,
        default=[],
        metavar="REVIEWER",
        help="this reviewer's green no longer counts: the commits since changed what it reviewed",
    )
    parser.add_argument(
        "--rounds",
        type=_whole_number_above_zero,
        default=DEFAULT_ROUNDS,
        metavar="N",
        help=f"rounds each reviewer may use before the loop stops (default {DEFAULT_ROUNDS})",
    )
    parser.add_argument("--brief", type=Path, help="default: docs/briefs/NNN-*.md from the branch")
    parser.add_argument(
        "--budget-usd", type=_amount_above_zero, help="spending cap per reviewer run"
    )
    parser.add_argument(
        "--timeout-min",
        type=_whole_number_above_zero,
        help="time limit per reviewer run, in minutes",
    )
    parser.add_argument("--dry-run", action="store_true", help="print the commands; run nothing")
    args = parser.parse_args(argv)
    return Call(
        pr=cast("int", args.pr),
        only=cast("str | None", args.only),
        expired=cast("list[str]", args.expire),
        rounds=cast("int", args.rounds),
        specs={"plan": cast("Spec | None", args.plan), "code": cast("Spec | None", args.code)},
        brief=cast("Path | None", args.brief),
        budget_usd=cast("float | None", args.budget_usd),
        timeout_min=cast("int | None", args.timeout_min),
        dry_run=cast("bool", args.dry_run),
    )


def main(
    argv: Sequence[str] | None = None, run: Runner = run_in_root, launch: Launcher = launch_claude
) -> int:
    call = parse_call(argv)
    try:
        return review(call, run, launch)
    except Refused as refusal:
        print(f"review: {refusal}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
