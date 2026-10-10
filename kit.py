#!/usr/bin/env python3
"""agentic-swe-kit: start a project from the kit, and take the kit's updates later.

    python3 kit.py init --package NAME [--maintainer NAME] [--base BRANCH] [--branch-prefix X]
                        [--python X.Y.Z] [--labels] [--hooks] [--no-sync]
    python3 kit.py render --package NAME ... --into DIR      (what init would write, elsewhere)
    uv run python kit.py update [--to REF] [--from REF] [--no-sync]   (take a newer kit)
    uv run python kit.py status                                       (where this project stands)

Standard library only, so it runs before `uv` has made an environment. `init` runs once, in a
fresh copy of the kit ("Use this template" on GitHub, then clone): it renders the placeholders,
seeds the project-owned files, removes the kit-only ones, writes `kit.lock` (the answers and the
kit version), re-locks and runs the gate. `update` fetches the kit, renders it at the recorded
version and at the new one with the same answers, and three-way merges every kit-owned file
(`git merge-file`): what the project never touched updates cleanly, its additions survive, a real
collision is a conflict marker it lists. `render_text` is shared, which is what makes that merge
sound (ADR-0007). `status` says where a project stands.

The kit's own tree holds real default values, not templating syntax: package `kitpkg`, base branch
`main`, branch prefix `main`, the maintainer as the phrase "the maintainer", Python 3.13.12. Each
site in a Python, YAML or TOML file carries a `# knob: <name>` comment; JSON rules and prose are
rewritten by exact pattern. docs/kit/HARNESS.md ("Knobs", "File ownership") is the specification.

This file is a gate file: it rewrites the others.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import importlib.util
import io
import json
import keyword
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

KIT_VERSION = "0.1.0"
KIT_REPO = "https://github.com/Dana-Afazeli/agentic-swe-kit"
LOCK = "kit.lock"
LABELS = (
    (
        "brief-approved",
        "0E8A16",
        "The maintainer read the brief in this draft PR; the implementer may start",
    ),
    (
        "gates-approved",
        "1D76DB",
        "The maintainer approved this PR's gate-file changes "
        "(Makefile, pyproject, .claude, .github, scripts)",
    ),
    (
        "checks-weakened-approved",
        "D93F0B",
        "The maintainer approved a removed/skipped test or an added escape-hatch comment "
        "in this PR",
    ),
    (
        "scope-approved",
        "5319E7",
        "The maintainer approved the work beyond the brief that this PR's page lists",
    ),
)


@dataclass(frozen=True)
class Answers:
    """What varies between projects. The kit's own values are PLACEHOLDER."""

    package: str
    base: str
    prefix: str
    maintainer: str
    python: str

    @property
    def minor(self) -> str:
        """`3.13.12` -> `3.13`."""
        return ".".join(self.python.split(".")[:2])

    @property
    def next_minor(self) -> str:
        """`3.13.12` -> `3.14`, the exclusive upper bound of `requires-python`."""
        major, minor = self.python.split(".")[:2]
        return f"{major}.{int(minor) + 1}"

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not self.package.isidentifier() or keyword.iskeyword(self.package):
            problems.append(f"--package {self.package!r} is not a Python identifier")
        elif self.package == PLACEHOLDER.package:
            problems.append(
                f"--package {self.package!r} is the kit's placeholder; choose your name"
            )
        elif self.package != self.package.lower():
            problems.append(f"--package {self.package!r}: use lowercase (PEP 8 package names)")
        elif not re.fullmatch(r"[a-z]([a-z0-9_]*[a-z0-9])?", self.package):
            problems.append(
                f"--package {self.package!r} is not a project name for uv: ASCII letters, digits "
                "and underscores, starting with a letter and ending with a letter or digit"
            )
        elif self.package in SHADOWED or self.package in sys.stdlib_module_names:
            problems.append(
                f"--package {self.package!r} would shadow a module the tests import first "
                f"(the standard library, kit.py and scripts/ come before src/)"
            )
        for name in ("base", "prefix"):
            value = getattr(self, name)
            if not is_branch_name(value):
                option = "branch-prefix" if name == "prefix" else name
                problems.append(f"--{option} {value!r} is not a branch name")
        if self.prefix.startswith(self.base + "/"):
            problems.append(
                f"--branch-prefix {self.prefix!r} is under the base branch's name: git cannot "
                f"create {self.prefix}-001-slug while {self.base} exists"
            )
        if not re.fullmatch(r"\d+\.\d+\.\d+", self.python):
            problems.append(f"--python {self.python!r} is not X.Y.Z")
        if not self.maintainer.strip():
            problems.append("--maintainer is empty")
        elif re.search(r'["`$\\\n]', self.maintainer):
            # the name lands inside the echo "…" lines of ci.yml and in JSON rule texts
            problems.append("--maintainer: no double quote, backtick, dollar sign or backslash")
        return problems


# Module names that pytest's path (`pythonpath = ["scripts", "."]`) resolves before `src/`.
SHADOWED = frozenset(
    {
        "kit",
        "conftest",
        "guard_bash",
        "stop_gate",
        "fmt_hook",
        "integrity",
        "mutation_gate",
        "review",
        "roles",
        "pr",  # the implementer skill's script, on the test path too
    }
    | {"tests", "scripts", "docs", "src"}
)


# What a branch name may hold here: git accepts more (`"`, `,`, `$`, `(`, `)`, `{`, `}`), and the
# name lands in a Python string, in JSON rule texts and in a YAML flow list, where those break.
BRANCH_CHARACTERS = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]*")


def is_branch_name(value: str) -> bool:
    """What git accepts as a branch name (`a..b`, `x.lock`, a space: refused), asked of git, and
    what the rendered files can hold (BRANCH_CHARACTERS)."""
    if not value or value.startswith("-") or not BRANCH_CHARACTERS.fullmatch(value):
        return False
    try:
        result = subprocess.run(
            ["git", "check-ref-format", "--branch", value], capture_output=True, check=False
        )
    except FileNotFoundError:  # no git: the shape was checked above (BRANCH_CHARACTERS)
        return True
    return result.returncode == 0


