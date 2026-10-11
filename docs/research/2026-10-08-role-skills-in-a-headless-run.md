# Research notes — role skills in a headless run, and a type checker that skips `.claude` (2026-10-08)

Carried from the source project's `docs/research/` (its pull request #15, merged 2026-10-10): the
runs and versions are the ones named below.
**Status:** snapshot (2026-10-08) — not edited; newer findings go in a new dated file.

Run for brief 007 (the three role skills) with Claude Code 2.1.294 and basedpyright 1.40.1 (based
on pyright 1.1.414). Each fact is marked **spike** (seen in a run on 2026-10-08), or **docs** (read,
not run).

## How the conformance reviewer gets the `reviewer` skill
- **spike** A prompt on stdin that begins `/reviewer conformance` puts the skill's text in front
  of a process started with `claude -p --agent plan-reviewer`, in a clone Claude Code has not been
  told to trust. The run: `--model sonnet --effort low --permission-mode auto --permission-prompts
  none --strict-mcp-config --max-budget-usd 0.5 --output-format stream-json --verbose`, the advisor
  off, in a clone of branch `v2-007-role-files` at `0a98f03`. The prompt asked for the first
  heading of any instructions beyond the agent file and for the bold words that open the five
  items under "What both reviews share", and forbade every tool. The answer gave `# Reviewer` and
  the five openers word for word, in one turn with no tool call (`num_turns` 1), on
  `claude-sonnet-5-5`. $0.04, 68 s.
- **spike** What the record of that run holds: its `init` line lists `reviewer` among
  `slash_commands`, 61 skills, and the tools `Read` and `Bash` (the agent file names `Read, Grep,
  Glob, Bash`; `Grep` and `Glob` are not in the list at start). It holds no `user` line, so the
  prompt as the model received it is not in the record: the evidence that the skill's text
  arrived is the answer that quotes it.
- **spike** The agent file's tool list has no `Skill` tool, and the skill arrived all the same: a
  `/name` at the start of the prompt is expanded before the model's first turn, not by a tool call.
- **docs** (looked up by the planning session of brief 007 at `code.claude.com/docs/en/skills` and
  `…/sub-agents`, on 2026-10-08): a message that starts with `/name args` runs the skill `name`
  with `$ARGUMENTS`; an agent file's `skills:` field preloads a skill's full text.
- **spike** Started as the launcher starts it (its `make_clone` and `sync_clone` on PR #15 at
  `3d51cf6`, its `claude_argv` with `sonnet/low`, its `plan_prompt` with three lines added that
  asked for a check of the set-up in place of a review), the conformance reviewer read
  `.claude/skills/reviewer/references/conformance.md` with `Read`, named the seven kinds P-01 to
  P-07 and the two rules P-08 and P-09 from it, and ran both read commands the reference adds:
  `gh api repos/Dana-Afazeli/centcom/issues/15/comments --jq length` printed 5, and
  `gh pr checks 15` printed the five checks and exited 1, as it does when a check is red. The
  record lists no denied call. $0.06, 4 turns.
- **spike** What the agent file still decides: the tools. A process started with
  `--agent plan-reviewer` begins with 2 tools (`Read`, `Bash`: the `init` line of that run); a
  process started with no agent begins with 25, `Edit`, `Write` and `Task` among them (the
  `init` line of a test run of the implementer skill). The file's `model` and `effort` are
  overridden by the launcher's flags on every call (research note of 2026-10-05).
- **not run** `skills: reviewer` in the agent file, and appending the skill's files the way the
  launcher appends the code review's protocol (`--append-subagent-system-prompt-file`). The first
  way worked, so the launcher uses it: `plan_prompt` in `scripts/review.py` begins with
  `/reviewer conformance`.

## A skill written while a session runs
- **spike** A folder created under `.claude/skills/` during a session is in that session's list
  of skills within the same turn: the session that wrote `reviewer`, `implementer` and
  `brief-writer` was shown each one as available right after writing its `SKILL.md`, and again
  after each edit of a description. (Agent definitions under `.claude/agents/` load when a session
  starts: `docs/research/2026-10-03-claude-code-hooks.md`.)

## A role skill run headless, in a clone (the eight test runs of brief 007)
Each run: `claude -p --model sonnet --effort medium --permission-mode auto --permission-prompts
none --strict-mcp-config --max-budget-usd 5 --output-format stream-json --verbose`, the prompt on
stdin, the advisor off, in a fresh clone whose `origin` was a local bare repository, with a
stand-in `gh` first on the `PATH`.
- **spike** `/implementer 901` at the start of the prompt ran the skill where the clone had it
  (this branch): the session's first steps were the skill's step 1, in order.
- **spike** Where the clone did not have the skill (`v2`), the same prompt reached the model as
  text. Its first sentence: "`/implementer` isn't installed in this session, so I'll treat this
  as a plain request to implement brief 901." Nothing failed and the run went on.
- **spike** A request in plain words started the skill too: both brief-writer runs on this
  branch ("next is the HTML rendering unit …", "write the brief for bursts …") made
  `Skill brief-writer` their first tool call.
- **spike** `$CLAUDE_CODE_SESSION_ID` is set in a headless run's shell and is the `session_id` of
  its record: the brief one run wrote ends `Brief written in session 166c2eab-…`, the id in that
  run's `result` line.
