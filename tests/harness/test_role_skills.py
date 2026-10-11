"""The three role skills, what is left in AGENTS.md, and the two templates that moved.

These read files of the repository, so a change to a skill that breaks its own shape turns
`make check` red. The skills are the same text in every project made from the kit: a test here
holds in each of them too.
"""

import re
import subprocess
from pathlib import Path

import pytest

import review
from conftest import REPO_ROOT

ROOT = REPO_ROOT
SKILLS = ROOT / ".claude" / "skills"
ROLES = ("brief-writer", "implementer", "reviewer")
BUNDLED = ("references", "assets", "scripts")
# The length of AGENTS.md on the base branch when the roles became skills (2026-10-10).
AGENTS_LINES_BEFORE_THE_ROLES = 92

# Written in two pieces each, so that this file does not name what it says nothing may name.
BRIEF_TEMPLATE = "docs/briefs/000-" + "TEMPLATE"  # the ADR template keeps its 0000-TEMPLATE name
PR_TEMPLATE = "pull_request_" + "template"
OLD_NOTES = "docs/kit/" + "research"  # where the dated lookups were; they are in docs/research/
# Records of what was true when they were written: a brief is the record of its unit, an ADR is
# never edited, a friction row, a changelog entry and a dated lookup say what happened then.
RECORDS = (
    "docs/briefs/",
    "docs/decisions/",
    "docs/research/",
    "docs/FRICTION.md",
    "CHANGELOG.md",
)


def frontmatter(text: str) -> dict[str, str]:
    assert text.startswith("---\n")
    head = text.removeprefix("---\n").split("\n---\n", 1)[0]
    pairs = (line.split(":", 1) for line in head.splitlines() if ":" in line)
    return {key.strip(): value.strip() for key, value in pairs}


def body_of(name: str) -> str:
    return (SKILLS / name / "SKILL.md").read_text("utf-8")


# --- the shape of a role skill --------------------------------------------------------------------


@pytest.mark.parametrize("name", ROLES)
def test_a_role_skill_has_a_name_and_a_description_that_says_when_to_use_it(name: str) -> None:
    fields = frontmatter(body_of(name))

    assert fields["name"] == name
    assert len(fields["description"]) > 100


@pytest.mark.parametrize("name", ROLES)
def test_a_role_skill_is_at_most_200_lines(name: str) -> None:
    assert len(body_of(name).splitlines()) <= 200


@pytest.mark.parametrize("name", ROLES)
def test_a_role_skill_ends_with_how_the_role_ends(name: str) -> None:
    headings = re.findall(r"^#+ (.+)$", body_of(name), flags=re.MULTILINE)

    assert headings[-1] == "How this role ends"
    ending = body_of(name).split("How this role ends", 1)[1].lower()
    for state in ("done", "needs the maintainer", "failed"):
        assert state in ending, state