PLACEHOLDER = Answers(
    package="kitpkg", base="main", prefix="main", maintainer="the maintainer", python="3.13.12"
)

# ----------------------------------------------------------------------------- file ownership
# Patterns match whole repository-relative paths; `*` matches across `/` (fnmatch). The first
# category that matches wins, so the more specific patterns come first. docs/kit/HARNESS.md,
# "File ownership", explains the four categories; tests/harness/test_kit.py checks that every
# tracked file of the kit falls into one. The manifest describes the kit's tree: a path a project
# adds beside it (its own workflow, skills, decisions, briefs) is the project's and is never
# managed, whatever a broad pattern here would say — `update` walks the kit's paths only.

KIT_OWNED = (
    "kit.py",
    "Makefile",
    ".claude/*",
    ".github/workflows/ci.yml",
    ".github/actions/*",
    ".pre-commit-config.yaml",
    "scripts/*",
    "tests/harness/*",
    "tests/prove/*",
    "AGENTS.md",
    ".gitignore",
    ".python-version",
    "docs/kit/*",
    "docs/decisions/0000-TEMPLATE.md",
)
MIXED = ("pyproject.toml",)
# Present in the kit, handed to the project as they are (rendered), never touched again.
PROJECT_OWNED = (
    "project.mk",
    "src/*",
    "tests/conftest.py",
    "tests/test_*.py",
    "uv.lock",
)
# Present in the kit only: removed by `init`, or replaced by a seed below. The first group is
# checked before the kit-owned patterns, which would otherwise claim these exact paths.
KIT_ONLY_FIRST = (
    "README.md",
    "CHANGELOG.md",
    "LICENSE",
    "docs/ROADMAP.md",
    "docs/FRICTION.md",
    "docs/BACKLOG.md",
    "tests/harness/test_kit.py",  # tests the kit's own tree and `init`; meaningless in a project
    "tests/harness/test_no_leftovers.py",  # scans for the source project's names; the kit's only
)
KIT_ONLY = (
    "docs/decisions/*",
    "docs/briefs/*",  # the kit's own briefs; a project's first comes from the brief-writer skill
    "docs/templates/*",
)
# Copied as they are: this file's constants *are* the kit's placeholders, and rendering it would
# rewrite them (the first version did, and the second `init` then refused the project's own name).
VERBATIM = ("kit.py",)
# Seeds: a kit file whose rendered copy becomes a project-owned file.
SEEDS = {
    "docs/templates/README.md": "README.md",
    "docs/templates/DELTAS.md": "docs/DELTAS.md",
    "docs/templates/ROADMAP.md": "docs/ROADMAP.md",
    "docs/templates/FRICTION.md": "docs/FRICTION.md",
    "docs/templates/BACKLOG.md": "docs/BACKLOG.md",
    "LICENSE": "docs/kit/LICENSE",
}
CATEGORIES = (
    ("kit-only", KIT_ONLY_FIRST),
    ("kit-owned", KIT_OWNED),
    ("mixed", MIXED),
    ("project-owned", PROJECT_OWNED),
    ("kit-only", KIT_ONLY),
)


def category(path: str) -> str | None:
    for name, patterns in CATEGORIES:
        if any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns):
            return name
    return None


def is_managed(path: str) -> bool:
    """Whether `update` may touch the file: kit-owned or mixed."""
    return category(path) in ("kit-owned", "mixed")


# ----------------------------------------------------------------------------- rendering

Rule = Callable[[str, Answers], str]


def _knob_line(knob: str, replace: Callable[[str, Answers], str]) -> Rule:
    """Apply `replace` to the lines that carry `# knob: <knob>`."""

    def rule(text: str, answers: Answers) -> str:
        marker = f"# knob: {knob}"
        return "".join(
            replace(line, answers) if marker in line else line
            for line in text.splitlines(keepends=True)
        )

    return rule


def _on_knob_base(line: str, a: Answers) -> str:
    # `"main"` covers Python and ci.yml (`branches: ["main"]`: quoted, so YAML reads a branch
    # named `1.10` or `true` as a string); `[main]` is kept for a bare YAML list
    line = re.sub(r'"main"', f'"{a.base}"', line)
    return re.sub(r"\[main\]", f"[{a.base}]", line)


def _on_knob_prefix(line: str, a: Answers) -> str:
    return re.sub(r'"main"', f'"{a.prefix}"', line)


def _on_knob_python(line: str, a: Answers) -> str:
    # One pass: `>=3.13,<3.14` holds both the kit's minor and the next one.
    kit_minor, kit_next = PLACEHOLDER.minor, PLACEHOLDER.next_minor
    pattern = rf"\b(?:{re.escape(kit_minor)}|{re.escape(kit_next)})\b"
    return re.sub(pattern, lambda m: a.minor if m[0] == kit_minor else a.next_minor, line)


def _prefix_in_text(text: str, a: Answers) -> str:
    """`main-NNN-slug`, `main-001-slug`, `main-:*` (permission rules), `main-kit-update`."""
    return re.sub(r"\bmain-(?=NNN|\d{3}-|:\*|kit-update)", f"{a.prefix}-", text)


def _base_in_text(text: str, a: Answers) -> str:
    """The base branch where prose and the JSON rules name it: `main` in backticks, `origin/main`,
    `HEAD:main`, `--base main`, `origin main` at the end of a rule."""
    text = re.sub(r"`main`", f"`{a.base}`", text)
    text = re.sub(r"\borigin/main\b", f"origin/{a.base}", text)
    text = re.sub(r"\bHEAD:main\b", f"HEAD:{a.base}", text)
    text = re.sub(r"--base main\b", f"--base {a.base}", text)
    return re.sub(r"\borigin main(?=\)\"|\"\))", f"origin {a.base}", text)


