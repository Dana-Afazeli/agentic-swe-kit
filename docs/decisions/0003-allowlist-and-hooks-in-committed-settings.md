# ADR-0003 — The dev-session permissions and hooks live in the committed `.claude/settings.json`

**Status:** accepted 2026-10-06 (adopted from the source project's ADR-0005 of 2026-09-30) ·
**Deciders:** the maintainer

## Context
Claude Code reads permission rules and hooks from several places: a user-level file, the project's
committed `.claude/settings.json`, a gitignored `.claude/settings.local.json`, and `--settings` on
the command line. The question was where the rules that make the harness work — the allowlist that
keeps prompts rare, the `ask` rules on gate files, the deny rules, the three hooks, the subagent
model pin — should live.

## Decision
- In the committed `.claude/settings.json`: versioned, reviewed in PRs, present in every clone,
  and a gate file (`gates-approved`), so a session cannot quietly loosen it.
- `.claude/settings.local.json` stays gitignored for personal, machine-only tweaks.
- Agents that a project *runs* (not the ones that *develop* it) never read these files; a project
  that runs agents composes their permissions in code.

## Consequences
- Every change to permissions is a diff the maintainer reads; the CI job `gate-guard` flags PRs that
  touch it.
- A new clone has the harness from its first session; nothing has to be set up per machine except
  the git hooks (`uv run prek install`, development checkout only).
- Permission rules are prefix matches on a spelling. The Bash guard (a hook, also in this file)
  catches the flag wherever it sits; a deny rule is the floor for the case where a hook cannot start.
  A prefix deny must not cover the unit branches: `Bash(git push origin main:*)` would also refuse
  `git push origin main-001-slug`, so the base-branch denies are exact spellings.
