# ADR-0002 — Separate clones, not worktrees; one Claude Code session per checkout

**Status:** accepted 2026-10-06 (adopted from the source project's ADR-0004 of 2026-09-30 and its
rule of 2026-10-02) · **Deciders:** the maintainer

## Context
A project often needs the repository in more than one place at once: a development checkout where
briefs are executed, a deployment checkout that runs the merged code, a second clone for a planning
session while an implementer works. Git worktrees looked like the answer and failed review twice:
worktrees share `.git/hooks` (a pre-commit hook installed for development runs on every worktree's
commits) and Claude Code reads `.claude/settings.local.json` from the *main checkout's* root when
started in a worktree, so a worktree-local allowlist is silently ignored.

Separately, on 2026-10-02 a planning session ran `git switch` in a folder where an implementer
session was working; the implementer's committed files vanished from its working tree mid-run. A
branch switch changes what every process in that folder sees.

## Decision
1. Separate clones for separate roles; never worktrees. The development checkout is the only one
   with git hooks installed; a deployment checkout is pinned to the base branch and pulled after
   merges; nothing crosses between checkouts except through the remote.
2. **One session per checkout.** A Claude Code session owns the working tree it was started in. A
   second session that needs the repository clones its own copy and deletes it afterwards. Never
   `git switch`, `git checkout`, `git stash` or `git reset` in a folder another session may be using.
3. The reviewers get a throwaway clone of the PR's head for the same reason: a review must not
   depend on what any session does to any checkout.

## Consequences
- Slightly more disk and a `git pull` after merges. Acceptable.
- Documents and configuration never hard-code a host path: paths are examples, configuration is
  `~`-relative or explicit, the repository assumes no host.
- Nothing enforces the one-session rule; `AGENTS.md` states it and the friction log holds the
  incident. A hook that detected a second session in the same folder would be the next step if it
  recurs.