def _maintainer(text: str, a: Answers) -> str:
    if a.maintainer == PLACEHOLDER.maintainer:
        return text  # the role phrase stays, in both cases
    # In backticks the phrase is the skills' term for the role (`the maintainer`), not the person:
    # it stays. Elsewhere, `\s+`: hard-wrapped prose may break the phrase over a line end; the
    # name joins the lines.
    spans = re.split(r"(`[^`\n]*`)", text)  # code at the odd positions; a fence's third
    return "".join(  # backtick opens the prose that follows it, so position decides, not a char
        span if position % 2 else re.sub(r"\b[Tt]he\s+maintainer\b", lambda _: a.maintainer, span)
        for position, span in enumerate(spans)
    )


# Never in a .py file: the Python knob sites are the `# knob:` lines, and anything else a name
# could change there — a test's own data, a line's length — would change what the file means or
# how it is formatted. The rename of a branch or a person stays in prose, rules and workflows.
PROSE_ONLY: tuple[Rule, ...] = (
    _prefix_in_text,  # before the base: in the kit both read `main`
    _base_in_text,
    _maintainer,
)


def _package(text: str, a: Answers) -> str:
    text = re.sub(r"\bKITPKG(?=_|\b)", lambda _: a.package.upper(), text)  # KITPKG_EVAL_BUDGET_USD
    return re.sub(r"\bkitpkg\b", lambda _: a.package, text)


RULES: tuple[Rule, ...] = (
    _knob_line("base", _on_knob_base),
    _knob_line("prefix", _on_knob_prefix),
    _knob_line("python", _on_knob_python),
    _package,
)


def render_text(path: str, text: str, answers: Answers) -> str:
    """The kit file `path` with `text`, as the project with `answers` has it."""
    if path in VERBATIM:
        return text
    if path.startswith(".claude/skills/"):
        # skills name no person and no project, so that they are the same text in every project
        # (and in the source they came from); AGENTS.md's Roles section says who and which here
        return text
    if path == ".python-version":
        return answers.python + "\n"
    for rule in RULES:
        text = rule(text, answers)
    if not path.endswith(".py"):
        for rule in PROSE_ONLY:
            text = rule(text, answers)
    return text


def render_path(path: str, answers: Answers) -> str:
    """Where a kit file lands in the project: the sample package is renamed."""
    prefix = f"src/{PLACEHOLDER.package}/"
    if path.startswith(prefix):
        return f"src/{answers.package}/" + path[len(prefix) :]
    return path


# ----------------------------------------------------------------------------- the lock


MIN_PYTHON = (3, 11, 4)  # tomllib, sys.stdlib_module_names, tarfile's extraction filter (3.11.4)


def python_version_problem(major: int, minor: int, micro: int) -> str | None:
    if (major, minor, micro) < MIN_PYTHON:
        return (
            f"kit.py needs Python {'.'.join(map(str, MIN_PYTHON))} or later; this is "
            f"{major}.{minor}.{micro}. `uv python install` gives the project's own, or run "
            "`uv run python kit.py …` once the environment exists"
        )
    return None


def toml_loads(text: str) -> dict[str, Any]:
    import tomllib  # 3.11+: imported here so that main() can say so first

    return tomllib.loads(text)


def toml_string(value: str) -> str:
    """A TOML basic string. JSON's escapes are TOML's, except that JSON writes a character outside
    the BMP as a surrogate pair, which TOML refuses: `ensure_ascii=False` writes the character."""
    return json.dumps(value, ensure_ascii=False)


@dataclass(frozen=True)
class Lock:
    """What `kit.lock` records: the kit a project came from, and the answers it was rendered with.

    `commit` is the kit commit the project's kit-owned files were rendered from — empty after
    `init` from a template copy (GitHub squashes the kit's history), so `update` then starts from
    the tag `v<version>`; `update` records the commit it moved to.
    """

    version: str
    answers: Answers
    repo: str = KIT_REPO
    commit: str = ""


def write_lock(
    root: Path,
    answers: Answers,
    version: str = KIT_VERSION,
    repo: str = KIT_REPO,
    commit: str = "",
) -> None:
    quoted = {f.name: toml_string(getattr(answers, f.name)) for f in fields(answers)}
    lines = [
        "# Written by `kit.py init`, rewritten by `kit.py update`. Do not edit by hand.",
        "[kit]",
        f"repo = {toml_string(repo)}",
        f"version = {toml_string(version)}",
        f"commit = {toml_string(commit)}",
        f"date = {toml_string(dt.date.today().isoformat())}",
        "",
        "[answers]",
        *(f"{name} = {value}" for name, value in quoted.items()),
        "",
    ]
    (root / LOCK).write_text("\n".join(lines), "utf-8")


def read_lock(root: Path) -> Lock:
    data = toml_loads((root / LOCK).read_text("utf-8"))
    answers = Answers(**{f.name: str(data["answers"][f.name]) for f in fields(Answers)})
    return Lock(
        version=str(data["kit"]["version"]),
        answers=answers,
        repo=str(data["kit"].get("repo", KIT_REPO)),
        commit=str(data["kit"].get("commit", "")),
    )


# ----------------------------------------------------------------------------- git and shell


class Missing(Exception):
    """A program this step needs is not installed."""

    def __init__(self, program: str) -> None:
        super().__init__(program)
        self.program = program


def run(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=check)
    except FileNotFoundError as error:
        raise Missing(args[0]) from error


def run_steps(commands: Iterable[list[str]], cwd: Path) -> bool:
    """Run the commands in order for the user to see; stop at the first that does not succeed."""
    for command in commands:
        if not step(command, cwd):
            say(f"{' '.join(command)} did not succeed: fix it, then `make check` again")
            return False
    return True


def print_next_steps(maintainer: str, steps: list[str]) -> None:
    print()
    print(f"Next steps for {maintainer}:")
    for number, text in enumerate(steps, 1):
        print(f"  {number}. {text}")


def step(command: list[str], cwd: Path) -> bool:
    """Run a command for the user to see; True when it succeeded, False when it failed or is not
    installed (said, not raised: by then the tree has been rewritten)."""
    say(" ".join(command))
    try:
        return subprocess.run(command, cwd=cwd, check=False).returncode == 0
    except FileNotFoundError:
        say(f"{command[0]} is not installed: install it, then run the step by hand")
        return False


