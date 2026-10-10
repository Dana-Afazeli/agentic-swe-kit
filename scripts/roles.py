"""The numbered rules of the role skills: list them, and fail when text and table disagree.

    uv run python scripts/roles.py

A role skill (`.claude/skills/<role>/`) numbers each instruction that someone could check: the
instruction starts with a bold id, `**I-07**`, where it stands in the skill's text. The skill's
`references/rules.md` has one row per id: the id, a few words, and where the rule can be checked
from. The text is what a session reads; the table is what the maintainer and the adherence check
read. This script keeps the two in step.

A skill's text is its `SKILL.md` and its other Markdown files under `references/`, at any depth.
The implementer's text also counts the `review-loop` skill, its last step, where the rules of the
loop stand.

An id is one capital letter, a dash and two digits. The script checks the two forms the skills
use, and no others:

- in the text, two stars and an id, wherever they stand: `**A-01**`, `**A-01 a name**`;
- in the table, a first cell that is an id and nothing else: `| A-01 | … |`.

A near miss in exactly those two places is a problem: a letter or two, a dash and digits between
two pairs of stars (`**A-7**`, `**AB-02**`), or as a first cell (`A-100`). The script reads no
Markdown beyond that, and does not guess what is emphasis or what is code:

- a single star or an underscore, in a command or a file name, is nothing to it, and `**UTF-8**`
  is left alone;
- two stars followed by something that is no id and has no closing stars (`2**n-1`,
  `docs/**b-1*`) are nothing to it either;
- two stars followed by an id are a rule wherever they stand, inside code too: an id shown as an
  example counts, and is reported as used twice.

The price: a rule written in a form the skills do not use (`__A-02__`, `*A-02*`, an id in
backticks, a cell `A-09:`, a table inside a quote, `**A-7 with a name**`) is on neither list, and
nothing here says so. Whoever reviews the skill is the one to see it.

Prints one line per rule. Exit codes: 0 text and tables agree; 1 they do not, with one line per
problem that names the file and the line: an id in the text with no row, a row whose id is nowhere
in the text, an id used twice, a row that names no known place to check from, a near miss. A
file that cannot be read as UTF-8 text is a problem with its name. Whatever the files hold, the
script ends with such lines and never with a traceback.
"""

import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / ".claude" / "skills"
TABLE = Path("references") / "rules.md"
CHECKED_FROM = ("transcript", "PR", "git", "judgment", "not checkable")
# Text outside a skill's own folder that states rules of that skill, from the folder of skills.
ALSO = {"implementer": (Path("review-loop") / "SKILL.md",)}

# An id follows two stars: `**I-07**`, or `**P-05 proof missing**` where the rule has a name.
ID = re.compile(r"[A-Z]-\d\d")
SHAPE = "an id is one capital letter, a dash and two digits"
# A near miss: a letter or two, a dash, digits. `ADR-0011` and `UTF-8` are not (three letters),
# nor is `e-mail` (no digits) or `3-2-1` (no letters).
NEAR_MISS = re.compile(r"[A-Za-z]{1,2}-\d+[A-Za-z0-9]*")
# Two stars and a word of letters, a dash and digits, wherever they stand in the text; and the
# closing stars, when they follow the word at once.
STARRED = re.compile(r"\*\*([A-Za-z]+-\d+[A-Za-z0-9]*)(\*\*)?")


@dataclass(frozen=True)
class Rule:
    id: str
    words: str
    checked_from: str


@dataclass(frozen=True)
class Place:
    """Where an id stands: a file and a line in it."""

    id: str
    file: Path
    line: int

    def __str__(self) -> str:
        return f"{self.file}:{self.line}"


def _read(path: Path, problems: list[str]) -> str:
    """A file's text. A file that cannot be read as text is a problem, and reads as empty."""
    try:
        return path.read_text("utf-8")
    except (UnicodeDecodeError, OSError) as error:
        problems.append(f"{path}: cannot be read as UTF-8 text ({type(error).__name__})")
        return ""


