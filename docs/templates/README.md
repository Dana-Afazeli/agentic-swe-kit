# kitpkg

<One paragraph: what this project is, for whom, and what it does today.>

**Status:** <phase>. <One line on what runs and what does not yet.>

## Start here

| Document | What it is |
|---|---|
| `AGENTS.md` | The rules a Claude Code session loads when it works here: the gate, TDD, the work protocol |
| `docs/kit/PHILOSOPHY.md` · `docs/kit/WORKFLOW.md` · `docs/kit/HARNESS.md` | Why and how we work, and the harness that enforces it (kit-owned; updated by `kit.py update`) |
| `docs/DELTAS.md` | Where this project deviates from the kit, and why |
| `docs/ROADMAP.md` | What we build, phase by phase, with exit criteria — the living status |
| `docs/BACKLOG.md` | Everything we could do but have not scheduled |
| `docs/decisions/` | Decision records; never edited after acceptance |
| `docs/briefs/` | One brief per unit of work — the file a fresh Claude Code session executes |
| `docs/research/` | Dated, verified research notes — anything we had to look up |
| `docs/FRICTION.md` | What went wrong or slow, and what would have caught it |

## Rules of the tree (the short list — `AGENTS.md` is the full one)

1. Everything lands on `main` through a PR from a `main-NNN-slug` branch. Nobody commits to `main` directly.
2. `make check` must be green before any work is called done.
3. Secrets never enter the repo. Runtime state lives outside it.
4. Kit-owned files change through `kit.py update` or a PR to the kit; project additions go in
   `project.mk`, `.github/workflows/project.yml`, `docs/DELTAS.md` and the "Project rules" of `AGENTS.md`.

---
Built on [agentic-swe-kit](https://github.com/Dana-Afazeli/agentic-swe-kit) (MIT; `docs/kit/LICENSE`),
version recorded in `kit.lock`.
