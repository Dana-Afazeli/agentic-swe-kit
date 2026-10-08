# ADR-0008 — The Stop hook keeps `make check`; the vanished-test check is CI's alone

**Status:** accepted 2026-10-08 (adopted from the source project's ADR-0010 of 2026-10-07) ·
**Deciders:** the maintainer · **Supersedes:** ADR-0005 decision 3 (the Stop hook runs the test half
of `scripts/integrity.py`) and the second sentence of decision 4 (the hook reads the label). The rest
of ADR-0005 stands: no edit-time guard on `tests/`, one script, the CI job `integrity`, one label.

## Context
ADR-0005 had the Stop hook run `scripts/integrity.py --tests-only` after `make check` and block while
a test that exists on the base is gone or skipped, until the branch's PR carries
`checks-weakened-approved`. The reason was feedback in the same session, while the agent still has
the context to restore a test it did not mean to remove.

What it did in practice, in the kit's first day and in the source project's PR #10:
- Both reviewers of the kit's PR 1 (a branch with renamed tests awaiting the label) could not end
  their sessions; the plan-reviewer looped to its 8-minute limit and the code reviewer to its
  20-minute limit, reports written and unposted. The launcher's `KIT_REVIEWER_CLONE` marker patched
  that for reviewers only.
- The init commit of a new project removes the kit's own tests and renames the sample's: seventy
  vanished tests against the template commit, so a Claude Code session in a fresh project cannot
  stop until the commit is pushed (SETUP.md §2; the open thread on PR 1).
- In the source project, an implementer whose brief asked for a test's removal was sent back about
  twenty times, each round a 45-second `make check`, able to say only that the label is the
  maintainer's; its reviewers were held the same way.

The block did what it was written to do, and what it was written to do is wrong for a removal that is
right: the session cannot give the answer the hook asks for, because the answer is a label only the
maintainer adds. A hold the held party cannot lift turns an approval step into a stall.

## Decision
1. **The Stop hook runs `make check` and nothing else.** Still exit 2 with the last 40 lines while
   the gate is red, still only when code changed, still no `stop_hook_active` bypass, still standing
   aside in a reviewer's clone (`KIT_REVIEWER_CLONE`: a reviewer changes nothing, and a red gate on
   the PR under review is the author's).
2. **A vanished or skipped test is reported by CI alone.** The job `integrity` runs the whole of
   `scripts/integrity.py` on the PR and stays red until the maintainer adds
   `checks-weakened-approved`; nothing about the job, the script or the label changes. The merge is
   what waits for the maintainer, not the session.
3. **The agent runs `scripts/integrity.py --base origin/<base>` itself before `gh pr ready`**
   (AGENTS.md says so) and lists what it prints under "Checks weakened" in the PR, which the hook's
   feedback used to prompt. `--tests-only` stays in the script as a quicker local run.

Considered and set aside: having the hook recognise the template commit or read a marker for "this
removal is meant" — either is a way for the held party to lift the hold, which is what the label was
there to prevent, and the CI job already is the layer that cannot be routed around.

## Consequences
- A session that removes a test on purpose can stop; so can the reviewers on its branch, and a
  session in a freshly initialised project. The reviewer-clone exemption keeps its other reason.
- The agent hears about a vanished test at its own run of the script or at CI, not at the stop. A
  removal it did not mean is caught by the first of those that runs; CI is red on the PR and says
  what is gone. This is the trade: a slower first warning for a hold that can always be lifted.
- `tests/harness/test_stop_gate.py` asserts that the hook runs nothing but `make check`, and that
  `ci.yml`'s `integrity` job still runs the whole script and wants the label — the check that left
  the hook cannot leave CI without a test going red.
- HARNESS.md's gates table, PHILOSOPHY.md §6, WORKFLOW.md step 4, SETUP.md §2 and §4, AGENTS.md and
  the brief template say what is true now, in the same PR (brief 003).
