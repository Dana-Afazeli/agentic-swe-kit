# Research notes — the conformance reviewer with no agent file (2026-10-10)

Carried from the source project's `docs/research/` (its pull request #15, merged 2026-10-10): the
runs and versions are the ones named below.
**Status:** snapshot (2026-10-10) — not edited; newer findings go in a new dated file.

Run for brief 007 with Claude Code 2.1.295, to see whether `scripts/review.py` can start the
conformance reviewer without `.claude/agents/plan-reviewer.md`. Each fact is marked **docs**
(read, not run) or **spike** (seen in the record of a run on 2026-10-10).

## A tool list on the command line
- **docs** `claude --help`: `--tools <tools...>`, "Specify the list of available tools from the
  built-in set. Use "" to disable all tools, "default" to use all tools, or specify tool names
  (e.g. "Bash,Edit,Read")." `--allowedTools` and `--disallowedTools` are lists "of tool names to
  allow" and "to deny": permission rules, not the tools a process has.
- **spike** `claude -p --tools Read,Grep,Glob,Bash`, with no `--agent` and otherwise as the
  launcher starts the conformance reviewer: its own clone of PR #15 at `fa15e6e`, its own prompt,
  `--model sonnet --effort low --permission-mode auto --permission-prompts none
  --strict-mcp-config --max-budget-usd 0.75 --output-format stream-json --verbose`, the advisor
  off. The `init` line of the record lists four tools: `Bash`, `Glob`, `Grep`, `Read`. Started
  with `--agent plan-reviewer`, whose file named the same four, a process began with two, `Read`
  and `Bash` (note of 2026-10-08).
- **spike** The skill arrives all the same. `reviewer` is among the `slash_commands` of that
  `init` line. The prompt began `/reviewer conformance`, and the process read
  `.claude/skills/reviewer/references/conformance.md` with `Read` and named its seven kinds (P-01
  to P-07) and its two rules (P-08, P-09).
- **spike** Both read commands of the reference ran: `gh api
  repos/Dana-Afazeli/centcom/issues/15/comments --jq length` printed 13, and `gh pr checks 15`
  printed the five checks and exited 1, as it does when a check is red. The record lists no
  permission denial.
- **spike** It has no `Edit` and no `Write` tool. Told to create a file with any tool that is
  not Bash, it answered that it has none, and the clone held no such file afterwards. Bash is
  still among its tools, and a shell can write: that it reads only is asked of it (rule P-08),
  and the clone is what keeps a write away from everyone else. Writing through Bash was not
  tried in this run.
- **spike** The run: 4 turns, `claude-sonnet-5-5` on every one, $0.06, 76 s.

## What the file under `.claude/agents/` did besides
- **spike** In that run the clone still held the agent file, and the `init` line lists
  `plan-reviewer` among the `agents` of a process that was not started with it. So a file under
  `.claude/agents/` is offered to every session in the repository: with the file there, a session
  could spawn the conformance reviewer through the Agent tool, outside the launcher's spending
  cap, time limit and advisor switch. Without the file there is no agent of that name. A session
  can still run the `reviewer` skill itself, or start a `claude` process by hand: what is gone is
  the agent, not every other way.

## A whole review started this way
- **spike** The conformance review of PR #15 at `88f2e5a`, started by the launcher with
  `--tools Read,Grep,Glob,Bash` and no agent, on Opus at medium: 22 turns, every one on
  `claude-opus-5-5`, 216 s, $0.91, no denied tool call. It read the brief, the description, the
  diff and the comments, and ended with three findings and its verdict line (its record comment
  on the pull request, 2026-10-09 23:22 UTC).

## Not run
- `--tools` on a CLI older than 2.1.295.
- A write through Bash by the conformance reviewer, and what the clone does with it.