@pytest.mark.parametrize("name", ROLES)
def test_a_role_skill_names_every_file_bundled_with_it(name: str) -> None:
    folder = SKILLS / name
    bundled = [
        path.relative_to(folder).as_posix()
        for directory in BUNDLED
        for path in sorted((folder / directory).rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
    ]

    assert bundled, "a role skill bundles at least its rules table"
    assert "references/rules.md" in bundled
    assert [path for path in bundled if f"`{path}`" not in body_of(name)] == []


@pytest.mark.parametrize("name", ROLES)
def test_a_role_skill_gives_reasons_and_does_not_shout(name: str) -> None:
    assert re.findall(r"\b(?:ALWAYS|NEVER|MUST)\b", body_of(name)) == []


# --- a skill works in any repository, for any maintainer ------------------------------------------

# The forms in which a text points at one repository's history. A skill holds none: its reader may
# be a session in another repository, working for someone else. (That no skill names the source
# project is `test_no_leftovers.py`'s to check, for every tracked file.)
HISTORY = re.compile(r"FRICTION 20\d\d|\bPR #\d+|\bADR-\d{4}|\bPlan [AB]\b|docs/PLAN-")
A_NAMED_PERSON = re.compile(r"\b(?:she|her|hers|herself|he|him|his|himself)\b", re.IGNORECASE)


def skill_texts() -> list[Path]:
    """Every file of every skill, and any agent file."""
    files = [
        path
        for path in sorted(SKILLS.rglob("*"))
        if path.is_file() and path.suffix in (".md", ".py", ".json")
    ]
    return [*files, *sorted((ROOT / ".claude" / "agents").glob("*.md"))]


def test_the_skills_are_looked_at_whole() -> None:
    names = {path.relative_to(ROOT).as_posix() for path in skill_texts()}

    assert ".claude/skills/review-loop/SKILL.md" in names
    assert ".claude/skills/implementer/scripts/pr.py" in names


def test_no_skill_points_at_this_repositorys_history() -> None:
    found = [
        f"{path.relative_to(ROOT)}:{number}: {match.group()}"
        for path in skill_texts()
        for number, line in enumerate(path.read_text("utf-8").splitlines(), start=1)
        for match in HISTORY.finditer(line)
    ]

    assert found == []


def test_no_skill_gives_the_maintainer_a_pronoun_of_one_person() -> None:
    found = [
        f"{path.relative_to(ROOT)}:{number}: {match.group()}"
        for path in skill_texts()
        if path.suffix == ".md"
        for number, line in enumerate(path.read_text("utf-8").splitlines(), start=1)
        for match in A_NAMED_PERSON.finditer(line)
    ]

    assert found == []


def test_no_skill_body_holds_a_dollar_and_a_digit() -> None:
    """In a skill's body, `$0`, `$1`, … stand for the words it was started with. Started with
    `15 --code opus/high`, a sample line `· $1.84 ·` reaches the session as `· --code.84 ·`."""
    found = [
        f"{path.relative_to(ROOT)}:{number}: {line.strip()[:60]}"
        for path in sorted(SKILLS.glob("*/SKILL.md"))
        for number, line in enumerate(path.read_text("utf-8").splitlines(), start=1)
        if re.search(r"\$\d", line)
    ]

    assert found == []


# --- what is left in AGENTS.md, and the templates ------------------------------------------------


def agents() -> str:
    return (ROOT / "AGENTS.md").read_text("utf-8")


def test_agents_md_says_who_the_maintainer_is_and_which_branch_is_the_base() -> None:
    """The skills say "the maintainer" and "the base branch"; this file is where a session in
    this repository learns what they stand for. The two terms stand in backticks, so that the
    kit's renderer leaves them and rewrites only the name and the branch after them."""
    roles = re.split(r"^## ", agents(), flags=re.MULTILINE)[1]

    assert "`the maintainer` is " in roles
    assert "`the base branch` is `" in roles


def test_agents_md_is_shorter_than_before_the_roles_and_inside_the_budget_it_names() -> None:
    lines = agents().splitlines()
    budgets = re.findall(r"Budget: (\d+) lines\b", agents())

    assert len(budgets) == 1
    assert len(lines) < AGENTS_LINES_BEFORE_THE_ROLES
    assert len(lines) <= int(budgets[0]) < AGENTS_LINES_BEFORE_THE_ROLES


def test_agents_md_opens_with_roles_and_names_how_each_is_started() -> None:
    sections = re.split(r"^## ", agents(), flags=re.MULTILINE)
    first = sections[1]

    assert first.splitlines()[0] == "Roles"
    assert "`/brief-writer`" in first
    assert "`/implementer NNN`" in first
    assert "scripts/review.py" in first  # a reviewer is started by the launcher


def test_agents_md_holds_no_roles_protocol() -> None:
    headings = re.findall(r"^#+ (.+)$", agents(), flags=re.MULTILINE)

    assert not [heading for heading in headings if "TDD" in heading]
    for phrase in ("failing test", "walkthrough", "review-loop"):
        assert phrase not in agents().lower(), phrase


def test_agents_md_keeps_what_every_role_needs() -> None:
    for needed in (
        "make check",
        "is pure",
        "git merge origin/",
        "gates-approved",
        "scope-approved",
        "Secrets never enter the repo",
        "docs/research/",
        "One session per tree",
        "make eval",
        "No global installs",
        "## Project rules",
    ):
        assert needed in agents(), needed
    assert OLD_NOTES not in agents()


def test_the_two_templates_are_where_the_skills_keep_them() -> None:
    assert not (ROOT / f"{BRIEF_TEMPLATE}.md").exists()
    assert not (ROOT / ".github" / f"{PR_TEMPLATE}.md").exists()
    assert (SKILLS / "brief-writer" / "assets" / "brief.md").is_file()
    assert (SKILLS / "implementer" / "assets" / "pr-page.md").is_file()


def test_nothing_but_the_records_names_the_two_templates_that_moved() -> None:
    """A brief, an ADR, a dated lookup, a friction row and a changelog entry say what was true
    when they were written, and stay as they are. Everything else is read as an instruction for
    today."""
    listed = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z"], check=True, capture_output=True, text=True
    ).stdout
    tracked = [path for path in listed.split("\0") if path and not path.startswith(RECORDS)]
    assert len(tracked) > 50  # git answered with the repository's files

    naming: list[str] = []
    for path in tracked:
        file = ROOT / path
        if not file.is_file():  # deleted in the working tree, not yet committed
            continue
        text = file.read_text("utf-8", errors="replace")
        naming += [path for name in (BRIEF_TEMPLATE, f".github/{PR_TEMPLATE}") if name in text]

    assert naming == []


