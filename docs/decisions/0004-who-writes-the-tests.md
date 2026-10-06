# ADR-0004 — Who writes the tests, and how they are protected from the agent that wrote the code

**Status:** accepted 2026-10-06 (adopted from the source project's ADR-0007 of 2026-09-30, as
amended by its ADR-0008) · **Deciders:** the maintainer (question and concern), the planning session
(evidence)

## Context
If the implementer writes the tests that certify its own code, the tests prove little — and agents
are known to delete a failing test instead of fixing the code. *Commons & Diffs* (ed. 2) names both:
"trusting AI-written tests to certify AI-written code is where teams over-trust" and "agents deleting
failing tests instead of fixing code". Its remedy is layered verification, not a different author:
the brief carries the check that proves it works; the implementer works red then green; a fresh
context sees only the diff and the brief; mutation testing checks that the tests test something;
policy lives in permissions and CI gates, not in a prompt.

Moving test authorship to a separate agent by default would cost what TDD is for — the test shaping
the design while the code is written — and would require fully specified interfaces up front.

## Decision
Three roles, three checks:

| Role | Writes | Cannot |
|---|---|---|
| **Planner** (the brief) | Acceptance criteria as **concrete test cases** — literal inputs, expected outputs, named edge cases — plus the unit's public interface | Write a criterion a trivial test could satisfy |
| **Implementer** (fresh session) | Those tests first, shown failing; then the code; then more tests as it refactors | Ship a vanished, skipped or escape-hatched test without the maintainer's label |
| **Checker** (`plan-reviewer` + `/code-review`, separate processes) | Findings only | Approve a criterion with no test that would fail without the change |

1. **Mutation gate** (`make mutate`, CI on changed `core/` modules): a test that never bites fails
   the PR.
2. **Integrity at the outcome** (ADR-0005): no test ID gone, no new skip, no new escape-hatch
   comment, unless `checks-weakened-approved`.
3. **Fresh-context review**: `plan-reviewer` maps each criterion to a test and flags tautologies.

**Escalation, for high-stakes units (described, not built):** a separate session writes acceptance
tests into `tests/acceptance/` from the brief before implementation; the implementer is denied edits
there and must make them pass. For a project whose friction log shows tests being gamed.

## Consequences
- The brief template asks for concrete criteria and the interface; a brief without them is sent back.
- Legitimate test changes (renames, removing a duplicate, fixing a wrong expectation) still happen:
  the hook says what needs the maintainer, the PR carries the label. Same habit as `gates-approved`.
- The assertion-level case (a test kept, its assertion gutted) is seen by the mutation gate on pure
  code and by the reviewer elsewhere; nothing else sees it.
