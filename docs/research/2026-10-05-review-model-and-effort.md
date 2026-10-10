# Research notes — a model and an effort for the PR reviewers (verified 2026-10-05)

**Status:** snapshot (2026-10-05) — not edited; newer findings go in a new dated file.
Carried into the kit from the project it was written for; the PR numbers are that project's.

Read for the `review-loop` skill in the official docs (`code.claude.com/docs/en/sub-agents`,
`…/skills`, `…/code-review`, `…/headless`, `…/settings`, `…/settings-reference`, `…/env-vars`,
`…/cli-reference`, fetched with `curl`) with CLI 2.1.288 installed, then run. Each fact is marked
**docs** (read, not run) or **spike** (seen in the record of a run on 2026-10-05). Quotes are the
docs' words with link markup removed.

## Why `/code-review` answers on Sonnet inside a session here
- **docs** `/code-review` runs as a *forked skill*, and that is not a fork of the conversation:
  "Claude Code starts a new subagent of the type set in the `agent` field and gives it the skill
  content as its prompt." "Despite the name, a skill with `context: fork` doesn't run in a fork of
  the current conversation, which would hand the subagent everything you've discussed so far."
- **docs** A subagent's model: "Claude Code resolves the subagent's model in this order: 1. The
  per-invocation `model` parameter 2. The subagent definition's `model` frontmatter, where `inherit`
  selects the main conversation's model 3. The `CLAUDE_CODE_SUBAGENT_MODEL` environment variable,
  when you set it to a model alias or model ID 4. The main conversation's model". The Skill tool has
  no `model` argument and the bundled skill names none, so step 3 decides: `.claude/settings.json`
  sets the variable to `claude-sonnet-5-5`. (Before v2.1.251 the variable came first.)
- **docs** The level typed after `/code-review` is the effort: "Pass an effort level to trade
  coverage for confidence."
- **spike** The subagent's type is `general-purpose` (`task_started` line of the record).

## A process of its own takes both
- **docs** `claude -p` has `--model` and `--effort`. In `-p` mode the review runs in the foreground:
  "You run it in non-interactive mode, with the `-p` flag or the Agent SDK; Claude Code waits for
  the review and includes the findings in the response".
- **docs** The pin can be overridden for one process with `--settings`, and not with a shell
  variable. "`--settings`: pass a key as JSON, inline or as a path to a file. Claude Code applies it
  above your user, project, and local files and below managed settings." Of a settings `env` value:
  "A value here overwrites the same variable exported in your shell, and when more than one settings
  file sets a variable, the highest-precedence one applies."
- **spike** `claude -p "/code-review low 6" --model claude-opus-5-5 --effort low --settings
  '{"env":{"CLAUDE_CODE_SUBAGENT_MODEL":"claude-opus-5-5", …}}'`: the reviewer's 4 turns were all
  on `claude-opus-5-5`, and `echo "effort=$CLAUDE_EFFORT"` in its shell printed `effort=low`. The
  session itself made no model turn (`num_turns` 0; its one assistant line has the model
  `<synthetic>`), so the `result` text is the reviewer's report as it came. $0.23, 39 s.
- **spike** `claude -p --agent plan-reviewer --model claude-opus-5-5 --effort low` (the task on
  stdin): all 11 turns on `claude-opus-5-5`, `effort=low`. The flags beat the agent file's
  `model: sonnet` and `effort: medium`. The agent's tool list applied (`Read`, `Bash` at start).
  $0.62, 55 s.
- **not separated** Which of `--effort` and the level argument sets the code reviewer's effort:
  both were `low`. The launcher always passes the same value to both.

## What a reviewer process can be held to
- **docs + spike** Text for the reviewer: `--append-subagent-system-prompt-file` ("Append custom
  text to the end of every subagent's system prompt, nested subagents included, apart from a forked
  subagent, which reuses the conversation's own prompt. Only applies in non-interactive mode with
  `-p`."; the file form needs v2.1.261). It reached the code reviewer: the reviewer ran the command
  the file asked for and ended with the verdict line the file asked for.
- **docs** Spending: `--max-budget-usd`, "Maximum dollar amount to spend on API calls before
  stopping (print mode only). Spend from subagents counts toward the cap."
- **docs** Advisor: `CLAUDE_CODE_DISABLE_ADVISOR_TOOL`, "Set to `1` to disable the advisor tool."
  Set through `--settings`, it applies to that process only. **spike** The three records hold no
  advisor call, and no advisor among the tools listed at start.
- **spike** Permission mode: a `-p` process inherits `defaultMode` from the user's settings (`auto`
  on Dana's machine: `permissionMode` in the record's first line). The launcher names the mode.
- **docs** No one to ask: `--permission-prompts none`, "Anything that would prompt is denied unless
  a `PermissionRequest` hook allows it, Claude is told that nobody can approve the request and not
  to retry it, and the run continues."
