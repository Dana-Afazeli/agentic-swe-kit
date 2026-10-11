Brief: [`docs/briefs/NNN-slug.md`](docs/briefs/NNN-slug.md)

## What this is, and where it sits
<!-- For a reader who has never seen this repository. What the unit is, in plain words; what comes
     before it in the product and what comes after; each term defined where it first appears; what
     is deliberately not there. Delete each of these comments as you write its part: the script
     refuses a page that still holds one, or a part with nothing written under it. -->

## Next steps for the maintainer
<!-- The first item says where the review stands, in one of three forms: "Review: remaining"
     from the first push until the loop closes; "Review: done" when every reviewer is green, with
     each verdict and every thread still open named; "Review: stopped" when the rounds are used
     and a reviewer is not green, with what is left open. Then every action only the maintainer
     can take, in the order to take it, one checkbox each, and what each one unblocks: what to
     read first, a label to add, a check to run by hand, the merge last. If nothing is needed
     but the read, the others are one item: "- [ ] Read the diff and merge." -->
- [ ]

## Decisions for the maintainer
<!-- "None." or one block per decision, each readable on its own, in this shape:
     **The question, as a question.** The situation in plain words, and the command or the run
     that checked each fact it rests on; then the options and what each costs to build and to
     whoever uses the result, as follows.
     - `option` — To build: what it takes. To use: what the person using the result sees, waits
       for or has to do.
     (one bullet per option, however few, each with both costs; never the options in a sentence)
     Recommendation `option`, and why. Reply `option` or `option`. -->

## Not proven
<!-- What the tests cannot show, and what would show it: where the maintainer can check by hand,
     how. What was not run. -->

Reference: below this line, checked by the reviewers

## File by file
<!-- Every file in the diff and what it is for, one line each. -->

## Where this differs from the brief
<!-- "Nowhere." or each difference: what the brief says, what the pull request does, and why.
     Work beyond the brief that the maintainer asked for: the maintainer's words, quoted, and
     where they were said. Such work needs the label `scope-approved`: ask for it under "Next
     steps for the maintainer". -->

## The review record
<!-- One line per reviewer run, copied from its record comment: round, asked, answered, verdict,
     cost, time. Then how many threads are resolved and how many open, and what no reviewer has
     checked. Before the first review: "Not reviewed yet." -->

## Out of scope, noticed
<!-- Each item is also a line in docs/BACKLOG.md, or in docs/FRICTION.md if something went wrong,
     was slow or confused. -->

## Docs made stale, and fixed
<!-- Each statement of a living document that this diff made false, and where it was fixed. -->

## Gate files changed
<!-- "None." or which gate files, what changed in each and why. The maintainer adds
     `gates-approved` after reading; a later push that touches one removes the label again. -->

## Checks weakened
<!-- "None." or what `uv run python scripts/integrity.py --base origin/<base>` prints, and why
     each line is right. The maintainer adds `checks-weakened-approved`. -->