def tracked_files(root: Path) -> list[str]:
    """The files git tracks that exist in the working tree (unstaged deletions are left out)."""
    out = run(["git", "ls-files", "-z"], root).stdout
    return sorted(path for path in out.split("\0") if path and (root / path).is_file())


def say(message: str) -> None:
    print(f"kit: {message}", flush=True)  # redirected to a file, a step's output follows its line


# ----------------------------------------------------------------------------- init


def render_tree(src: Path, dst: Path, answers: Answers, paths: Iterable[str]) -> list[str]:
    """Render the kit files `paths` from `src` into `dst` (which may be `src`: in place).

    Returns the project paths written. Kit-only files are not written; seeds are written to their
    destinations. Rendering in place renames the sample package and removes what has moved.
    """
    written: list[str] = []
    in_place = src.resolve() == dst.resolve()
    pending: list[tuple[str, str]] = []
    for path in paths:
        cat = category(path)
        if cat is None:
            raise SystemExit(
                f"kit: {path} is in no ownership category (kit.py CATEGORIES); refusing"
            )
        if path in SEEDS:
            pending.append((path, SEEDS[path]))
        if cat == "kit-only":
            continue
        pending.append((path, render_path(path, answers)))
    for source, target in pending:
        text = (src / source).read_text("utf-8")
        out = dst / target
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_text(source, text, answers), "utf-8")
        shutil.copymode(src / source, out)
        written.append(target)
    if in_place:
        seeded = set(SEEDS.values())  # README.md and the docs a seed has just replaced stay
        for path in paths:
            removed = category(path) == "kit-only" and path not in seeded
            if removed or render_path(path, answers) != path:
                (src / path).unlink(missing_ok=True)
        for folder in (src / "docs" / "templates", src / "src" / PLACEHOLDER.package):
            shutil.rmtree(folder, ignore_errors=True)
    return written


def answers_from(args: argparse.Namespace) -> Answers | None:
    """The answers on the command line, or None after saying what is wrong with them."""
    answers = Answers(
        package=args.package,
        base=args.base,
        prefix=args.branch_prefix or args.base,
        maintainer=args.maintainer,
        python=args.python,
    )
    problems = answers.validate()
    for problem in problems:
        say(problem)
    return None if problems else answers


def init(args: argparse.Namespace) -> int:
    root = Path.cwd()
    answers = answers_from(args)
    if answers is None:
        return 2
    if (root / LOCK).exists():
        say(f"{LOCK} exists: this project was initialised already (kit.py update takes updates)")
        return 2
    if (
        not (root / ".git").exists() or not (root / "kit.py").is_file()
    ):  # a worktree's .git is a file
        say("run init at the root of a clone of the kit (where kit.py and .git are)")
        return 2
    if run(["git", "status", "--porcelain"], root).stdout.strip():
        say("the working tree is not clean: commit or stash first, so init's changes are the diff")
        return 2

    paths = tracked_files(root)
    written = render_tree(root, root, answers, paths)
    write_lock(root, answers)
    run(["git", "add", "-A"], root)
    say(
        f"rendered {len(written)} files for package {answers.package!r}, base {answers.base!r}, "
        f"prefix {answers.prefix!r}, maintainer {answers.maintainer!r}, Python {answers.python}"
    )
    seeded = ", ".join(sorted(SEEDS.values()))
    say(f"removed the kit-only files; seeded {seeded}; wrote {LOCK}")

    status = 0
    if not args.no_sync:
        owned_python = [
            "src",
            "tests/conftest.py",
            *sorted(str(p.relative_to(root)) for p in root.glob("tests/test_*.py")),
        ]
        commands = (
            ["uv", "lock"],
            ["uv", "sync", "--all-groups"],
            ["uv", "run", "ruff", "format", *owned_python],
            ["make", "check"],
        )
        if not run_steps(commands, root):
            status = 1
    if args.labels:
        status = max(status, create_labels(root))
    if args.hooks and not step(["uv", "run", "prek", "install"], root):
        status = 1
    # once more: `uv lock` and `ruff format` change tracked files after the first staging
    run(["git", "add", "-A"], root)

    steps = ["Read what init did (`git status`, `git diff --cached`), then commit it."]
    steps.append(
        f"Push that commit straight to `{answers.base}`, the one time anything does: the template "
        "commit is not yet your project, and a PR would show the kit's own tests as vanished to "
        "the integrity check. The first CI run compares with the root commit and should be green."
    )
    if not args.labels:
        steps.append("Create the labels: `python3 kit.py labels` (or --labels on init).")
    if not args.hooks:
        steps.append("In the development checkout only: `uv run prek install`.")
    if "\nprove:" in (root / "Makefile").read_text("utf-8"):
        steps.append("`make prove` — every gate shown red on a planted defect, on this machine.")
    steps.append(
        "Read docs/kit/SETUP.md; write the first brief with `/brief-writer` in a fresh session."
    )
    print_next_steps(answers.maintainer, steps)
    return status


def create_labels(root: Path) -> int:
    status = 0
    for name, color, description in LABELS:
        try:
            result = run(
                ["gh", "label", "create", name, "--color", color, "--description", description],
                root,
                check=False,
            )
        except Missing:
            say("gh is not installed: create the labels later with `python3 kit.py labels`")
            return 1
        if result.returncode == 0:
            say(f"label {name} created")
        elif "already exists" in result.stderr:
            say(f"label {name} exists")
        else:
            say(f"label {name}: {result.stderr.strip() or result.stdout.strip()}")
            status = 1
    return status


# ----------------------------------------------------------------------------- render (dry)