- **spike** Deny rules apply in `auto` mode, and a Bash rule stops one spelling only. With
  `--disallowedTools "Bash(git add:*)" "Edit(//<repository>/**)"`: a `Write` inside the repository
  was refused ("File is in a directory that is denied by your permission settings."), `git add
  --dry-run README.md` was refused, `git log` ran. Both refusals are listed in the record's
  `permission_denials`. $0.09. Then, in a throwaway repository with `"Bash(git commit:*)"` and the
  `Edit` rule: `git commit --allow-empty -m plain` was refused by the rule; `git -C . commit
  --allow-empty -m dash-c` ran and made a commit; `python3 -c "open('tracked.txt','a').write('x')"`
  ran and changed the tracked file; `git -c user.name=… commit` was refused, by the auto-mode
  classifier and not by the rule. $0.08. So the path rule on the edit tools holds, and a prefix
  rule on a command is a net for the plain form (the round 1 review of PR #11 found this first).
- **spike** The spending cap does not count a `claude` process the reviewer starts from its shell:
  the round 1 reviewer of PR #11 ran two of its own (about $0.4 by its report) beside the $0.67 the
  launcher read from the record.
- **spike** A write outside the repository works when the folder is passed with `--add-dir` and
  allowed with `--allowedTools "Write(//<folder>/**)"`.
- **spike** `--strict-mcp-config` with no `--mcp-config`: 0 MCP servers and 25 tools at start,
  against 94 tools without it.
- **spike** The project's hooks run in a reviewer process: the Bash guard on every Bash call, and
  the Stop hook at the end.

## A clone for each reviewer
- **spike** `git clone --branch <PR branch> <origin>` from GitHub took 3.6 s and `uv sync --locked
  --all-groups --project <clone>` 1.0 s (warm cache). The clone got a `.venv` of its own although
  the launcher, run under `uv run`, had `VIRTUAL_ENV` set to another one.
- **spike** With the clone's push address set to `no-push://…`, `git push origin HEAD` ends with
  exit code 128 ("git: 'remote-no-push' is not a git command"). That stops a push to `origin`
  only: the round 3 reviewer of PR #11 pushed from such a clone by typing the address out. A
  pre-push hook in the clone now refuses that too, and what is left is a push with the address
  typed out and `--no-verify`. Two tests run real `git` against a local bare repository: six
  spellings that do not get out, and the one that does.
- **spike** `claude -p --agent plan-reviewer` in an untrusted clone: the agent file loaded (tools
  `Read`, `Bash`), 14 turns on `claude-sonnet-5-5`, `gh pr view 6; gh pr diff 6` ran with no call
  denied, and the report ended `VERDICT: GREEN`. $0.21, 70 s.
- **spike** Round 3 on PR #11 was the first whole run through the launcher with the reviewer in a
  clone: 23 turns on `claude-opus-5-5`, 7 findings posted inline, $2.48, 832 s; the clone was at
  the PR's head with a clean tree afterwards and is gone.
- **spike** `uv run python` in the clone, started with the launcher's environment minus
  `VIRTUAL_ENV` and its `.venv` on the PATH, imports `centcom` from the clone's `src/`.
- **spike** A fresh clone is a folder Claude Code has not been told to trust. The project's
  `permissions.allow` entries are then ignored (the process says so on stderr: "Ignoring 26
  permissions.allow entries … this workspace has not been trusted"), and the project's hooks run
  all the same: with `--allowedTools "Bash(gh api:*)"`, `gh api repos/…/issues/11/labels` was
  refused by the Bash guard ("guard_bash: labels are Dana's"). $0.08. The reviewers do not need
  the `allow` entries: they run in `auto` mode with the allowances the launcher passes.
- **spike** `origin/<base>` resolves in the clone and there is no local `<base>` branch: in round
  2 of PR #11 `git log v2..HEAD` failed for that reason, and in round 1 a stale local `v2` made
  the diff show another PR's work. The reviewers are now told `origin/<base>`.

## The record of a run (`--output-format stream-json --verbose`)
- **spike** One JSON object per line. An `assistant` line holds `message.model`, and
  `parent_tool_use_id` is null for the session's own turns and set for a subagent's.
- **spike** The last line has `type: result` with `result` (the final text), `is_error`, `subtype`,
  `total_cost_usd`, `duration_ms` and `permission_denials` (each with `tool_name` and `tool_input`).

## The first real run (round 1 of the code review on PR #11, through `scripts/review.py`)
- **spike** `/code-review high --comment 11` on Sonnet: 16 reviewer turns, all on
  `claude-sonnet-5-5`; 7 findings, each posted as an inline comment from the `-p` run (with
  `gh api`: by the reviewer's report no MCP comment tool was there, as `--strict-mcp-config` leaves
  none); $0.67, 253 s. At `high` the review started no further subagents.

- **spike** Round 2, `/code-review xhigh --comment 11` on Opus: 28 reviewer turns, all on
  `claude-opus-5-5`; 8 findings posted inline; $2.09, 662 s. By the reviewer's report the skill's
  text at `xhigh` says to work in its own context and start no subagents.

## Not verified
- The `max` level, and a review that starts helper agents. A helper that names its own model
  would show as a second model in the record's `answered` line. (Until 2026-10-06 the launcher
  failed such a run; Dana removed that check: the caller names the model when it starts the
  reviewer, and that is the requirement met. The record still lists every model that answered.)
- The Stop hook's `make check` inside a reviewer process on a branch that changed code. Rounds 1
  and 2 on PR #11 were on such a branch, but their records hold no hook events, so whether it ran
  and how long it took was not seen.
- plan-reviewer through the launcher, as one whole call: PR #11 has no brief, so only the code
  review ran through it. plan-reviewer's own command line was run by hand, in a trusted checkout
  and in an untrusted clone (above).
- The launcher's set-up time with a cold `uv` cache (the 1.0 s above is with a warm one).
- A reviewer process that ends with a non-zero exit code and a readable record: the launcher's
  reading of it is tested with doubles only.

## Also seen
- **docs** "Setting `CLAUDE_CODE_SUBAGENT_MODEL` by itself doesn't change the model the built-in
  Explore and Plan subagents run on." Plan A §2 says the pin covers them (BACKLOG, 2026-10-05).