# --- the reviewers read their text from the skill ------------------------------------------------

PR = review.PullRequest(
    number=42,
    repo="o/r",
    head="a" * 40,
    base="main",
    branch="main-042-quiet-hours",
    url="https://github.com/o/r/pull/42",
)
BRIEF = Path("docs/briefs/042-quiet-hours.md")


def test_the_code_reviewers_protocol_is_the_reviewer_skills_correctness_reference() -> None:
    assert review.PROTOCOL == (
        review.ROOT / ".claude" / "skills" / "reviewer" / "references" / "correctness.md"
    )
    assert review.PROTOCOL.is_file()


def test_the_code_review_is_asked_its_four_questions_by_name() -> None:
    """The bundled `/code-review` looks for bugs and for cleanup and has no angle for security;
    what asks it for one is the protocol the launcher appends."""
    protocol = review.PROTOCOL.read_text("utf-8").lower()
    which_review = " ".join(body_of("reviewer").lower().split())

    assert [
        q for q in ("correctness", "cleanness", "maintainability", "security") if q not in protocol
    ] == []
    assert "correct, clean, maintainable and secure" in which_review
    assert "/code-review" in which_review


def test_the_conformance_reviewer_is_started_on_the_reviewer_skill() -> None:
    """A prompt that begins `/reviewer conformance` puts the skill's text in front of the
    process; the launcher's own lines follow it as the skill's arguments."""
    first = review.plan_prompt(PR, BRIEF, 1, 3)
    later = review.plan_prompt(PR, BRIEF, 2, 3)

    for prompt in (first, later):
        assert prompt.startswith(f"/reviewer conformance\n\nBrief: {BRIEF}")
        assert prompt.rstrip().endswith("otherwise `VERDICT: FINDINGS <number of findings>`.")
    assert "Round 2 of at most 3" in later


