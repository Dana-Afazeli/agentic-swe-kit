"""The numbered rules of the role skills: each id stands once in a skill's text and has one row."""

import re
from pathlib import Path

import pytest

import roles
from conftest import REPO_ROOT
from roles import Rule

ROOT = REPO_ROOT
SKILLS = ROOT / ".claude" / "skills"

HEADER = "| Id | Rule | Checked from |\n|---|---|---|\n"


def skill(skills: Path, name: str, body: str, rows: str, **references: str) -> Path:
    """A skill folder under `skills`: its SKILL.md, its rules table, and other reference files."""
    folder = skills / name
    (folder / "references").mkdir(parents=True)
    (folder / "SKILL.md").write_text(f"---\nname: {name}\ndescription: d\n---\n{body}", "utf-8")
    (folder / "references" / "rules.md").write_text(f"# Rules\n\n{HEADER}{rows}", "utf-8")
    for stem, text in references.items():
        (folder / "references" / f"{stem}.md").write_text(text, "utf-8")
    return folder


def ids(letter: str, last: int) -> list[str]:
    return [f"{letter}-{number:02d}" for number in range(1, last + 1)]


# --- criterion 1: on temporary skills -------------------------------------------------------------


def test_an_id_in_the_text_with_a_row_is_a_rule(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = skill(
        tmp_path,
        "implementer",
        "1. **I-01** run this skill before anything else.\n",
        "| I-01 | the skill runs first | transcript |\n",
    )

    assert roles.rules(folder) == [Rule("I-01", "the skill runs first", "transcript")]
    assert roles.main(tmp_path) == 0
    assert capsys.readouterr().out.splitlines() == [
        "I-01 · transcript · the skill runs first",
    ]


def test_an_id_in_the_text_with_no_row_fails_and_names_file_and_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    body = "# Steps\n1. **I-01** first.\n2. **I-02** second.\n"
    skill(tmp_path, "implementer", body, "| I-01 | first | PR |\n")

    assert roles.main(tmp_path) == 1
    err = capsys.readouterr().err
    assert "implementer/SKILL.md:7: I-02 has no row in references/rules.md" in err


def test_a_row_with_no_id_in_the_text_fails_and_names_file_and_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rows = "| I-01 | first | PR |\n| I-02 | second | git |\n"
    skill(tmp_path, "implementer", "1. **I-01** first.\n", rows)

    assert roles.main(tmp_path) == 1
    err = capsys.readouterr().err
    assert "implementer/references/rules.md:6: I-02 is nowhere in the skill's text" in err


def test_one_id_in_two_skills_fails_and_names_both(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    skill(tmp_path, "brief-writer", "1. **B-01** sign the brief.\n", "| B-01 | signed | PR |\n")
    skill(tmp_path, "implementer", "1. **B-01** sign it too.\n", "| B-01 | signed | PR |\n")

    assert roles.main(tmp_path) == 1
    err = capsys.readouterr().err
    assert "B-01 is used twice" in err
    assert "brief-writer/SKILL.md:5" in err
    assert "implementer/SKILL.md:5" in err


def test_one_id_twice_in_one_skill_fails_and_names_both_lines(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    body = "1. **I-01** first.\n2. **I-01** again.\n"
    skill(tmp_path, "implementer", body, "| I-01 | first | PR |\n")

    assert roles.main(tmp_path) == 1
    err = capsys.readouterr().err
    assert "I-01 is used twice" in err
    assert "implementer/SKILL.md:5" in err
    assert "implementer/SKILL.md:6" in err


def test_a_checked_from_that_is_not_one_of_the_five_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    skill(tmp_path, "implementer", "1. **I-01** first.\n", "| I-01 | first | vibes |\n")

    assert roles.main(tmp_path) == 1
    err = capsys.readouterr().err
    assert "implementer/references/rules.md:5: I-01 is checked from 'vibes'" in err
    assert "transcript, PR, git, judgment, not checkable" in err


@pytest.mark.parametrize("checked_from", ["transcript", "PR", "git", "judgment", "not checkable"])
def test_each_of_the_five_is_a_place_a_rule_is_checked_from(
    tmp_path: Path, checked_from: str
) -> None:
    folder = skill(
        tmp_path, "implementer", "1. **I-01** first.\n", f"| I-01 | first | {checked_from} |\n"
    )

    assert roles.main(tmp_path) == 0
    assert roles.rules(folder) == [Rule("I-01", "first", checked_from)]


def test_a_list_item_with_no_bold_id_is_not_a_rule_and_not_an_error(tmp_path: Path) -> None:
    body = "1. **I-01** first.\n2. Read the brief; I-01 above says why.\n- **Note** in bold.\n"
    folder = skill(tmp_path, "implementer", body, "| I-01 | first | PR |\n")

    assert roles.main(tmp_path) == 0
    assert roles.rules(folder) == [Rule("I-01", "first", "PR")]


def test_a_row_that_is_not_three_cells_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    skill(tmp_path, "implementer", "1. **I-01** first.\n", "| I-01 | first |\n")

    assert roles.main(tmp_path) == 1
    err = capsys.readouterr().err
    assert (
        "implementer/references/rules.md:5: a row is `| id | a few words | checked from |`" in err
    )


def test_two_rows_for_one_id_fail(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rows = "| I-01 | first | PR |\n| I-01 | again | git |\n"
    skill(tmp_path, "implementer", "1. **I-01** first.\n", rows)

    assert roles.main(tmp_path) == 1
    err = capsys.readouterr().err
    assert "implementer/references/rules.md:6: I-01 has a row already, on line 5" in err


def test_an_id_in_a_reference_file_is_in_the_skills_text(tmp_path: Path) -> None:
    folder = skill(
        tmp_path,
        "reviewer",
        "Read `references/conformance.md`.\n",
        "| P-01 | untested criterion | judgment |\n",
        conformance="1. **P-01 Untested criterion.** No test would fail without the change.\n",
    )

    assert roles.main(tmp_path) == 0
    assert roles.rules(folder) == [Rule("P-01", "untested criterion", "judgment")]


def test_the_implementers_text_also_counts_the_review_loop_skill(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rows = "| I-01 | first | PR |\n| I-13 | read every comment | transcript |\n"
    skill(tmp_path, "implementer", "1. **I-01** first.\n", rows)

    assert roles.main(tmp_path) == 1  # nothing states I-13 yet
    assert "I-13 is nowhere in the skill's text" in capsys.readouterr().err

    loop = tmp_path / "review-loop"
    loop.mkdir()
    (loop / "SKILL.md").write_text("1. **I-13** Read every comment on the PR first.\n", "utf-8")

    assert roles.main(tmp_path) == 0


def test_an_id_in_the_review_loop_skill_with_no_row_names_that_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    skill(tmp_path, "implementer", "1. **I-01** first.\n", "| I-01 | first | PR |\n")
    loop = tmp_path / "review-loop"
    loop.mkdir()
    (loop / "SKILL.md").write_text("# Loop\n\n1. **I-15** Reproduce the finding.\n", "utf-8")

    assert roles.main(tmp_path) == 1
    assert "review-loop/SKILL.md:3: I-15 has no row" in capsys.readouterr().err


# An id is one capital letter, a dash and two digits. What is written like an id and is not one
# is reported: skipped, it would be a rule that neither the text nor the table accounts for.


@pytest.mark.parametrize("written", ["A-7", "A-100", "AB-02", "a-02", "A-02b"])
def test_what_is_written_like_an_id_in_the_text_and_is_not_one_is_reported(
    written: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    body = f"1. **A-01** first.\n2. **{written}** a rule nobody lists.\n"
    skill(tmp_path, "implementer", body, "| A-01 | first | git |\n")

    assert roles.main(tmp_path) == 1
    captured = capsys.readouterr()
    assert f"implementer/SKILL.md:6: {written} is not an id" in captured.err
    assert "one capital letter, a dash and two digits" in captured.err
    assert captured.out == ""


@pytest.mark.parametrize("written", ["A-7", "A-100", "AB-02", "a-02", "A-02b"])
def test_a_row_whose_first_cell_is_written_like_an_id_and_is_not_one_is_reported(
    written: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rows = f"| A-01 | first | git |\n| {written} | a rule with no text | git |\n"
    skill(tmp_path, "implementer", "1. **A-01** first.\n", rows)

    assert roles.main(tmp_path) == 1
    assert f"implementer/references/rules.md:6: {written} is not an id" in capsys.readouterr().err


def test_an_id_that_stands_later_in_a_bold_span_is_no_rule_and_its_row_says_so(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    body = "1. **A-01** first.\n2. **Rule A-02** second.\n"
    skill(tmp_path, "implementer", body, "| A-01 | first | git |\n| A-02 | second | git |\n")

    assert roles.main(tmp_path) == 1
    err = capsys.readouterr().err
    assert "implementer/references/rules.md:6: A-02 is nowhere in the skill's text" in err


def test_bold_text_and_table_rows_that_are_not_written_like_an_id_are_left_alone(
    tmp_path: Path,
) -> None:
    body = (
        "1. **A-01** first, by **RFC-2119**; **UTF-8** text, **3-2-1**, an **e-mail**, "
        "`x9-007`, and a **Note** in bold.\n"
    )
    rows = "| A-01 | first | git |\n| see | the table above | too |\n"
    folder = skill(tmp_path, "implementer", body, rows)

    assert roles.main(tmp_path) == 0
    assert roles.rules(folder) == [Rule("A-01", "first", "git")]


# What the script checks, and no more: the two forms the skills use. In the text a rule is two
# stars and an id, wherever they stand; in the table it is a first cell that is an id. It reads
# no Markdown beyond that: it does not guess what is emphasis, and so it does not take a star in
# a command for one.


@pytest.mark.parametrize(
    "line",
    [
        "**A-02**",
        "**A-02 a name that\nwraps** unlisted",
        "2 ** 3 and **A-02** unlisted",
        "see**A-02** unlisted",
        "rule 2**A-02** unlisted",
        "`make check`**A-02** unlisted",
        "> **A-02** in a quote",
        "***A-02*** in bold italics",
    ],
)
def test_two_stars_and_an_id_are_a_rule_wherever_they_stand(
    line: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    skill(tmp_path, "implementer", f"1. **A-01** first.\n{line}\n", "| A-01 | first | git |\n")

    assert roles.main(tmp_path) == 1
    captured = capsys.readouterr()
    assert "implementer/SKILL.md:6: A-02 has no row in references/rules.md" in captured.err
    assert captured.out == ""


@pytest.mark.parametrize(
    "row", ["A-09 | ghost | git |", "  A-09 | ghost | git", "|A-09|ghost|git|"]
)
def test_a_first_cell_that_is_an_id_is_a_row_with_or_without_its_first_pipe(
    row: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    skill(tmp_path, "implementer", "1. **A-01** first.\n", f"| A-01 | first | git |\n{row}\n")

    assert roles.main(tmp_path) == 1
    err = capsys.readouterr().err
    assert "implementer/references/rules.md:6: A-09 is nowhere in the skill's text" in err


@pytest.mark.parametrize(
    "line",
    [
        'T3\nls "$W"/*pr-15*\nT3',
        "Remove `/tmp/work/*brief-007*` afterwards.",
        "Save it in `$W/_notes-1.md`.",
        "A glob such as *pr-15* or _notes-1_ in plain text.",
        "*RFC-2119* in italics and __UTF-8__ underlined.",
        # two stars in code, before something that is no id
        "Wait `2**n-1` seconds between tries.",
        "T3\ndelay = 2**k-1\nT3",
        "T3\nls docs/**b-1*\nT3",
        "`x = 2**k-1 + 3`",
    ],
)
def test_a_command_a_file_name_or_other_emphasis_is_not_taken_for_a_rule(
    line: str, tmp_path: Path
) -> None:
    body = f"1. **A-01** first.\n{line.replace('T3', '`' * 3)}\n"
    folder = skill(tmp_path, "implementer", body, "| A-01 | first | git |\n")

    assert roles.main(tmp_path) == 0
    assert roles.rules(folder) == [Rule("A-01", "first", "git")]


@pytest.mark.parametrize(
    ("where", "written"),
    [
        ("text", "__A-02__ unlisted"),
        ("text", "*A-02* unlisted"),
        ("text", "**`A-02`** unlisted"),
        ("table", "| `A-09` | ghost | git |"),
        ("table", "| **A-09** | ghost | git |"),
        ("table", "| A-09: | ghost | git |"),
        ("table", "> | A-09 | ghost | git |"),
    ],
)
def test_a_rule_written_in_another_form_is_not_seen(
    where: str, written: str, tmp_path: Path
) -> None:
    """The limit the script states: a rule written in a form the skills do not use is on
    neither list, and whoever reviews the skill is the one to see it."""
    text = f"{written}\n" if where == "text" else ""
    row = f"{written}\n" if where == "table" else ""
    folder = skill(
        tmp_path, "implementer", f"1. **A-01** first.\n{text}", f"| A-01 | first | git |\n{row}"
    )

    assert roles.main(tmp_path) == 0
    assert roles.rules(folder) == [Rule("A-01", "first", "git")]


# Whatever its files hold, the script ends with problem lines and an exit code, never with a
# traceback: a session reads the lines, and a traceback names neither the file nor the others.


@pytest.mark.parametrize("line", ["|", "  |  ", "||", "| |"])
def test_a_table_line_with_no_cell_in_it_is_no_row_and_no_crash(line: str, tmp_path: Path) -> None:
    rows = f"| A-01 | first | git |\n{line}\n"
    folder = skill(tmp_path, "implementer", "1. **A-01** first.\n", rows)

    assert roles.main(tmp_path) == 0
    assert roles.rules(folder) == [Rule("A-01", "first", "git")]


@pytest.mark.parametrize("name", ["SKILL.md", "references/rules.md", "references/notes.md"])
def test_a_file_that_is_not_utf8_text_is_a_problem_by_name_and_not_a_traceback(
    name: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = skill(tmp_path, "implementer", "1. **A-01** first.\n", "| A-01 | first | git |\n")
    (folder / name).write_bytes(b"caf\xe9 **A-01**\n")

    assert roles.main(tmp_path) == 1
    assert f"implementer/{name}: cannot be read as UTF-8 text" in capsys.readouterr().err


def test_a_rule_in_a_file_below_the_references_folder_is_in_the_skills_text(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = skill(tmp_path, "implementer", "1. **A-01** first.\n", "| A-01 | first | git |\n")
    (folder / "references" / "deep").mkdir()
    (folder / "references" / "deep" / "more.md").write_text("**A-02** unlisted\n", "utf-8")

    assert roles.main(tmp_path) == 1
    err = capsys.readouterr().err
    assert "implementer/references/deep/more.md:1: A-02 has no row" in err


def test_an_id_that_is_only_mentioned_declares_no_rule(tmp_path: Path) -> None:
    body = (
        "1. **A-01** first (see A-02, `A-03`, and rules A-04 to A-05).\n"
        "* A-07 opens a list item and is a mention too; 2*A-08 is arithmetic.\n"
    )
    folder = skill(tmp_path, "implementer", body, "| A-01 | first | git |\n")

    assert roles.main(tmp_path) == 0
    assert roles.rules(folder) == [Rule("A-01", "first", "git")]


def test_a_folder_with_no_rules_table_is_not_a_role_skill(tmp_path: Path) -> None:
    other = tmp_path / "other-skill"
    other.mkdir()
    (other / "SKILL.md").write_text("**X-01** is bold here, and nobody counts it.\n", "utf-8")
    skill(tmp_path, "implementer", "1. **I-01** first.\n", "| I-01 | first | PR |\n")

    assert roles.main(tmp_path) == 0


def test_every_problem_is_reported_in_one_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    body = "1. **I-01** first.\n2. **I-02** second.\n"
    skill(tmp_path, "implementer", body, "| I-01 | first | vibes |\n| I-03 | third | PR |\n")

    assert roles.main(tmp_path) == 1
    captured = capsys.readouterr()
    assert len(captured.err.splitlines()) == 3
    assert captured.out == ""  # a table with a problem in it is not printed as if it were right


def test_with_no_role_skill_at_all_it_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert roles.main(tmp_path) == 1
    assert "no skill with a references/rules.md" in capsys.readouterr().err


# --- criterion 2: on the repository ---------------------------------------------------------------

EXPECTED = {
    "brief-writer": ids("B", 12),
    "implementer": ids("I", 17),
    "reviewer": [*ids("P", 9), *ids("C", 6)],
}
BOLD_ID = re.compile(r"\*\*([A-Z]-\d\d)\b")


def stated_in(path: Path) -> set[str]:
    return set(BOLD_ID.findall(path.read_text("utf-8")))


def test_the_repositorys_rules_are_consistent(capsys: pytest.CaptureFixture[str]) -> None:
    assert roles.main(SKILLS) == 0
    assert len(capsys.readouterr().out.splitlines()) == 12 + 17 + 9 + 6


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_each_role_skill_has_exactly_the_ids_the_brief_names(name: str) -> None:
    assert sorted(rule.id for rule in roles.rules(SKILLS / name)) == sorted(EXPECTED[name])


def test_only_the_three_role_skills_carry_rules() -> None:
    carrying = [path.parent.parent.name for path in SKILLS.glob("*/references/rules.md")]

    assert sorted(carrying) == sorted(EXPECTED)


def test_each_id_stands_where_its_role_reads_it() -> None:
    reviewer = SKILLS / "reviewer" / "references"

    assert stated_in(reviewer / "conformance.md") == set(ids("P", 9))
    assert stated_in(reviewer / "correctness.md") == set(ids("C", 6))
    # the five rules of the loop stand in the loop's own skill, the implementer's last step
    assert stated_in(SKILLS / "review-loop" / "SKILL.md") == {
        "I-13",
        "I-14",
        "I-15",
        "I-16",
        "I-17",
    }
    assert stated_in(SKILLS / "implementer" / "SKILL.md") == set(ids("I", 12))
    assert stated_in(SKILLS / "brief-writer" / "SKILL.md") == set(ids("B", 12))