def _rows(skill: Path) -> tuple[list[tuple[Rule, Place]], list[str]]:
    """The rows of a skill's table with where each stands, and the rows that are not rows."""
    table = skill / TABLE
    rows: list[tuple[Rule, Place]] = []
    problems: list[str] = []
    for number, line in enumerate(_read(table, problems).splitlines(), start=1):
        if "|" not in line:
            continue  # the heading, prose
        # GitHub shows a line with cells as a row with or without its first pipe
        cells = [cell.strip() for cell in line.strip().removeprefix("|").split("|")]
        cells = cells[:-1] if cells[-1] == "" else cells
        if not cells:
            continue  # a pipe and nothing else: no cell, so no row
        if not ID.fullmatch(cells[0]):
            if NEAR_MISS.fullmatch(cells[0]):
                problems.append(f"{table}:{number}: {cells[0]} is not an id: {SHAPE}")
            continue  # the table's header, its rule, a row of another table
        if len(cells) != 3 or not all(cells):
            problems.append(f"{table}:{number}: a row is `| id | a few words | checked from |`")
            continue
        rows.append((Rule(*cells), Place(cells[0], table, number)))
    return rows, problems


def rules(skill: Path) -> list[Rule]:
    """The rules of one skill, as its `references/rules.md` lists them."""
    return [rule for rule, _ in _rows(skill)[0]]


def _texts(skill: Path) -> list[Path]:
    own = [skill / "SKILL.md", *sorted((skill / "references").rglob("*.md"))]
    also = [skill.parent / path for path in ALSO.get(skill.name, ())]
    return [path for path in (*own, *also) if path.is_file() and path != skill / TABLE]


def _stated(skill: Path) -> tuple[list[Place], list[str]]:
    """Every place in a skill's text where two stars are followed by an id, and every near miss
    that stands between two pairs of stars. Found in the whole text, so nothing earlier on a
    line hides one."""
    places: list[Place] = []
    problems: list[str] = []
    for path in _texts(skill):
        text = _read(path, problems)
        for found in STARRED.finditer(text):
            written, closed = found.group(1), found.group(2)
            place = Place(written, path, text.count("\n", 0, found.start()) + 1)
            if ID.fullmatch(written):
                places.append(place)
            elif closed and NEAR_MISS.fullmatch(written):
                problems.append(f"{place}: {written} is not an id: {SHAPE}")
    return places, problems


def _problems(skills: list[Path]) -> list[str]:
    problems: list[str] = []
    first: dict[str, Place] = {}  # where each id was first stated, over all skills
    for skill in skills:
        rows, malformed = _rows(skill)
        problems += malformed
        row_of: dict[str, Place] = {}
        for rule, place in rows:
            if rule.id in row_of:
                earlier = row_of[rule.id].line
                problems.append(f"{place}: {rule.id} has a row already, on line {earlier}")
                continue
            row_of[rule.id] = place
            if rule.checked_from not in CHECKED_FROM:
                problems.append(
                    f"{place}: {rule.id} is checked from {rule.checked_from!r}, "
                    f"which is not one of: {', '.join(CHECKED_FROM)}"
                )
        stated, miswritten = _stated(skill)
        problems += miswritten
        for place in stated:
            if place.id in first:
                problems.append(f"{place}: {place.id} is used twice: also at {first[place.id]}")
                continue
            first[place.id] = place
            if place.id not in row_of:
                problems.append(f"{place}: {place.id} has no row in {TABLE}")
        in_text = {place.id for place in stated}
        problems += [
            f"{place}: {found} is nowhere in the skill's text"
            for found, place in row_of.items()
            if found not in in_text
        ]
    return problems


def main(skills: Path = SKILLS) -> int:
    role_skills = sorted(path.parent.parent for path in skills.glob(f"*/{TABLE}"))
    if not role_skills:
        print(f"roles: no skill with a {TABLE} under {skills}", file=sys.stderr)
        return 1
    problems = _problems(role_skills)
    if problems:
        print(*problems, sep="\n", file=sys.stderr)
        return 1
    for skill in role_skills:
        for rule in rules(skill):
            print(f"{rule.id} · {rule.checked_from} · {rule.words}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
