# ADR-0010 — A project holds no record of the kit

**Status:** accepted 2026-10-10 · **Deciders:** the maintainer, for the rule and points 1 and 2;
points 3 to 6 are choices made when brief 005 was written and read by the maintainer with it, not
answers the maintainer gave

## Context
`kit.py`'s manifest decides what `init` hands to a project. The kit's decision records, briefs,
changelog, roadmap, friction log and backlog were already kit-only. Three things still carried the
kit's history into a project:

- the research notes, which sat under `docs/kit/` and so matched the kit-owned `docs/kit/*`;
- pointers in shipped files to records a project does not have: record ids (`ADR-NNNN`) and the
  paths of notes and briefs;
- sentences that told what happened to the kit instead of what a thing does: a date, an incident, a
  count of review rounds.

A project reading its own `HARNESS.md` met "ADR-0008" and had no ADR-0008.

## Decision
The rule, the maintainer's: **a project receives the structure and empty places for its own
records, and nothing about how the kit came to be.**

1. **The research notes move** to `docs/research/` and are kit-only there. The maintainer's word:
   `move`.
2. **A pointer to a record in a shipped file is removed, and the decision stays.** The maintainer's
   words: "just state the decision without explanation or pointers".
3. **`docs/briefs/` and `docs/research/` ship empty**: a `.gitkeep` of 0 bytes each, project-owned,
   so `init` hands it over and `update` never touches it. Each sits under a kit-only `*` pattern in
   the manifest; the first match wins, so the project-owned patterns come first.
4. **A site that tells an event loses the event and keeps the fact**, in the present tense; a
   condition replaces a story. `PHILOSOPHY.md` is where the reasons live and keeps them; it loses
   its ids, dates and events.
5. **A kit-only test keeps it so.** `tests/harness/test_stateless.py` renders the kit as a project
   with `kit.render_tree` and asserts four things of the result: the files under `docs/`, no record
   id, no path of a kit-only document, no date. `kit.py` is left out of the pointer check: it is the
   manifest and names the kit's tree. Dates are not read in `tests/` (test data carries them), in
   `kit.lock` or in `uv.lock`.
6. **The maintenance notes leave `SETUP.md`**: they become the kit-only `docs/MAINTAINING.md`. The
   one line that is for projects (a fix to a kit-owned file goes to the kit as a pull request)
   stays, in `SETUP.md` §4.

Considered and set aside:
- *A render rule that strips ids and dates at `init` and `update` time.* A project's file would then
  differ from the kit's, and `update`'s three-way merge renders both sides with the same function;
  the kit's own files lose the pointers instead, so the kit and a project read the same.
- *Keeping the notes under `docs/kit/research/` and making that folder kit-only.* The notes are
  records of what was true on a date, like decisions and briefs; they belong beside those, and a
  project's own notes go in the same `docs/research/` that the kit's skills already name.

## Consequences
- A project made before this change takes the update with "5 removed" (the notes) and no conflict.
  A project's own files under `docs/research/` and `docs/briefs/` are never managed.
- Briefs 002 and 004 name `docs/kit/research/…` three times. They are records and are not edited;
  those paths no longer resolve, and the notes are under `docs/research/`.
- `HARNESS.md` §9 says what is true of ownership; `SETUP.md` ends with §6.
- This is wrong if projects turn out to want the kit's dated lookups at hand: they would read them
  in the kit's repository today.