- **spike** A run in a fresh clone loads the user's own settings all the same: the record's
  `init` line lists the user's agents and 61 skills, and its `memory_paths` names a memory
  folder of its own under `~/.claude/projects/`, one per clone path. So a run "without the
  skill" is not a run without Dana's machine-wide instructions: the run on `v2` that was told
  "the SDK already merges messages" checked the claim against spike 004 and said it did not
  hold, in the words of those instructions ("I took your premise as a hypothesis").
- **spike** An untrusted clone ignores the project's `permissions.allow` (stderr says so), and
  in `auto` mode with no one to ask, the eight runs edited files under `src/`, `tests/` and
  `docs/` and ran `make`, `uv`, `git commit` and `git push`. Six records list no denied call.
  Two list one each (`permission_denials`), and both are refusals by the project's Bash guard,
  read from the tool results: a Python here-document that edited a brief (`gate file — use the
  editor so Dana sees the diff`: the brief's text names gate paths), and a command that ended in
  `rm -f "$P/….bak"` (`rm refused: cannot resolve '$P/…' (a variable, a glob, or a path relative
  to an earlier cd)`). A refused command runs no part of itself: the second also held a page
  written from a here-document and a `pr.py page` call, and the session did both again, the
  page with the editor.
- **spike** Files under `src/` and `tests/` can be written through the shell: two runs on `v2`
  did (`cat > tests/test_preview.py <<'EOF'`, a Python here-document that edited
  `tests/test_policy.py`), and the guard let them pass.
- **spike** Cost and time, eight runs: $0.21 to $0.96 each, $4.06 together, 138 to 694 s. The
  implementer runs on a brief of three criteria: $0.21 to $0.36, 219 to 349 s, `make check` and
  one `make mutate` included.

## The skill-creator's trigger script counts wrongly with more than one worker
- **spike** `scripts/run_eval.py` writes one temporary command per request into the project's
  `.claude/commands/`, and counts a run as triggered when the first tool call is `Skill` or
  `Read` and names that command. Its default is 10 workers, so up to ten temporary commands with
  the same description are on offer at once, and a session that picks a neighbour's is counted
  as a miss. First measurement, default workers, 3 runs per request: 2 of 18 runs triggered on
  the six requests that should start `implementer`, and 2 of 18 for `brief-writer`.
- **spike** The same six `implementer` requests, set up the same way, one run each, stopped at
  the first tool call: five made `Skill implementer-skill-diag00` their first call, each naming
  the first of the six commands on offer and not its own; the sixth started with `Bash` (`ls` of
  the skills folder).
- **spike** Run with `--num-workers 1`, so that one temporary command is on offer at a time, and
  with the real skill taken out of the clone (two skills with one description would split the
  picks the same way): `implementer` 18 of 18 runs on the six requests that should start it and
  0 of 18 on the six near misses; `brief-writer` 18 of 18 and 0 of 18. `--model sonnet`, 3 runs
  per request, `--timeout 90`, in a clone of this branch at `a41b665`. The clone's `AGENTS.md`
  opens with "Roles", which names both skills and when to run them, so these figures are for the
  description and that section together, not for the description alone.

## A dollar sign and a digit in a skill's body is an argument
- **spike** Started through the Skill tool with the arguments `15 --code opus/high --plan
  opus/medium --rounds 5`, the `review-loop` skill reached the session with its sample line
  `· $1.84 · 412 s` reading `· --code.84 · 412 s`: `$1` had been replaced by the second word of
  the arguments, so the count starts at 0. The file itself said `$1.84`. The same skill started
  with no arguments was not looked at.
- So a `SKILL.md` writes a sample amount without a digit after the dollar sign (`$N.NN`), and a
  test fails on `$` followed by a digit in any skill's body. Files under `references/` and
  `assets/` are read with the Read tool and are not touched by this.

## basedpyright does not read a folder whose name starts with a dot
- **spike** With `.claude/skills/implementer/scripts` added to `include` in `pyproject.toml`,
  `uv run basedpyright --verbose` printed `Auto-excluding **/.*` and `Found 66 source files`: the
  66 files under `src`, `tests` and `scripts`, and not `pr.py`. `0 errors` was about those 66.
- **spike** Naming the file on the command line does not help:
  `uv run basedpyright .claude/skills/implementer/scripts/pr.py` printed `No source files found.`
  and `0 errors, 0 warnings, 0 notes`.
- **spike** `exclude = ["**/__pycache__"]` in `pyproject.toml` did not replace the default
  excludes: the same `Auto-excluding **/.*` line, the same 66 files. The checker's own source says
  why (`dist/pyright.js`): the defaults "are applied additively on top of any user-specified
  excludes and, like any other exclude, take precedence over `include`", unless a setting
  `useDefaultExcludes` is off.
- **spike** `useDefaultExcludes = false` under `[tool.basedpyright]`: `Config contains unrecognized
  setting "useDefaultExcludes"`, and the same 66 files. It is read from the command-line options
  of the language server, not from a config file.
- **spike** A copy of the file in a folder with no dot in its path is analysed, in the project's
  strict mode, when the checker is run from the repository root:
  `python -m basedpyright --outputjson <copy of pr.py> <a file with an unannotated function>`
  reported `filesAnalyzed: 2` and four errors, all in the second file.
- So a Python file under `.claude/` is outside `make types`, silently. `pr.py` is covered by
  `tests/test_pr.py::test_the_script_passes_the_strict_type_check_on_a_copy_outside_its_dot_folder`,
  which also fails if the checker reads fewer files than it was given. ruff does read `.claude/`.
