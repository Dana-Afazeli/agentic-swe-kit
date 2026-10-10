# Maintaining the kit itself

The kit is a project under its own harness: briefs, PRs, the review loop, `gates-approved`. This
file is kit-only: `init` removes it, and a project never receives it.

- A change is proven on the kit first (`make check`, `make prove`, CI), then released.
- `CHANGELOG.md` has an `Unreleased` section; every PR adds its line there.
- Release: bump `KIT_VERSION` in `kit.py`, move `Unreleased` under the version heading with the date,
  merge, tag `vX.Y.Z` on `main`, `gh release create vX.Y.Z --notes-from-tag`. A test asserts the
  changelog has a heading for `KIT_VERSION`.
- Renaming or removing a kit-owned file: `update` adds the new path and deletes the old one only
  where the project left it unchanged; say so in the changelog.
- The kit's own decision records, briefs and research notes are records of the kit: they live in
  `docs/decisions/`, `docs/briefs/` and `docs/research/`, are kit-only, and no file a project
  receives names one. `tests/harness/test_stateless.py` renders the kit as a project and scans it
  for a record id, a pointer to a record, and a date.
