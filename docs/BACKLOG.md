# Backlog — the kit's own

**Status:** living · kit-only (a project gets an empty one from `docs/templates/BACKLOG.md`).

The parking lot for ideas, wishes and deferred work on the kit. Nothing here is a commitment; an
item moves into `docs/ROADMAP.md` when the friction log shows it twice, or when the maintainer says so.
Rejected items stay listed, struck through, with the reason.

Item states: `idea` · `someday` (agreed, unscheduled) · `waiting on <who/what>` · `→ roadmap` ·
~~rejected — reason~~.

| added | item | notes | state |
|---|---|---|---|
| 2026-10-06 | Library extraction: the gate scripts as an installable package with a `[tool.harness]` configuration, projects call it from their hooks | when a second project needs a fix to travel faster than `kit.py update`, or the knob set grows past a handful (ADR-0001) | someday |
| 2026-10-06 | `/pr-comments <n>` skill: fetch every comment on a PR (inline, top-level, reviews) from anyone, answer what can be answered in the PR, apply agreed fixes, list what needs a conversation | the review loop's `commands.md` has the reads; the loop itself covers the reviewers' comments, not the maintainer's | idea |
| 2026-10-06 | Implementer auto-start: when the maintainer adds `brief-approved`, a hook starts the implementer session on that branch (`claude -p "Execute docs/briefs/NNN…"`) with a cost cap and a time cap | needs a decision on where sessions run (a local watcher vs a CI runner with OAuth) | idea |
| 2026-10-06 | Review auto-start on `ready_for_review`, bounded rounds, then stop | the loop exists (`review-loop`); what is left is the trigger | idea |
| 2026-10-06 | Escalation label `needs-human` + a notification, so "everything before the PR is automated" never means "nobody is watching" | with the two items above | idea |
| 2026-10-06 | The Bash guard on a real parser (`tree-sitter-bash` or `shfmt --to-json`): the hand-written reader held against habit, not against a search; eight review rounds each found a line it read differently from the shell | the source project's backlog has the known gaps as acceptance cases | waiting on friction |
| 2026-10-06 | `scripts/` under the mutation gate: coverage does not measure it and nothing mutates it; a one-off run found real test gaps in the source project | needs a layout mutmut can name (a package), or `also_copy` tricks | someday |
| 2026-10-06 | "Core is pure" as an allowlist (what `core/` may import) instead of a blacklist: `import os` passes today | needs a custom import-linter contract type | idea |
| 2026-10-06 | Non-Python variants: the documents are language-agnostic, the gates are not | when a non-Python project wants the kit | idea |
| 2026-10-06 | Signed launcher markers: a PR comment that starts with the review launcher's marker counts as a record, whoever wrote it | matters once more than one account comments | idea |
| 2026-10-06 | A hook that detects a second Claude Code session in the same checkout (one session per checkout is prose today) | if the incident recurs | idea |
| 2026-10-06 | `checks-weakened-approved` expiring on a push that weakens something new, as `gates-approved` does on gate files | the source project's backlog | idea |
| 2026-10-06 | `plan-reviewer` reports rows added to `docs/BACKLOG.md` and `docs/FRICTION.md` as "out of scope", although the brief template and the PR template require them (an out-of-scope line, a friction line); its instructions should exempt the two living logs from the scope check | PR 1, plan-reviewer round 1: five of its ten findings were of this kind | idea |
| 2026-10-06 | `kit.py init` could commit what it did (today it stages and prints the commit as the maintainer's first step), and `init --labels` could also set the repository's merge options (squash only, delete branch on merge) with `gh repo edit` | from PR 1; small, and the maintainer may want to read the diff first | idea |
| 2026-10-06 | The CI `mutation` job skips when no `core/` module changed, so a PR that only adds tests never runs `make mutate`; PR 1's `make mutate` was red twice for reasons the job would not have caught | run `make mutate` on every PR that touches `tests/`, or on a schedule | idea |
| 2026-10-06 | `stop_gate.py` has no time limit of its own on `make check` or `gh pr view`; a hang ends at the hook's 180 s timeout, and whether a Stop hook that times out blocks is not written in the research notes | look it up, write it down, then give both calls a timeout that exits 2 | idea |
| 2026-10-10 | `scope-approved` is read by the conformance reviewer only: no CI job holds the merge for it, and it stays on the PR whatever is listed after it | enforce when the label has been used more than twice; a workflow that removes it on a push that changes "Where this differs from the brief" is the shape | idea |
| 2026-10-10 | `.claude/skills/implementer/scripts/pr.py` is outside `make types`: basedpyright leaves out every dot-folder, also when named; a test type-checks a copy of the script | a `scripts/` location would put it under the gate, at the price of a skill that is not self-contained | idea |
| 2026-10-10 | The role skills carry no test prompts (`evals/`) in the kit; the source project's are its own | the rehearsal brief runs each skill once on a prompt against the sample package | idea |
| 2026-10-10 | Homogenising with the source project: the kit keeps `KIT_REVIEWER_CLONE` (the Stop hook stands aside in a reviewer's clone) and the source project does not; the skills are the same text in both; `pr.py` differs in three places (GitHub's line ends, an empty list marker counts as nothing written, a dry run's file among the proofs is refused) | when the source project adopts the kit | idea |
| 2026-10-10 | `pr.py` reads a page with a hand-written model of GitHub's Markdown, and two shapes GitHub shows as code are refused as an open fence or an open comment: three backticks indented four spaces after a blank line (an indented code block), and a code span that runs over a line end. Both refusals are false, with a message that is not true | a Markdown parser (markdown-it-py is in the environment through textual) in place of the scan, if a third shape turns up | idea |
| 2026-10-10 | `scripts/review.py` posts a run's record with one call and gives the run up when that call fails on the network, after the review itself ran; one retry of that call would have saved a round | the next record post that fails | idea |
| 2026-10-11 | The shipped documents name a `make prove` target and a CI job `prove` that do not exist yet | brief 007 builds them; until then a project reading `HARNESS.md` looks for a target it does not have | waiting on brief 007 |
| 2026-10-11 | `test_stateless.py` reads record ids, paths and dates, and not a pointer by number (`brief 002`, `PR #5 review, round 8`); brief 005 removed about fifty of those by hand from comments and docstrings, and nothing keeps them out | a fourth scanner over the rendered project for `brief [0-9]{3}` and `PR #?[0-9]+` | idea |
| 2026-10-11 | Shipped files that still tell how the kit came to be, none of it read by a scan: `test_role_skills.py` (`AGENTS_LINES_BEFORE_THE_ROLES` and its dated comment), `kit.py` ("the source project's names" in a manifest comment), the comments in `test_review.py` that narrate a bug ("was taken as", "the fix above") instead of the behaviour they pin, `PHILOSOPHY.md` §3 ("the kit has a backlog item for it") | restate each as the fact; dates are not read under `tests/` | idea |
| 2026-10-11 | Five case names in `tests/harness/fixtures/integrity_cases.toml` end in `(PR #5 review, round N)` | the names are test IDs, so renaming them lists five vanished tests and needs `checks-weakened-approved`; do it in a unit that asks for the label | idea |
