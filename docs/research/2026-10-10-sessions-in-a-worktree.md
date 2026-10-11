# Research notes — a Claude Code session started in a git worktree (observed 2026-10-10)

Carried from the source project's `docs/research/` (its pull request #17, merged 2026-10-10): the
runs and versions are the ones named below.
**Status:** snapshot (2026-10-10) — not edited; newer findings go in a new dated file.

Observed for brief 009 with CLI **2.1.296** (`claude --version`), on macOS, permission mode `auto`
for the session under observation. The session was started in a worktree of the development
checkout; each row says how it was observed. "The tree" is `~/centcom-v2-009`, a worktree made
with `git worktree add` on branch `v2-009-parallel-trees`; "the main checkout" is `~/centcom-v2`,
on `v2`.

```
$ git rev-parse --git-dir --git-common-dir        # in the tree
/Users/sophos/centcom-v2/.git/worktrees/centcom-v2-009
/Users/sophos/centcom-v2/.git
$ git worktree list
/Users/sophos/centcom-v2      3af6164 [v2]
/Users/sophos/centcom-v2-009  b91dc15 [v2-009-parallel-trees]
```

## What was observed

| Question | Answer | How |
|---|---|---|
| `$CLAUDE_PROJECT_DIR` a hook sees | **the tree** | a logging hook, below |
| which `.claude/settings.json` took effect | **the tree's own** | the Bash guard that refused a command was the tree's `scripts/guard_bash.py`; the lock hook of the tree's file fired; a two-folder test repository |
| which `.claude/settings.local.json` took effect | **both**: the tree's own, and the main checkout's | a hook in the tree's file fired; an allow rule in the main checkout's file applied in the tree |
| the folder in which the Stop hook ran `make check` | **the tree** | `coverage.xml` mtimes |
| the shared `pre-commit` hook, for a commit made in the tree | **ran, in the tree**; the hook file is the main checkout's | commit output, `coverage.xml` mtimes |
| where the transcript is | `~/.claude/projects/-Users-sophos-centcom-v2-009/<session_id>.jsonl` (the tree's own folder) | hook input |
| can a `SessionStart` hook refuse a session | **no**; it can add to the context | a hook that exits 2; a hook that prints JSON |
| `session_id` of a subagent's tool call | **the parent's**, with `agent_id` and `agent_type` added | hook input |
| auto-memory | **the main checkout's** folder, `~/.claude/projects/-Users-sophos-centcom-v2/memory/` | the path the session was given, and a listing |
| workspace trust | looked up under **the main checkout's path** | a warning from a headless run |
| do the new lock hooks fire in the tree | **yes** | the lock file, and a second session |

### `$CLAUDE_PROJECT_DIR`, the transcript and the subagent
A logging hook (`sh probe.sh <event>`, kept outside the repository) in the tree's
`.claude/settings.local.json` on `PreToolUse` for `Write|Edit|Agent`, on `SessionStart` and on
`Stop`. It printed `pwd`, `$CLAUDE_PROJECT_DIR` and the hook's stdin. For a `Write` of the session:

```
pwd=/Users/sophos/centcom-v2-009
CLAUDE_PROJECT_DIR=/Users/sophos/centcom-v2-009
stdin={"session_id":"216e706b-d0ac-493e-8448-0574f409cc29",
  "transcript_path":"/Users/sophos/.claude/projects/-Users-sophos-centcom-v2-009/216e706b-….jsonl",
  "cwd":"/Users/sophos/centcom-v2-009", … "permission_mode":"auto",
  "hook_event_name":"PreToolUse","tool_name":"Write", …}
```

A subagent (`Agent` tool, Haiku, one `Write`) in the same session, as the hook saw its call:

```
{"session_id":"216e706b-d0ac-493e-8448-0574f409cc29","cwd":"/Users/sophos/centcom-v2-009",
 "hook_event_name":"PreToolUse","tool_name":"Write",
 "agent_id":"aef7077287f06065f","agent_type":"general-purpose", …}
```

The session id is the parent's, so a lock keyed on the session id covers a session's subagents.

### The committed `.claude/settings.json`, and `.claude/settings.local.json`
A throwaway repository under `$HOME` (removed afterwards): a main folder on `v2` and a worktree of
it, each with a committed `.claude/settings.json` and an untracked `.claude/settings.local.json`,
each file holding a `SessionStart` hook that appends its own marker to a log and an allow rule
`Bash(touch <its own name>)`. A headless session started in the worktree:

```
$ claude -p '… run touch MAIN_COMMITTED; touch MAIN_LOCAL; touch TREE_COMMITTED; touch TREE_LOCAL; touch NONE …' \
    --model haiku --permission-mode default       # cwd: the worktree
touch MAIN_COMMITTED: DENIED
touch MAIN_LOCAL: RAN
touch TREE_COMMITTED: DENIED     # see the warning below: rules of a committed file were not honoured
touch TREE_LOCAL: RAN
touch NONE: DENIED
$ sort seen.log | uniq -c        # the hooks that fired
   1 HOOK_MAIN_LOCAL
   1 HOOK_TREE_COMMITTED
   1 HOOK_TREE_LOCAL
```

So for hooks: the tree's committed file, the tree's local file and **the main checkout's local
file** ran; the main checkout's committed file did not. The warning that came with that run:

```
Ignoring 1 permissions.allow entry from .claude/settings.json: this workspace has not been
trusted. Run Claude Code interactively here once and accept the trust dialog, or set
projects["/Users/sophos/.probe-009-matrix/main"].hasTrustDialogAccepted: true in …/.claude.json.
```

It names the **main** folder: trust of a worktree is looked up under the main checkout's path
(the tree `~/centcom-v2-009` is not in `~/.claude.json` at all and ran without a dialog). The
test repository was untrusted, so its committed file's allow rule was ignored; the hook markers
are what show which committed file was read.

The same question on the real repository, with the one rule in the main checkout's
`.claude/settings.local.json` (`Bash(echo "check exit=$?")`; the tree has no such rule):

```
$ claude -p 'Run each of these two bash commands … (1) echo "check exit=$?"  (2) echo "other exit=$?" …' \
    --model haiku --permission-mode default       # cwd: the tree
(1): RAN
(2): DENIED
$ claude -p 'Run exactly this bash command … echo "check exit=$?" …' --model haiku \
    --permission-mode default                     # cwd: a bare folder with no settings
DENIED
```

An `echo` without `$?` is allowed by default, so a probe with plain `echo` shows nothing; the rule
applies to exactly the command it names.

### The Stop hook and the `pre-commit` hook
`coverage.xml` is written by `make check` in the folder it runs in. In the tree, with changes
against `origin/v2`:

```
before:  15:21:40  coverage.xml        13:46:49  /Users/sophos/centcom-v2/coverage.xml
$ claude -p 'Reply with the single word: ok' --model haiku --max-turns 2     # cwd: the tree
ok                                     # a turn ended, the Stop hook ran make check (62 s)
after:   15:22:57  coverage.xml        13:46:49  /Users/sophos/centcom-v2/coverage.xml
```

The hook's command is `uv run --project "$CLAUDE_PROJECT_DIR" python "$CLAUDE_PROJECT_DIR/scripts/stop_gate.py"`,
and `stop_gate.py` runs `make check` in its own parent folder: the tree.

The git hook is one file, in the main checkout's `.git/hooks/`, shared by every worktree:

```
$ sed -n 5,6p /Users/sophos/centcom-v2/.git/hooks/pre-commit
HERE="$(cd "$(dirname "$0")" && pwd)"
PREK="/Users/sophos/centcom-v2/.venv/bin/prek"
```

It names the main checkout's `prek` binary and so needs that checkout's `.venv`. A commit made in
the tree ran the hooks of `.pre-commit-config.yaml` there:

```
ruff format --check (staged Python)......................................Passed
make check (the gate)....................................................Passed
before 15:05:05 (tree)   after 15:16:23 (tree)   main checkout's coverage.xml: 13:46:49, unchanged
```

### A `SessionStart` hook cannot refuse a session
```
$ claude -p 'Reply with the single word: alive' --model haiku --max-turns 2 \
    --settings '{"hooks":{"SessionStart":[{"hooks":[{"type":"command","command":"echo REFUSED-BY-HOOK >&2; exit 2"}]}]}}'
alive
```

What it can do is add to the context: `scripts/session_lock.py`, in a held tree, prints
`{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "…"}}`, and a
second session in that tree, asked what it was told at session start, quoted it back.

### The lock hooks, in the tree
After the hooks were added to the tree's `.claude/settings.json` (hooks reload while a session
runs), the session's next edit took the lock, in the tree's own git directory and not in the
working tree:

```
$ cat "$(git rev-parse --absolute-git-dir)/centcom-session.lock"
{"session_id": "216e706b-d0ac-493e-8448-0574f409cc29", "seen": 1791635036.9198}
$ git status --porcelain          # the lock is not listed
```

A second session (a headless `claude -p` in the tree, permission mode `acceptEdits`):

```
SessionStart note:  This tree is held by session 216e706b-…, last seen 0 minutes ago. Edits made
                    here are refused while it holds the lock; to work in a tree of your own, run
                    `make tree BRIEF=NNN` in the main checkout and start a session there, …
Write docs/lock-probe.txt → PreToolUse:Write hook error: … session lock: this tree is held by
                    session 216e706b-…, last seen 0 minutes ago. One session works in a tree; …
                    run `make tree BRIEF=NNN` … (the file was not created)
```

The way round, tried with the same second session: `touch docs/lock-probe.txt` through the Bash
tool under `acceptEdits` ran and created the file. The lock stops the editing tools; the shell is
not covered, as the brief says. A `>` redirect under permission mode `default` was refused, by
Claude Code's own prompt for a redirect and not by the lock.

## What follows
- **Hooks, rules and the Stop gate of a tree are the tree's own**; nothing in `scripts/` or the
  committed settings resolves to the main checkout. The pre-commit hook runs the tree's config but
  the main checkout's `prek` binary.
- **The main checkout's `.claude/settings.local.json` applies in every tree**, besides the tree's
  own. ADR-0004 expected the opposite (a tree's local file ignored); the tree's file is read.
- **Auto-memory is shared by every tree** (it follows the main checkout); a transcript is the
  tree's own.
- A session's subagents carry its `session_id`, so the lock needs no special case for them.