def test_the_conformance_reviewer_has_no_agent_file_and_the_launcher_names_its_tools() -> None:
    """Who runs is the launcher's to say: the conformance reviewer is started with no agent, on
    the tools its reference tells it to use, without `Edit` and `Write`."""
    conformance = (SKILLS / "reviewer" / "references" / "conformance.md").read_text("utf-8")

    argv = review.claude_argv("plan", review.Spec("sonnet", "medium"), PR, 1, budget=2, root=ROOT)

    assert not (ROOT / ".claude" / "agents" / "plan-reviewer.md").exists()
    assert "--agent" not in argv
    assert argv[argv.index("--tools") + 1].split(",") == ["Read", "Grep", "Glob", "Bash"]
    assert "Use Read, Grep and Glob" in conformance
    assert "Bash is for" in conformance
    assert "Untested criterion" in conformance


def test_the_implementer_keeps_its_own_notes_out_of_the_folder_that_is_posted_whole() -> None:
    """`pr.py proofs` posts every file of the proofs folder. What is the session's own (the
    gate's output before any change, its list of what can go wrong) is saved beside that
    folder, not in it."""
    text = body_of("implementer")
    paragraphs = [" ".join(each.split()) for each in text.split("\n\n")]
    (the_list,) = [each for each in paragraphs if each.startswith("Before the first test")]

    assert '"$P/00-baseline.txt"' not in text
    assert '"$W/baseline.txt"' in text
    assert 'P="$W/proofs"' in text
    assert "`$W`" in the_list
    assert "proofs folder" not in the_list


# --- what the roles agree on ----------------------------------------------------------------------


def test_wherever_a_decisions_parts_are_listed_its_cost_has_the_users_side() -> None:
    """An option costs what it takes to build and what the people who use the result notice of
    it. Each place that lists the parts of a decision says both, in the same words."""
    parts = re.compile(r"what each costs")
    files = [*(path for path in skill_texts() if path.suffix == ".md"), ROOT / "AGENTS.md"]
    places = [
        (path.relative_to(ROOT).as_posix(), flat[match.end() : match.end() + 60])
        for path in files
        for flat in [" ".join(path.read_text("utf-8").split())]
        for match in parts.finditer(flat)
    ]

    assert len(places) >= 5
    assert {name for name, _ in places} >= {
        "AGENTS.md",
        ".claude/skills/brief-writer/SKILL.md",
        ".claude/skills/brief-writer/references/decisions.md",
        ".claude/skills/implementer/assets/pr-page.md",
        ".claude/skills/reviewer/references/conformance.md",
    }
    assert [
        (name, after)
        for name, after in places
        if not after.startswith(" to build and to whoever uses the result")
    ] == []


def test_both_who_shape_the_tests_list_what_can_go_wrong_first() -> None:
    """The brief writer writes the criteria and the implementer writes the tests. Each starts
    from a list of what can go wrong, and names what no test can show for a check by hand."""
    for name in ("brief-writer", "implementer"):
        text = " ".join(body_of(name).lower().split())
        assert "what can go wrong" in text, name
        assert "by hand" in text, name
    template = (SKILLS / "brief-writer" / "assets" / "brief.md").read_text("utf-8").lower()
    page = (SKILLS / "implementer" / "assets" / "pr-page.md").read_text("utf-8").lower()

    assert "check by hand" in template
    assert "check by hand" in " ".join(page.split("## not proven", 1)[1].split())


def test_work_beyond_the_brief_is_approved_by_a_label_that_both_roles_know() -> None:
    """The maintainer's yes to work a brief does not ask for is the label `scope-approved` on
    the pull request. The implementer lists such work with the maintainer's words and asks for
    the label; the conformance reviewer counts it as a finding only without the list or the
    label; `AGENTS.md` names the label among those no session may touch."""
    label = "`scope-approved`"

    def flat(path: Path) -> str:
        return " ".join(path.read_text("utf-8").split())

    implementer = flat(SKILLS / "implementer" / "SKILL.md")
    stay_inside = implementer.split("**I-07**", 1)[1].split("**I-08**", 1)[0]
    conformance = flat(SKILLS / "reviewer" / "references" / "conformance.md")
    out_of_scope = conformance.split("**P-02 Out of scope.**", 1)[1].split("**P-03", 1)[0]
    template = flat(SKILLS / "implementer" / "assets" / "pr-page.md")
    differs = template.split("## Where this differs from the brief", 1)[1].split("## ", 1)[0]

    assert label in stay_inside
    assert "Where this differs from the brief" in stay_inside
    assert label in out_of_scope
    assert "gh pr view" in out_of_scope
    assert "words" in differs
    assert label in differs
    assert label in flat(ROOT / "AGENTS.md")