def render_command(args: argparse.Namespace) -> int:
    """Render the kit into another directory, for a look or for a test; the kit is untouched."""
    root = Path.cwd()
    if (root / LOCK).exists():
        say(f"{LOCK} exists: this is a project, not the kit; render runs in a clone of the kit")
        return 2
    answers = answers_from(args)
    if answers is None:
        return 2
    if (
        not (root / ".git").exists() or not (root / "kit.py").is_file()
    ):  # a worktree's .git is a file
        say("run render at the root of a clone of the kit (where kit.py and .git are)")
        return 2
    into = Path(args.into)
    if into.resolve() == root.resolve() or root.resolve() in into.resolve().parents:
        say(f"--into {args.into!r} is into the kit itself: render writes somewhere else")
        return 2
    into.mkdir(parents=True, exist_ok=True)
    written = render_tree(root, into, answers, tracked_files(root))
    write_lock(into, answers)
    say(f"rendered {len(written)} files into {into}")
    return 0


def labels_command(_args: argparse.Namespace) -> int:
    return create_labels(Path.cwd())


# ----------------------------------------------------------------------------- update

VERSION_TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
HALF_UPDATED = (
    "the tree is half updated; it was clean before: `git checkout -- . && git clean -fd` "
    "takes it back, then run update again"
)


class Refused(Exception):
    """A call that cannot be right; the message says why."""


def version_key(version: str) -> tuple[int, int, int] | None:
    """`0.2.0` or `v0.2.0` -> (0, 2, 0); None for anything else (a branch, a sha)."""
    match = VERSION_TAG.match(version if version.startswith("v") else f"v{version}")
    return (int(match[1]), int(match[2]), int(match[3])) if match else None


def fetch_kit(repo: str, into: Path, cwd: Path) -> str:
    """Clone the kit into `into`; a relative local path is read from `cwd` (where the user stands),
    and the repository is returned as recorded in the lock: absolute when it is a local path."""
    local = (cwd / repo).resolve()
    source = str(local) if local.exists() else repo
    result = run(["git", "clone", "--quiet", source, str(into)], cwd, check=False)
    if result.returncode != 0:
        raise Refused(f"the kit could not be fetched from {repo}: {result.stderr.strip()}")
    return source


def kit_versions(clone: Path) -> list[str]:
    """The release tags of the kit, oldest first."""
    tags = run(["git", "tag", "--list", "v*"], clone).stdout.split()
    return sorted(
        (tag for tag in tags if VERSION_TAG.match(tag)), key=lambda t: version_key(t) or (0, 0, 0)
    )


def resolve(clone: Path, ref: str) -> str:
    """The commit `ref` names in the kit, or Refused. A fresh clone has a local branch for the
    remote's HEAD only, so a branch name is tried as `origin/<ref>` too."""
    for candidate in (ref, f"origin/{ref}"):
        result = run(
            ["git", "rev-parse", "--verify", "--quiet", f"{candidate}^{{commit}}"],
            clone,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    raise Refused(f"the kit has no ref {ref!r} (a tag such as v0.2.0, a branch, or a commit)")


def is_behind(clone: Path, target: str, base: str) -> bool:
    """Whether `target` is an ancestor of `base`: moving there would go backwards in the history."""
    result = run(["git", "merge-base", "--is-ancestor", target, base], clone, check=False)
    return result.returncode == 0 and target != base


def export(clone: Path, ref: str, into: Path) -> None:
    """The kit's tree at `ref`, without its history."""
    archive = subprocess.run(
        ["git", "-C", str(clone), "archive", "--format=tar", ref], capture_output=True, check=True
    )
    into.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
        tar.extractall(into, filter="data")


def files_under(root: Path) -> list[str]:
    """Every file under `root`, repository-relative, sorted (an export has no git to ask). A `.git`
    of the tree itself is left out, not a `.git` somewhere above it."""
    return sorted(
        str(p.relative_to(root))
        for p in root.rglob("*")
        if p.is_file() and ".git" not in p.relative_to(root).parts
    )


def kit_version_of(tree: Path) -> str:
    """`KIT_VERSION` as the kit's own `kit.py` states it in that tree."""
    match = re.search(r'^KIT_VERSION = "([^"]+)"', (tree / "kit.py").read_text("utf-8"), re.M)
    return match[1] if match else "unknown"


def changelog_between(text: str, old: str, new: str) -> str:
    """The sections of CHANGELOG.md for the versions after `old` up to `new`, newest first."""
    old_key, new_key = version_key(old), version_key(new)
    sections: list[str] = []
    current: str | None = None
    for line in text.splitlines():
        heading = re.match(r"^## v?(\d+\.\d+\.\d+)\b", line)
        if line.startswith("## "):
            key = version_key(heading[1]) if heading else None
            current = line if key and old_key and new_key and old_key < key <= new_key else None
            if current is not None:
                sections.append(line)
            continue
        if current is not None:
            sections.append(line)
    return "\n".join(sections).strip()


@dataclass
class UpdatePlan:
    """What `update` does to each managed path, decided before anything is written."""

    merge: list[str] = field(default_factory=list)  # in both kits and the project: three-way
    add: list[str] = field(default_factory=list)  # new in the kit, absent from the project
    remove_clean: list[str] = field(default_factory=list)  # gone from the kit, project unchanged
    remove_kept: list[str] = field(default_factory=list)  # gone from the kit, project changed it
    missing: list[str] = field(default_factory=list)  # kit-owned, the project deleted it
    blocked_add: list[str] = field(default_factory=list)  # new in the kit, project has another
    linked: list[str] = field(default_factory=list)  # a symbolic link in the project: left alone
    unchanged: list[str] = field(default_factory=list)


def _same(a: Path, b: Path) -> bool:
    return a.read_bytes() == b.read_bytes()


def plan_update(base: Path, theirs: Path, project: Path, managed: Iterable[str]) -> UpdatePlan:
    """`base` and `theirs`: the old and the new kit, rendered with the project's answers; `managed`:
    the paths each of them owns, by its own manifest."""
    plan = UpdatePlan()
    real_root = os.path.realpath(project)
    for path in sorted(set(managed)):
        in_base, in_theirs = (base / path).is_file(), (theirs / path).is_file()
        # the path or a folder on the way is a link: a merge, add or remove would land outside
        if os.path.realpath(project / path) != os.path.join(real_root, path):
            plan.linked.append(path)
            continue
        in_project = (project / path).is_file()
        occupied = os.path.lexists(project / path)  # a directory or a link where a file would go
        if in_base and in_theirs:
            if not in_project:
                plan.missing.append(path)
            elif _same(base / path, theirs / path) or _same(theirs / path, project / path):
                plan.unchanged.append(path)
            else:
                plan.merge.append(path)
        elif in_theirs:
            if not occupied:
                plan.add.append(path)
            elif in_project and _same(theirs / path, project / path):
                plan.unchanged.append(path)
            else:
                plan.blocked_add.append(path)
        elif in_project:
            if _same(base / path, project / path):
                plan.remove_clean.append(path)
            else:
                plan.remove_kept.append(path)
        else:
            plan.unchanged.append(path)
    return plan


@dataclass
class UpdateResult:
    merged: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)


