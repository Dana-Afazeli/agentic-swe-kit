#!/usr/bin/env python3
"""agentic-swe-kit: start a project from the kit, and take the kit's updates later.

    python3 kit.py init --package NAME [--maintainer NAME] [--base BRANCH] [--branch-prefix X]
                        [--python X.Y.Z] [--labels] [--hooks] [--no-sync]
    python3 kit.py render --package NAME ... --into DIR      (what init would write, elsewhere)

Standard library only, so it runs before `uv` has made an environment. `init` runs once, in a
fresh copy of the kit ("Use this template" on GitHub, then clone): it renders the placeholders,
seeds the project-owned files, removes the kit-only ones, writes `kit.lock` (the answers and the
kit version), re-locks and runs the gate. `update` (a later version of this file) renders the kit
at the recorded version and at the new one with the same answers and three-way merges every
kit-owned file; `render()` is shared, which is what makes that merge sound.

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
import json
import keyword
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass, fields
from pathlib import Path

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
        for name in ("base", "prefix"):
            value = getattr(self, name)
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", value) or value.endswith("/"):
                problems.append(
                    f"--{name.replace('prefix', 'branch-prefix')} {value!r} is not a branch name"
                )
        if not re.fullmatch(r"\d+\.\d+\.\d+", self.python):
            problems.append(f"--python {self.python!r} is not X.Y.Z")
        if not self.maintainer.strip():
            problems.append("--maintainer is empty")
        return problems


PLACEHOLDER = Answers(
    package="kitpkg", base="main", prefix="main", maintainer="the maintainer", python="3.13.12"
)

# ----------------------------------------------------------------------------- file ownership
# Patterns match whole repository-relative paths; `*` matches across `/` (fnmatch). The first
# category that matches wins, so the more specific patterns come first. docs/kit/HARNESS.md,
# "File ownership", explains the four categories; tests/harness/test_kit.py checks that every
# tracked file falls into exactly one.

KIT_OWNED = (
    "kit.py",
    "Makefile",
    ".claude/*",
    ".github/*",
    ".pre-commit-config.yaml",
    "scripts/*",
    "tests/harness/*",
    "tests/prove/*",
    "AGENTS.md",
    ".gitignore",
    ".python-version",
    "docs/kit/*",
    "docs/briefs/000-TEMPLATE.md",
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
)
KIT_ONLY = (
    "docs/decisions/*",
    "docs/briefs/*",  # the kit's own briefs; a project starts with the template alone
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
    return re.sub(r"\b[Tt]he maintainer\b", lambda _: a.maintainer, text)


PROSE_ONLY: tuple[Rule, ...] = (_maintainer,)  # never in .py: a rename must not reformat code


def _package(text: str, a: Answers) -> str:
    text = re.sub(r"\bKITPKG(?=_|\b)", lambda _: a.package.upper(), text)  # KITPKG_EVAL_BUDGET_USD
    return re.sub(r"\bkitpkg\b", lambda _: a.package, text)


RULES: tuple[Rule, ...] = (
    _knob_line("base", _on_knob_base),
    _knob_line("prefix", _on_knob_prefix),
    _knob_line("python", _on_knob_python),
    _prefix_in_text,  # before the base: in the kit both read `main`
    _base_in_text,
    _package,
)


def render_text(path: str, text: str, answers: Answers) -> str:
    """The kit file `path` with `text`, as the project with `answers` has it."""
    if path in VERBATIM:
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


def write_lock(root: Path, answers: Answers, version: str = KIT_VERSION) -> None:
    quoted = {f.name: json.dumps(getattr(answers, f.name)) for f in fields(answers)}
    lines = [
        "# Written by `kit.py init`, rewritten by `kit.py update`. Do not edit by hand.",
        "[kit]",
        f"repo = {json.dumps(KIT_REPO)}",
        f"version = {json.dumps(version)}",
        f"date = {json.dumps(dt.date.today().isoformat())}",
        "",
        "[answers]",
        *(f"{name} = {value}" for name, value in quoted.items()),
        "",
    ]
    (root / LOCK).write_text("\n".join(lines), "utf-8")


def read_lock(root: Path) -> tuple[str, Answers]:
    import tomllib

    data = tomllib.loads((root / LOCK).read_text("utf-8"))
    answers = Answers(**{f.name: str(data["answers"][f.name]) for f in fields(Answers)})
    return str(data["kit"]["version"]), answers


# ----------------------------------------------------------------------------- git and shell


def run(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=check)


def tracked_files(root: Path) -> list[str]:
    out = run(["git", "ls-files", "-z"], root).stdout
    return sorted(path for path in out.split("\0") if path)


def say(message: str) -> None:
    print(f"kit: {message}")


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


def init(args: argparse.Namespace) -> int:
    root = Path.cwd()
    answers = Answers(
        package=args.package,
        base=args.base,
        prefix=args.branch_prefix or args.base,
        maintainer=args.maintainer,
        python=args.python,
    )
    problems = answers.validate()
    if problems:
        for problem in problems:
            say(problem)
        return 2
    if (root / LOCK).exists():
        say(f"{LOCK} exists: this project was initialised already (kit.py update takes updates)")
        return 2
    if not (root / ".git").is_dir() or not (root / "kit.py").is_file():
        say("run init at the root of a clone of the kit (where kit.py and .git are)")
        return 2
    if run(["git", "status", "--porcelain"], root).stdout.strip():
        say("the working tree is not clean: commit or stash first, so init's changes are the diff")
        return 2

    paths = tracked_files(root)
    written = render_tree(root, root, answers, paths)
    write_lock(root, answers)
    say(
        f"rendered {len(written)} files for package {answers.package!r}, base {answers.base!r}, "
        f"prefix {answers.prefix!r}, maintainer {answers.maintainer!r}, Python {answers.python}"
    )
    say(
        f"removed the kit-only files; seeded README.md, docs/DELTAS.md, docs/ROADMAP.md, "
        f"docs/FRICTION.md, docs/BACKLOG.md, docs/kit/LICENSE; wrote {LOCK}"
    )

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
        for command in commands:
            say(" ".join(command))
            if subprocess.run(command, cwd=root, check=False).returncode != 0:
                say(f"{' '.join(command)} failed: fix it, then `make check` again")
                status = 1
                break
    if args.labels:
        status = max(status, create_labels(root))
    if args.hooks:
        say("uv run prek install")
        if subprocess.run(["uv", "run", "prek", "install"], cwd=root, check=False).returncode != 0:
            status = 1

    print()
    print(f"Next steps for {answers.maintainer}:")
    print(
        "  1. Read the diff (`git status`, `git diff`), then commit it: `git add -A && git commit`."
    )
    print("  2. Push; the first CI run compares against the root commit and should be green.")
    if not args.labels:
        print("  3. Create the labels: `python3 kit.py labels` (or --labels on init).")
    if not args.hooks:
        print("  4. In the development checkout only: `uv run prek install`.")
    print("  5. `make prove` — every gate shown red on a planted defect, on this machine.")
    print("  6. Read docs/kit/SETUP.md; write the first brief from docs/briefs/000-TEMPLATE.md.")
    return status


def create_labels(root: Path) -> int:
    status = 0
    for name, color, description in LABELS:
        result = run(
            ["gh", "label", "create", name, "--color", color, "--description", description],
            root,
            check=False,
        )
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
    answers = Answers(
        package=args.package,
        base=args.base,
        prefix=args.branch_prefix or args.base,
        maintainer=args.maintainer,
        python=args.python,
    )
    problems = answers.validate()
    if problems:
        for problem in problems:
            say(problem)
        return 2
    into = Path(args.into)
    into.mkdir(parents=True, exist_ok=True)
    written = render_tree(root, into, answers, tracked_files(root))
    write_lock(into, answers)
    say(f"rendered {len(written)} files into {into}")
    return 0


def labels_command(_args: argparse.Namespace) -> int:
    return create_labels(Path.cwd())


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
    p_init.add_argument("--labels", action="store_true", help="create the three labels with gh")
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

    p_labels = sub.add_parser("labels", help="create the three labels with gh")
    p_labels.set_defaults(func=labels_command)
    return top


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    func: Callable[[argparse.Namespace], int] = args.func
    return func(args)


if __name__ == "__main__":
    sys.exit(main())