# --- how a decision is put to the maintainer ------------------------------------------------------


def test_a_decision_is_a_list_with_one_bullet_per_option_and_each_has_both_costs() -> None:
    """A decision put to the maintainer is not a paragraph: one bullet per option, however few,
    each saying what it is "To build" and what it is "To use". Each role that asks one says so in
    its own skill, with the same two labels, and the template and the example show them."""
    shape = ("one bullet per option", "To build", "To use")

    def flat(*parts: str) -> str:
        return " ".join((SKILLS.joinpath(*parts)).read_text("utf-8").split())

    places = {
        "implementer SKILL": flat("implementer", "SKILL.md"),
        "implementer template": flat("implementer", "assets", "pr-page.md"),
        "implementer example": flat("implementer", "references", "page.md"),
        "brief-writer SKILL": flat("brief-writer", "SKILL.md"),
        "brief-writer example": flat("brief-writer", "references", "decisions.md"),
        "review-loop SKILL": flat("review-loop", "SKILL.md"),
    }

    missing = [
        (place, phrase) for place, text in places.items() for phrase in shape if phrase not in text
    ]
    assert missing == []
    # one pair of labels: the older wording of the second one is gone
    assert not [place for place, text in places.items() if "What a user notices" in text]


# --- the state of the review ----------------------------------------------------------------------


def test_the_first_step_of_the_maintainer_says_whether_the_review_is_remaining_or_done() -> None:
    """The maintainer's checklist opens with one line that says where the review stands:
    `Review: remaining`, `Review: done` or `Review: stopped`. The template asks for it, the
    example shows it, the implementer and the review loop each say when it is set, and the
    conformance reviewer counts a page without it as not the page."""
    states = ("Review: remaining", "Review: done", "Review: stopped")

    def flat(*parts: str) -> str:
        return " ".join((SKILLS.joinpath(*parts)).read_text("utf-8").split())

    template = flat("implementer", "assets", "pr-page.md")
    steps = template.split("## Next steps for the maintainer", 1)[1].split("## ", 1)[0]
    example = flat("implementer", "references", "page.md")
    example_steps = example.split("## Next steps for the maintainer", 1)[1].split("## ", 1)[0]
    implementer = flat("implementer", "SKILL.md")
    show_page = implementer.split("**I-10**", 1)[1].split("**I-11**", 1)[0]
    loop = flat("review-loop", "SKILL.md")
    close_out = loop.split("## 5. Close out", 1)[1]
    conformance = flat("reviewer", "references", "conformance.md")
    not_the_page = conformance.split("**P-07 Not the page.**", 1)[1].split("Not style", 1)[0]

    assert all(state in steps for state in states)
    # one meaning: the template defines the three words and the loop and the reviewer judge by it
    for rule in ("when every reviewer is green", "when the rounds are used"):
        assert rule in steps, rule
        assert rule in close_out, rule
    assert "is not green" in not_the_page
    assert "while a finding is still open" not in not_the_page
    assert "Review: remaining" in example_steps
    assert "Review: remaining" in show_page
    # the sentence about the script's checks keeps its subject: the script, not the review line
    assert "The script checks the page's shape and not its words" in implementer
    assert "Review: remaining" in loop.split("## 2.", 1)[0]
    assert "Review: done" in close_out
    assert "Review: stopped" in close_out
    assert "Review:" in not_the_page