def apply_update(
    plan: UpdatePlan, base: Path, theirs: Path, project: Path, old: str, new: str
) -> UpdateResult:
    """Write what the plan says. A merge with conflicts leaves the markers in the file and counts
    it under `conflicts`: `git merge-file` exits with the number of conflicts (at most 127), which
    is not an error; its errors come back as 255 (a negative status) and stop the update."""
    result = UpdateResult()
    try:
        for path in plan.merge:
            merged = subprocess.run(
                [
                    "git",
                    "merge-file",
                    *("-L", "yours", "-L", f"kit {old}", "-L", f"kit {new}"),
                    str(project / path),
                    str(base / path),
                    str(theirs / path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if merged.returncode < 0 or merged.returncode > 127:
                raise Refused(
                    f"git merge-file could not merge {path}: {merged.stderr.strip()}; "
                    f"{HALF_UPDATED}"
                )
            (result.conflicts if merged.returncode else result.merged).append(path)
        for path in plan.add:
            (project / path).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(theirs / path, project / path)  # content and mode
            result.added.append(path)
        for path in plan.remove_clean:
            (project / path).unlink()
            result.removed.append(path)
    except OSError as error:
        raise Refused(f"{error}; {HALF_UPDATED}") from error
    return result


@dataclass
class Rules:
    """One kit version's manifest and renderer: its own `kit.py`. Each exported tree is classified
    and rendered by the kit.py it came with, so a pattern the newer kit dropped still names the
    base's file (which is then removed), and the base is rendered by the rules that rendered the
    project."""

    version: str
    is_managed: Callable[[str], bool]
    category: Callable[[str], str | None]
    render_tree: Callable[[Path, Path, Any, Iterable[str]], list[str]]
    answers: Any  # that version's `Answers`, from the lock's values it knows


def rules_of(raw: Path, answers: Answers, label: str) -> Rules:
    """The rules of the kit exported at `raw`: this module's own when its kit.py is this file,
    otherwise that kit.py loaded as a module of its own. `label` names the version to the user."""
    source = raw / "kit.py"
    if not source.is_file():
        raise Refused(f"the kit at {label} has no kit.py: not the kit")
    if _same(source, Path(__file__)):
        return Rules(KIT_VERSION, is_managed, category, render_tree, answers)
    name = "kit_" + re.sub(r"\W", "_", raw.name)
    spec = importlib.util.spec_from_file_location(name, source)
    if spec is None or spec.loader is None:
        raise Refused(f"{source} cannot be loaded as a module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # the dataclasses in it look their module up by name
    bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True  # no __pycache__ in the export: files_under() lists it
    try:
        spec.loader.exec_module(module)
        known = {f.name for f in fields(module.Answers)}
        theirs = module.Answers(**{k: v for k, v in asdict(answers).items() if k in known})
        return Rules(
            module.KIT_VERSION, module.is_managed, module.category, module.render_tree, theirs
        )
    except Exception as error:  # another version's code: whatever it raises is one sentence here
        raise Refused(f"the kit.py of the kit at {label} could not be used ({error!r})") from error
    finally:
        sys.dont_write_bytecode = bytecode


@dataclass
class Export:
    """A kit version rendered with the project's answers, and what of it the kit owns."""

    rendered: Path
    managed: list[str]


def _render_raw(raw: Path, answers: Answers, rendered: Path, label: str) -> Export:
    """Render the exported tree at `raw` into `rendered`, by its own kit.py's rules."""
    rules = rules_of(raw, answers, label)
    paths = files_under(raw)
    unknown = [p for p in paths if rules.category(p) is None]
    if unknown:
        shown = ", ".join(unknown[:5]) + ("…" if len(unknown) > 5 else "")
        say(
            f"{len(unknown)} files of the kit {rules.version} are unknown to its own kit.py: "
            f"{shown}"
        )
    written = rules.render_tree(
        raw, rendered, rules.answers, [p for p in paths if p not in unknown]
    )
    return Export(rendered, [p for p in written if rules.is_managed(p)])


def _render_export(
    clone: Path, ref: str, answers: Answers, work: Path, name: str, label: str
) -> Export:
    """The kit at `ref`, exported under `work/<name>-raw` and rendered under `work/<name>`."""
    raw = work / f"{name}-raw"
    export(clone, ref, raw)
    return _render_raw(raw, answers, work / name, label)


def _project_checks(root: Path, require_clean: bool = True) -> Lock:
    if not (root / LOCK).is_file():
        raise Refused(f"no {LOCK} here: this is not a project made by `kit.py init`")
    try:
        lock = read_lock(root)
        pyproject = toml_loads((root / "pyproject.toml").read_text("utf-8"))
        name = pyproject["project"]["name"]
    except (OSError, KeyError, ValueError) as error:  # tomllib's error is a ValueError
        raise Refused(
            f"{LOCK} or pyproject.toml cannot be read ({error}): unresolved conflict markers?"
        ) from error
    if require_clean:  # `status` needs no git at all
        state = run(["git", "status", "--porcelain"], root, check=False)
        if state.returncode != 0:
            raise Refused(f"{root} is not a git repository: update runs in the project's checkout")
        if state.stdout.strip():
            raise Refused(
                "the working tree is not clean: commit or stash first, so the update is the diff"
            )
    if name != lock.answers.package:
        raise Refused(
            f"{LOCK} says package {lock.answers.package!r}, pyproject.toml says {name!r}: the "
            "lock was edited, or the project renamed; fix the lock"
        )
    return lock


def _print_list(title: str, paths: list[str]) -> None:
    if paths:
        print(f"{title}:")
        for path in paths:
            print(f"  {path}")


def without_option(argv: list[str], name: str) -> list[str]:
    """`argv` without `name <value>` and `name=<value>`."""
    kept: list[str] = []
    skip = False
    for arg in argv:
        if skip:
            skip = False
        elif arg == name:
            skip = True
        elif not arg.startswith(name + "="):
            kept.append(arg)
    return kept


def _hand_over(
    root: Path, theirs_raw: Path, target: str, args: argparse.Namespace, clone: Path, repo: str
) -> int | None:
    """Run the target kit's `kit.py` — from the export, written nowhere — with the same arguments,
    so its manifest and rules decide the update, and `kit.py` itself arrives through the plan like
    every other kit-owned file. None when that kit.py is this file, or when this is the run handed
    over to (`--clone` marks it and brings the first run's clone). The tree is untouched either way,
    so a refusal from either run leaves it as it was."""
    if args.clone or _same(theirs_raw / "kit.py", Path(__file__)):
        return None
    say(
        f"the kit at {target} has another kit.py ({kit_version_of(theirs_raw)}); it runs this "
        "update"
    )
    done = subprocess.run(
        [
            sys.executable,
            str(theirs_raw / "kit.py"),
            "update",
            *without_option(args.argv, "--repo"),  # the resolved one goes instead
            "--repo",
            repo,
            "--clone",
            str(clone),
        ],
        cwd=root,
        check=False,
    )
    return done.returncode


def update(args: argparse.Namespace) -> int:
    root = Path.cwd()
    try:
        lock = _project_checks(root)
        if Path(tempfile.gettempdir()).resolve().is_relative_to(root.resolve()):
            raise Refused(
                "the temporary directory (TMPDIR) is inside the project: the update's working "
                "files would be in the diff; point it elsewhere"
            )
        branch = run(["git", "branch", "--show-current"], root).stdout.strip()
        if branch == lock.answers.base:
            raise Refused(
                f"on the base branch {branch!r}: update on a branch of its own, so the result "
                "is a PR"
            )
        with tempfile.TemporaryDirectory(prefix="kit-update-") as tmp:
            work = Path(tmp)
            if args.clone and Path(args.clone).is_dir():  # the clone the first run made
                clone, repo = Path(args.clone), args.repo or lock.repo
            else:
                clone = work / "kit"
                repo = fetch_kit(args.repo or lock.repo, clone, root)
            versions = kit_versions(clone)
            target = args.to or (versions[-1] if versions else None)
            if target is None:
                raise Refused("the kit has no release tag yet; pass --to <ref>")
            target_sha = resolve(clone, target)
            base_ref = args.from_ref or lock.commit or f"v{lock.version}"
            try:
                base_sha = resolve(clone, base_ref)
            except Refused as error:
                raise Refused(
                    f"{error}; the base is what this project was rendered from — pass --from <ref>"
                ) from error
            if base_sha == target_sha:
                say(f"already at {target} ({target_sha[:7]}); nothing to do")
                return 0
            if is_behind(clone, target_sha, base_sha):
                raise Refused(
                    f"the kit at {target} ({target_sha[:7]}) is behind what this project has "
                    f"({base_sha[:7]}); an update does not go backwards"
                )
            theirs_raw = work / "theirs-raw"
            export(clone, target_sha, theirs_raw)
            their_label, base_label = f"{target} ({target_sha[:7]})", f"{base_ref} ({base_sha[:7]})"
            if not (theirs_raw / "kit.py").is_file():
                raise Refused(
                    f"the kit at {their_label} has no kit.py: not the kit (--repo {repo})"
                )
            new_version = kit_version_of(theirs_raw)
            old_key, new_key = version_key(lock.version), version_key(new_version)
            if old_key and new_key and new_key < old_key:  # before the hand-over: nothing written
                raise Refused(
                    f"the kit at {target} is version {new_version}, older than the "
                    f"{lock.version} this project has"
                )
            handed = _hand_over(root, theirs_raw, target, args, clone, repo)
            if handed is not None:
                return handed
            theirs = _render_raw(theirs_raw, lock.answers, work / "theirs", their_label)
            base = _render_export(clone, base_sha, lock.answers, work, "base", base_label)
            managed = [*base.managed, *theirs.managed]
            plan = plan_update(base.rendered, theirs.rendered, root, managed)
            result = apply_update(
                plan, base.rendered, theirs.rendered, root, lock.version, new_version
            )
            write_lock(root, lock.answers, new_version, repo, target_sha)
            changelog = theirs_raw / "CHANGELOG.md"
            notes = (
                changelog_between(changelog.read_text("utf-8"), lock.version, new_version)
                if changelog.is_file()
                else ""
            )
    except Refused as error:
        say(str(error))
        return 2
    except Missing as error:
        say(f"{error.program} is not installed")
        return 2

    run(["git", "add", "-A"], root)
    came_from = (lock.commit or "v" + lock.version)[:12]
    say(
        f"updated from {lock.version} ({came_from}) to {new_version} ({target_sha[:7]}): "
        f"{len(result.merged)} merged, {len(result.conflicts)} with conflicts, "
        f"{len(result.added)} added, {len(result.removed)} removed"
    )
    _print_list("conflicts — resolve the markers, then `make check`", result.conflicts)
    _print_list(
        "kept: the kit removed these, you had changed them (delete or keep)", plan.remove_kept
    )
    _print_list("missing: kit-owned files you deleted (not recreated)", plan.missing)
    _print_list("not added: new in the kit, you have another file there", plan.blocked_add)
    _print_list(
        "not touched: symbolic links in the project (the kit's file would go through them; the "
        "link stays yours)",
        plan.linked,
    )
    if notes:
        print()
        print(notes)
        print()

    status = 1 if result.conflicts else 0
    if not args.no_sync and not run_steps(
        (["uv", "lock"], ["uv", "sync", "--all-groups"], ["make", "check"]), root
    ):
        status = 1
    run(["git", "add", "-A"], root)
    steps: list[str] = []
    if result.conflicts:
        steps.append("Resolve the conflict markers listed above; `make check`.")
    steps.append(
        "Read the diff (`git diff --cached`), commit, push; `make prove` if the project has it."
    )
    steps.append("Open the PR: it touches gate files, so `gate-guard` waits for `gates-approved`.")
    print_next_steps(lock.answers.maintainer, steps)
    return status


def status_command(args: argparse.Namespace) -> int:
    root = Path.cwd()
    try:
        lock = _project_checks(root, require_clean=False)  # a dirty tree is what status is for
        with tempfile.TemporaryDirectory(prefix="kit-status-") as tmp:
            work = Path(tmp)
            clone = work / "kit"
            fetch_kit(args.repo or lock.repo, clone, root)
            versions = kit_versions(clone)
            newest = versions[-1] if versions else "(no release tag)"
            own = lock.commit or f"v{lock.version}"
            base_ref = args.from_ref or own
            compared = f"; compared with --from {args.from_ref}" if args.from_ref else ""
            print(f"kit version: {lock.version} ({own[:12]}); newest: {newest}{compared}")
            try:
                base_sha = resolve(clone, base_ref)
            except Refused:
                if args.from_ref:  # a ref the user typed: a call that cannot be right
                    raise
                why = (
                    f"the commit {lock.commit[:12]} the lock records is not in the kit (another "
                    "repository, or a rewritten history)"
                    if lock.commit
                    else f"no tag v{lock.version} in the kit (a project made before the kit's "
                    "first release)"
                )
                print(
                    f"the kit this project took cannot be reconstructed: {why}; pass --from <ref>"
                )
                return 0
            label = f"{base_ref} ({base_sha[:7]})"
            base = _render_export(clone, base_sha, lock.answers, work, "base", label)
            changed = [
                p
                for p in base.managed
                if not (root / p).is_file() or not _same(base.rendered / p, root / p)
            ]
            _print_list("kit-owned files that differ from the kit you took", changed)
            if not changed:
                print("kit-owned files: as the kit rendered them")
    except Refused as error:
        say(str(error))
        return 2
    except Missing as error:
        say(f"{error.program} is not installed")
        return 2
    return 0


# ----------------------------------------------------------------------------- command line


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(
        prog="kit.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = top.add_subparsers(dest="command", required=True)

    def answers_options(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--package", required=True, help="the Python package name (lowercase identifier)"
        )
        p.add_argument(
            "--maintainer",
            default=PLACEHOLDER.maintainer,
            help='the human who reads briefs and merges (default: "the maintainer")',
        )
        p.add_argument(
            "--base", default=PLACEHOLDER.base, help="the branch PRs merge into (default: main)"
        )
        p.add_argument(
            "--branch-prefix",
            default=None,
            help="unit branches are <prefix>-NNN-slug (default: the base)",
        )
        p.add_argument(
            "--python",
            default=PLACEHOLDER.python,
            help="the interpreter, X.Y.Z (default: the kit's)",
        )

    p_init = sub.add_parser("init", help="render the placeholders in this clone of the kit, once")
    answers_options(p_init)
    p_init.add_argument("--labels", action="store_true", help="create the labels with gh")
    p_init.add_argument(
        "--hooks", action="store_true", help="install the git hooks (uv run prek install)"
    )
    p_init.add_argument(
        "--no-sync", action="store_true", help="skip uv lock, uv sync and make check"
    )
    p_init.set_defaults(func=init)

    p_render = sub.add_parser(
        "render", help="render the kit into another directory (the kit is untouched)"
    )
    answers_options(p_render)
    p_render.add_argument("--into", required=True, help="the directory to write")
    p_render.set_defaults(func=render_command)

    p_labels = sub.add_parser("labels", help="create the labels with gh")
    p_labels.set_defaults(func=labels_command)

    p_update = sub.add_parser(
        "update", help="take a newer kit: three-way merge the kit-owned files"
    )
    p_update.add_argument(
        "--to", default=None, help="the kit ref to move to (default: the newest release tag)"
    )
    p_update.add_argument(
        "--from",
        dest="from_ref",
        default=None,
        help="the kit ref this project was rendered from (default: the lock)",
    )
    p_update.add_argument("--repo", default=None, help="the kit repository (default: the lock)")
    p_update.add_argument(
        "--no-sync", action="store_true", help="skip uv lock, uv sync and make check"
    )
    p_update.add_argument("--clone", default=None, help=argparse.SUPPRESS)  # the hand-over's
    p_update.set_defaults(func=update)

    p_status = sub.add_parser(
        "status", help="the kit version here, the newest, and what you changed"
    )
    p_status.add_argument("--repo", default=None, help="the kit repository (default: the lock)")
    p_status.add_argument(
        "--from",
        dest="from_ref",
        default=None,
        help="the kit ref this project was rendered from (default: the lock)",
    )
    p_status.set_defaults(func=status_command)
    return top


def main(argv: list[str] | None = None) -> int:
    problem = python_version_problem(
        sys.version_info.major, sys.version_info.minor, sys.version_info.micro
    )
    if problem:
        say(problem)
        return 2
    argv = list(sys.argv[1:] if argv is None else argv)
    args = parser().parse_args(argv)
    args.argv = argv[1:]  # the subcommand's own arguments, for update's hand-over
    func: Callable[[argparse.Namespace], int] = args.func
    try:
        return func(args)
    except Missing as error:
        say(f"{error.program} is not installed")
        return 2


if __name__ == "__main__":
    sys.exit(main())
