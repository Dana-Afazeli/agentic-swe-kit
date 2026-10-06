# Research notes — Claude Code hooks and subagent files (verified 2026-10-03)

**Status:** snapshot (2026-10-03) — not edited; newer findings go in a new dated file.
Carried into the kit from the project it was written for; `brief 002` and `PR #5` are that project's.

Read for brief 002 in the official docs (`code.claude.com/docs/en/hooks`, `…/hooks-guide`,
`…/sub-agents`, `…/memory`) with CLI 2.1.288 installed. **Docs-verified**, not spike-verified;
what brief 002's Part 2 proofs observed is in PR #5. Adds to, and in one place corrects, the "dev
harness facts" of `2026-09-29-agent-sdk-claude-code-tooling.md`.

## Hooks
- **Not snapshotted at session start.** "Direct edits to hooks in settings files are normally
  picked up automatically by the file watcher"; if they have not appeared after a few seconds,
  restart the session. Brief 002 assumed the opposite. `/hooks` is a read-only browser of what is
  loaded.
- **Input** (JSON on stdin), common fields: `session_id`, `transcript_path`, `cwd`,
  `permission_mode`, `hook_event_name`, … **`cwd` follows the session:** it is "the new directory
  after Claude runs `cd`". `$CLAUDE_PROJECT_DIR` stays at the project root where the session
  started.
- **Where a hook command runs:** "in the current directory with Claude Code's environment" — the
  directory that follows `cd`, not the project root. A hook that needs the project environment
  must say so (`uv run --project "$CLAUDE_PROJECT_DIR" …`).
- **PreToolUse:** adds `tool_name`, `tool_input`, `tool_use_id`. For `Bash`: `tool_input.command`
  (plus `description`, `timeout`, `run_in_background`). For `Write`/`Edit`/`Read`,
  `tool_input.file_path` is always absolute.
- **Exit codes.** 2 = blocking error: on PreToolUse the tool call is blocked and stderr is the
  reason shown to Claude; on Stop it "prevents Claude from stopping" and stderr is the reason; on
  PostToolUse nothing can be blocked, stderr is shown to Claude. 0 = success; stderr goes to the
  debug log only. **Any other code does not block**: exit 1 is a non-blocking error, and "a hook
  that can't start lands in the same non-blocking bucket" — a mistyped path leaves the gate
  silently off. A PreToolUse command hook that **times out does not block** the tool call.
- **Stop:** input adds `stop_hook_active` (true when the session is already continuing because of
  a stop hook) and `last_assistant_message`. "After stop hooks have continued the turn eight times
  in a row, Claude Code overrides the next block and ends the turn"; the cap is
  `CLAUDE_CODE_STOP_HOOK_BLOCK_CAP`.
- **PostToolUse:** input has `tool_input` and `tool_response`. To tell Claude something without an
  error notice: exit 0 and print `{"hookSpecificOutput": {"hookEventName": "PostToolUse",
  "additionalContext": "…"}}`.
- **Configuration:** `hooks.<Event>[].matcher` (letters, digits, `_`, `|` only = exact names, so
  `Edit|Write`; anything else is a regex; Stop ignores it) and `hooks.<Event>[].hooks[]` with
  `type: "command"`, `command`, and `timeout` in **seconds** (default 600 for command hooks).
  Shell form runs through `sh -c`; path placeholders must be double-quoted there.
- `"disableAllHooks": true` in a settings file, or `--settings '{"disableAllHooks": true}'`,
  switches every hook off. `.claude/**` is a gate path, so that edit asks Dana.

## Subagent files (`.claude/agents/*.md`)
- Frontmatter: `name`, `description` (required); `tools` (comma-separated names; omitted = every
  tool), `disallowedTools`, `model` (`sonnet`, `opus`, `haiku`, `fable`, a full ID, or `inherit`),
  `effort` (`low` … `max`), `permissionMode`, `maxTurns`, and others.
- The tool lists work on whole tools: "a `disallowedTools` entry with a specifier, such as
  `Bash(git push *)`, still removes the whole tool". To keep Bash and limit its commands, use
  `permissions.deny` in the settings: "the rule applies to the main conversation and to subagents".

- **Loaded at session start, unlike hooks** (observed, not from the docs: PR #5's reviewer
  session, started before `.claude/agents/plan-reviewer.md` existed in the checkout, answered
  `Agent type 'plan-reviewer' not found`, while a fresh `claude -p` in the same checkout listed
  it). Start a session after the branch that defines the agent is checked out.

## Permission rules for files (`code.claude.com/docs/en/permissions`, "Read and Edit")
- **`Edit(path)` rules cover every editing tool.** "`Edit` rules apply to all built-in tools that
  edit files." And: "Claude Code checks file permissions against `Edit(path)` and `Read(path)`
  rules only. If you write a path rule for `Write`, `NotebookEdit`, `Glob`, or the legacy
  `MultiEdit` tool instead, Claude Code accepts the rule but never consults it, and warns at
  startup". Observed with CLI 2.1.288: the three `Write(...)` ask rules brief 001 left in
  `.claude/settings.json` printed that warning; PR #5 replaced them with `Edit(...)` rules.

## The shell behind the Bash tool (`code.claude.com/docs/en/tools-reference`, read 2026-10-04)
- **It is the user's shell, not bash.** "The Bash tool runs each command in a separate process."
  And: "Aliases and shell functions defined in your shell startup file are available. At session
  start, Claude Code sources `~/.zshrc`, `~/.bashrc`, or `~/.profile` depending on your shell,
  captures the resulting aliases, functions, and shell options, and applies them to every Bash
  command."
- Observed on Dana's machine with CLI 2.1.288 (PR #5 review, round 7): `echo $0` in a Bash tool
  call answers `/bin/zsh` (zsh 5.9, `SHELL=/bin/zsh`, `BASH_VERSION` unset); a shell error is
  prefixed `(eval):1:`. The options of the startup file are set — `interactivecomments` among
  them, so a `#` starts a comment — but `autocd` did not act: a bare directory name answered
  "command not found". CI's runner has bash and no zsh.
- What follows for `scripts/guard_bash.py`: it has to read a line as zsh does, and as bash does.
  Its tests ask each shell that is installed.

## AGENTS.md
- Read at session start when no `CLAUDE.md`, `.claude/CLAUDE.md` or `CLAUDE.local.md` exists in the
  working directory or above it; `~/.claude/CLAUDE.md` does not count and keeps loading alongside.
  An interactive session prints `no CLAUDE.md found; AGENTS.md loaded: <path>`.
