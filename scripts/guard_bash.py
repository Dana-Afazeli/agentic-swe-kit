"""PreToolUse guard for the Bash tool (brief 002): refuse the few commands that must not run.

Claude Code passes the hook's JSON on stdin. Exit 2 with a one-line reason on stderr refuses the
command; exit 0 leaves it to the normal permission flow.

Refused:
  rm          a target git tracks, or inside .git; with -r/-f, a target outside the repository
              (the OS temp directories excepted); any target the guard cannot resolve
  gate files  a write from the shell — the editor asks the maintainer, the shell would not. A tool's
              own config file (pytest.ini, ruff.toml, pyrightconfig.json, GNUmakefile, …) is one:
              it would override pyproject.toml or the Makefile. After a cd, a
              relative target is judged from every directory the shell was in: a cd can fail,
              end with its subshell, or never be reached
  git commit  --no-verify, -n
  git push    --force, -f, --force-with-lease, +refspec; any push that lands on main
  gh          adding or removing labels; `gh api` writes other than PR comments and reviews,
              and any GraphQL mutation other than `resolveReviewThread`; `gh alias set`

Not a wall. `find -delete`, `find -exec`, `git rm`, `rmdir`, `git clean`, `dd`, `ln -sf`, a
script file (also one that calls gh), a script piped into a shell or given to it as a
here-string (`bash <<< '…'`), an interpreter other than python, a variable that expands to a
gate file or to a command's name, `core.hooksPath` (`git -c`, `git config`) or `SKIP=` in front
of a commit, a write into `.git/hooks`: none of these is inspected. The guard stops the
habitual spellings early; CI (`gate-guard`, `integrity`) and the maintainer's read of the diff are
the wall. If the guard itself fails, the command is refused.

The command line is read in one pass, the way the shell reads it (`_Reader`): quotes, comments,
`$( … )`, backticks, `$(( … ))`, here-documents. A command substitution — also inside double
quotes or an unquoted here-document — is judged as a command line of its own. What the reader
cannot read the way the shell does is refused: an unbalanced quote, a `case` inside `$( … )`,
a `"` inside `"${ … }"`, a `<<` inside `(( … ))`, zsh's `${(e)…}`.

"The shell" is the user's: Claude Code runs the Bash tool through it, with its aliases, functions
and options (docs/kit/research/2026-10-03-claude-code-hooks.md): zsh on a Mac, bash on CI. So the
guard also steps over zsh's words in front of a command (`noglob`, `repeat N`, `=rm`, a short
`if [[ … ]] rm x`) and knows zsh's redirections (`>!`). tests/test_guard_bash.py asks each shell
that is installed whether it and the guard agree. Unseen, as above: an alias or a function from
the startup file, a script made on the fly and sourced (`source =(…)`, `. <(…)`), a glob
qualifier that runs code (`*(e:'…':)`).

The reader holds against habit, not against a search. The tests ask the shells about the lines
someone has thought of; a review that went looking (PR #5, round 8) found ten more that hide a
command — a `#` or a `<<` inside `${ … }`, zsh's `{ … } always { … }` and `else { … }` — and
zsh's glob groups, `Makefil(e|x)`, which the reader takes for a subshell. docs/BACKLOG.md lists
them, with what would end the class: a real shell parser.
"""

import fnmatch
import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import IO, cast

ROOT = Path(__file__).resolve().parents[1]

# A tool that `make check` runs reads each of these before, or instead of, pyproject.toml or the
# Makefile. None exists here — all configuration is in pyproject.toml — and one that appears
# can lower a threshold without touching a file the maintainer is asked about. So they are gate
# files.
CONFIG_OVERRIDES = frozenset(
    {
        *("GNUmakefile", "makefile"),  # GNU make
        *("pytest.toml", ".pytest.toml", "pytest.ini", ".pytest.ini"),  # pytest
        *("ruff.toml", ".ruff.toml"),  # ruff
        "pyrightconfig.json",  # basedpyright
        *(".coveragerc", ".coveragerc.toml"),  # coverage
        ".importlinter",  # import-linter
        *("setup.cfg", "tox.ini"),  # coverage, import-linter, mutmut; pytest without the above
        "uv.toml",  # uv
    }
)
# Keep in step with the grep in .github/workflows/ci.yml (job gate-guard).
GATE_FILES = CONFIG_OVERRIDES | {
    "Makefile",
    "pyproject.toml",
    ".pre-commit-config.yaml",
    ".python-version",
    ".gitignore",
    "uv.lock",
    ".betterleaks.toml",
    ".betterleaksignore",
    "kit.py",  # rewrites the files above when it applies a kit update
}
GATE_DIRS = frozenset({".claude", ".github", "scripts"})
# `uv add|remove|lock|sync` rewrite pyproject.toml and uv.lock by design. They are exempt simply
# by not being in the list of writers below.

GATE_MESSAGE = "gate file — use the editor so the maintainer sees the diff"
GATE_AFTER_CD_MESSAGE = (
    "gate file, if the cd earlier in this command does not last (it can fail, or end with its "
    "subshell) — use the editor; for a file in another directory, give its absolute path"
)
LABEL_MESSAGE = "labels are the maintainer's"


@dataclass(frozen=True)
class RepoContext:
    """What the guard knows about the repository. `cwd` is where the shell is (default: root)."""

    root: Path
    is_tracked: Callable[[Path], bool]
    tmp_dirs: tuple[Path, ...]
    cwd: Path | None = None


@dataclass
class _Command:
    argv: list[str]
    writes: list[str]  # the targets of its output redirections
    heredocs: list[int]  # the numbers of the here-documents it reads
    depth: int = 0  # how many `( … )` it sits inside


@dataclass
class _Shell:
    cwd: Path
    # Where the shell was before each cd earlier in the command line. It may still be there: a
    # cd can fail (`cd /nowhere; …`), be undone (`cd -`) or never be reached (`false && cd …`).
    earlier: tuple[Path, ...] = ()


# ---------------------------------------------------------------------------- reading the line

# Longest first. The ones that end in `!` or a second `|` are zsh's: write whatever `noclobber`.
_OPERATORS = (
    *("&>>|", "&>>!", "&>>", "<<<", ">>|", ">>!", "&>|", "&>!", ">&|", ">&!"),
    *("&&", "||", ">>", "&>", ">&", ">|", ">!", "<<", "<&", "<>", ";;", "|&"),
    *(";", "|", "&", "<", ">"),
)
_WRITES = frozenset(
    {
        *(">", ">>", "&>", "&>>", ">|", ">&", "<>"),
        *(">!", ">>|", ">>!", "&>|", "&>!", ">&|", ">&!", "&>>|", "&>>!"),
    }
)
_READS = frozenset({"<", "<<", "<<<", "<&"})
_WORD_ENDS = ("", " ", "\t", "\n", ";", "&", "|", "<", ">", "(", ")")
# A here-document's delimiter: quoted, and its body is data; or bare, and its body is expanded.
# Only what ends a word for the shell ends it here: `<<X` + a carriage return is the word `X\r`.
_DELIMITER = re.compile(
    r"""'([^'\n]+)'|"([^"\\$`\n]+)"|\\([^ \t\n;&|<>()'"\\$`]+)|([^ \t\n;&|<>()'"\\$`]+)"""
)
_SUBSTITUTION = "$()"  # what a word shows where a command substitution or arithmetic stood


@dataclass(frozen=True)
class _Token:
    kind: str  # "word", "operator", or "heredoc" — then `text` is the here-document's number
    text: str


class _Reader:
    """One pass over a command line, reading it the way the shell does.

    Quotes (also `$'…'`), escapes, comments, `$( … )`, backticks, `$(( … ))` and here-documents
    are read where they stand, so that what is a command to the shell is a command here: a `#`
    or a `<<X` inside quotes is text, and a quote inside `"$( … )"` belongs to the substitution.

    `tokens` are the words (quotes removed) and operators outside any substitution. Each
    substitution is kept whole in `substitutions`: a command line of its own, to be read again.
    `bodies` are the here-documents. What cannot be read the way the shell reads it raises
    ValueError, and the command is refused.
    """

    def __init__(self, text: str, start: int = 0, *, nested: bool = False) -> None:
        self.text = text
        self.pos = start
        self.nested = nested  # reading the inside of a `$( … )`, up to its `)`
        self.tokens: list[_Token] = []
        self.bodies: list[str] = []
        self.substitutions: list[str] = []
        self.word: list[str] | None = None
        self.bare = True  # the word being read has no quoted part
        self.dollar = False  # the word being read ends in an unquoted `$`
        self.pending: list[tuple[int, str, bool, bool]] = []  # here-documents awaiting bodies

    def peek(self, offset: int = 0) -> str:
        index = self.pos + offset
        return self.text[index] if index < len(self.text) else ""

    def add(self, text: str, *, quoted: bool = True) -> None:
        if self.word is None:
            self.word, self.bare = [], True
        self.word.append(text)
        self.bare = self.bare and not quoted
        self.dollar = text == "$" and not quoted

    def end_word(self) -> None:
        if self.word is None:
            return
        word = "".join(self.word)
        if self.nested and self.bare and word == "case":
            raise ValueError("a `case` inside $( … ): its `)` cannot be told from the closing one")
        self.tokens.append(_Token("word", word))
        self.word = None

    def emit(self, operator: str) -> None:
        self.end_word()
        self.tokens.append(_Token("operator", operator))

    def refuse_evaluating_flags(self) -> None:
        """At a `${(`: zsh's flag `e` runs the value's `$( … )` again, quoted or not."""
        flags = self.text[self.pos + 3 : self.pos + 40].partition(")")[0]
        if self.text.startswith("${(", self.pos) and "e" in flags:
            raise ValueError("zsh's `${(e)…}` reads its value again, as a command line would be")

    def read(self) -> None:
        """Read command text to the end — or, when nested, to the `)` that closes the `$(`."""
        depth = 0  # of the `( … )` opened here
        arithmetic: int | None = None  # the depth at which a `((` without a `$` opened
        while self.pos < len(self.text):
            char, following = self.peek(), self.peek(1)
            if char == "\\":
                if following != "\n":  # a backslash-newline joins two lines
                    self.add(following)
                self.pos += 2
            elif char in "'\"":
                ansi = self.dollar  # `$'…'`, `$"…"`: the `$` is part of the quote
                if ansi and self.word:
                    self.word.pop()
                self.add("")  # an empty string is a word too
                self.pos += 1
                if char == '"':
                    self.double_quoted()
                else:
                    self.single_quoted(ansi=ansi)
            elif char == "`":
                self.pos += 1
                self.backticks(in_double_quotes=False)
            elif char == "$" and following == "(":
                self.substitution()
            elif char in " \t":  # the shell's only blanks: a carriage return is a character
                self.end_word()
                self.pos += 1
            elif char == "#" and self.word is None:  # a comment, to the end of the line
                end = self.text.find("\n", self.pos)
                self.pos = len(self.text) if end == -1 else end
            elif char == "\n":
                self.emit("\n")
                self.pos += 1
                self.read_bodies()
            elif char == "(":
                if following == "(" and arithmetic is None:
                    arithmetic = depth
                depth += 1
                self.emit("(")
                self.pos += 1
            elif char == ")":
                if self.nested and depth == 0:
                    self.end_word()
                    self.pos += 1
                    return
                depth = max(depth - 1, 0)  # a `)` with no `(` is a `case` pattern
                if arithmetic is not None and depth <= arithmetic:
                    arithmetic = None
                self.emit(")")
                self.pos += 1
            elif char in ";&|<>":
                operator = next(each for each in _OPERATORS if self.text.startswith(each, self.pos))
                self.emit(operator)
                self.pos += len(operator)
                if operator == "<<":
                    if arithmetic is not None:
                        raise ValueError("`<<` inside (( … )): a shift, or a here-document?")
                    self.heredoc()
            else:
                self.refuse_evaluating_flags()
                self.add(char, quoted=False)
                self.pos += 1
        if self.nested:
            raise ValueError("no closing `)` for a `$(`")
        self.end_word()

    def single_quoted(self, *, ansi: bool) -> None:
        """Read to the closing quote. Only in `$'…'` does a backslash escape, the quote included."""
        while self.pos < len(self.text):
            char = self.peek()
            if ansi and char == "\\":
                self.add(self.peek(1))
                self.pos += 2
            elif char == "'":
                self.pos += 1
                return
            else:
                self.add(char)
                self.pos += 1
        raise ValueError("no closing quotation")

    def double_quoted(self, closer: str = '"') -> None:
        """Read to the closing quote: text, except that substitutions run in here.

        With no `closer` the text is the body of an unquoted here-document, where the same holds
        to the end and a `"` is a plain character.
        """
        braces = 0  # of the `${ … }` open
        while self.pos < len(self.text):
            char, following = self.peek(), self.peek(1)
            if char == "\\":
                if following != "\n":
                    self.add(following if following in '$`"\\' else char + following)
                self.pos += 2
            elif char == closer:
                if braces:  # the shell opens a new string there; where it ends is beyond this
                    raise ValueError('a `"` inside "${ … }"')
                self.pos += 1
                return
            elif char == "`":
                self.pos += 1
                self.backticks(in_double_quotes=True)
            elif char == "$" and following == "(":
                self.substitution()
            else:
                self.refuse_evaluating_flags()
                braces += (char == "$" and following == "{") - (char == "}" and braces > 0)
                self.add(char)
                self.pos += 1
        if closer:
            raise ValueError("no closing quotation")

    def substitution(self) -> None:
        """At a `$(`: keep the command line inside it, to its own `)`, for a reading of its own."""
        if self.peek(2) == "(":
            self.arithmetic()
            return
        start = self.pos + 2
        inside = _Reader(self.text, start, nested=True)
        inside.read()
        self.substitutions.append(self.text[start : inside.pos - 1])
        self.pos = inside.pos
        self.add(_SUBSTITUTION)

    def arithmetic(self) -> None:
        """At a `$((`: skip to its `))`. A `<<` in here is a shift; a substitution still runs."""
        self.pos += 3
        depth = 0
        while self.pos < len(self.text):
            char = self.peek()
            if char in "'\"":
                raise ValueError("a quote inside $(( … ))")
            if char == "`":
                self.pos += 1
                self.backticks(in_double_quotes=False)
            elif char == "$" and self.peek(1) == "(":
                self.substitution()
            elif char == ")" and depth == 0:
                if self.peek(1) != ")":  # then it was `$( ( … ) … )` all along
                    raise ValueError("a `$((` that a single `)` closes")
                self.pos += 2
                self.add(_SUBSTITUTION)
                return
            else:
                depth += (char == "(") - (char == ")")
                self.pos += 1
        raise ValueError("no closing `))` for a `$((`")

    def backticks(self, *, in_double_quotes: bool) -> None:
        """After a backtick: keep the command line up to the next one that is not escaped."""
        escapable = '$`\\"' if in_double_quotes else "$`\\"
        inside: list[str] = []
        while self.pos < len(self.text):
            char, following = self.peek(), self.peek(1)
            if char == "\\" and following and following in escapable:
                inside.append(following)
                self.pos += 2
            elif char == "`":
                self.pos += 1
                self.substitutions.append("".join(inside))
                self.add(_SUBSTITUTION)
                return
            else:
                inside.append(char)
                self.pos += 1
        raise ValueError("no closing backtick")

    def heredoc(self) -> None:
        """After a `<<`: note the delimiter. The body starts after the next newline."""
        strip_tabs = self.peek() == "-"
        self.pos += strip_tabs
        while self.peek() in (" ", "\t"):
            self.pos += 1
        match = _DELIMITER.match(self.text, self.pos)
        if match is None or self.text[match.end() : match.end() + 1] not in _WORD_ENDS:
            raise ValueError("a here-document whose delimiter is more than one plain word")
        self.pos = match.end()
        delimiter = next(group for group in match.groups() if group)
        number = len(self.bodies)
        self.bodies.append("")
        self.pending.append((number, delimiter, strip_tabs, match.group(4) is not None))
        self.tokens.append(_Token("heredoc", str(number)))

    def read_bodies(self) -> None:
        """After a newline: the bodies of the here-documents opened on the line before it."""
        for number, delimiter, strip_tabs, expanded in self.pending:
            lines: list[str] = []
            while self.pos < len(self.text):
                end = self.text.find("\n", self.pos)
                end = len(self.text) if end == -1 else end
                line = self.text[self.pos : end]
                self.pos = min(end + 1, len(self.text))
                if (line.lstrip("\t") if strip_tabs else line) == delimiter:
                    break
                lines.append(line)
            self.bodies[number] = "\n".join(lines)
            if expanded:  # a bare delimiter: `$( … )` and backticks in the body run
                body = _Reader(self.bodies[number])
                body.double_quoted(closer="")
                self.substitutions += body.substitutions
        self.pending.clear()


def _commands(tokens: list[_Token]) -> list[_Command]:
    """The simple commands in a command line, redirections taken out of their arguments."""
    commands = [_Command([], [], [])]
    redirect: str | None = None
    for token in tokens:
        if token.kind == "heredoc":
            commands[-1].heredocs.append(int(token.text))
            redirect = None
        elif token.kind == "word":
            if redirect is None:
                commands[-1].argv.append(token.text)
            elif redirect in _WRITES:  # `2>&1` lists "1": harmless, no gate file is a number
                commands[-1].writes.append(token.text)
            redirect = None
        elif token.text in _WRITES or token.text in _READS:
            redirect = token.text
            argv = commands[-1].argv
            if argv and argv[-1].isdigit():  # `2>file`: the 2 is a file descriptor
                argv.pop()
        else:
            # through a pipe the here-documents travel on: `cat <<EOF | sh`
            piped = commands[-1].heredocs if token.text in ("|", "|&") else []
            # a `)` with no `(` before it closes nothing: it is a `case` pattern
            depth = max(commands[-1].depth + (token.text == "(") - (token.text == ")"), 0)
            commands.append(_Command([], [], list(piped), depth))
            redirect = None
    return commands


_ASSIGNMENT = re.compile(r"[A-Za-z_]\w*=.*", re.DOTALL)
_NO_OPTIONS: tuple[frozenset[str], int] = (frozenset(), 0)
# wrapper -> (its options that take a value, positional arguments before the wrapped command)
_WRAPPERS: dict[str, tuple[frozenset[str], int]] = {
    "sudo": (frozenset({"-u", "-g", "-h", "-p", "-C", "-D", "-R", "-T", "-U"}), 0),
    "env": (frozenset({"-u", "-C"}), 0),
    "command": _NO_OPTIONS,
    "builtin": _NO_OPTIONS,
    "exec": (frozenset({"-a"}), 0),
    "nohup": _NO_OPTIONS,
    "time": _NO_OPTIONS,
    "nice": (frozenset({"-n"}), 0),
    "timeout": (frozenset({"-k", "-s"}), 1),
    "xargs": (frozenset({"-n", "-I", "-P", "-L", "-s", "-d", "-E", "-a", "-J", "-R"}), 0),
    # shell keywords that sit in front of a command: `do rm -rf x`, `then …`, `! …`, `{ …`
    **dict.fromkeys(("if", "then", "elif", "else", "while", "until", "do", "!", "{"), _NO_OPTIONS),
    "function": (frozenset(), 1),  # `function f { rm -rf x; }`: the name, then the body
    # zsh's own: words in front of a command, and `repeat N command`
    **dict.fromkeys(("noglob", "nocorrect", "coproc", "-"), _NO_OPTIONS),
    "repeat": (frozenset(), 1),
}
_UV_RUN_VALUE_OPTIONS = frozenset(
    {
        *("--with", "--with-editable", "--with-requirements", "-w", "-p", "--python"),
        *("--group", "--only-group", "--no-group", "--extra", "--no-extra", "--package"),
        *("--project", "--directory", "--env-file", "--index", "--default-index"),
        *("--config-file", "--cache-dir", "--color", "--python-preference"),
    }
)


def _past_options(args: list[str], value_options: frozenset[str]) -> list[str]:
    """`args` from the first word that is not an option (nor the value of one)."""
    index = 0
    while index < len(args) and args[index].startswith("-"):
        index += 2 if args[index] in value_options else 1
    return args[index:]


def _unwrap(argv: list[str]) -> tuple[list[str], bool]:
    """The command that really runs, past `VAR=value` and wrappers; and whether xargs feeds it."""
    from_stdin = False
    while argv:
        name = Path(argv[0]).name
        if _ASSIGNMENT.fullmatch(argv[0]):
            argv = argv[1:]
        elif argv[:2] == ["uv", "run"]:
            argv = _past_options(argv[2:], _UV_RUN_VALUE_OPTIONS)
        elif argv[0] == "[[" and "]]" in argv:  # zsh: `if [[ … ]] rm x`, with no `then`
            argv = argv[argv.index("]]") + 1 :]
        elif argv[0].startswith("=") and len(argv[0]) > 1:  # zsh: `=rm` is the path of rm
            argv = [argv[0][1:], *argv[1:]]
        elif name in _WRAPPERS:
            value_options, positionals = _WRAPPERS[name]
            from_stdin = from_stdin or name == "xargs"
            argv = _past_options(argv[1:], value_options)[positionals:]
        else:
            break
    return argv, from_stdin


def _operands(args: list[str]) -> list[str]:
    """The arguments that are not options (no gate file starts with a dash)."""
    return [arg for arg in args if not arg.startswith("-")]


def _has_flag(args: list[str], letter: str, take_a_value: str) -> bool:
    """Whether a short-option cluster such as `-Ei` carries `letter`."""
    for arg in args:
        if arg.startswith("-") and not arg.startswith("--"):
            for char in arg[1:]:
                if char == letter:
                    return True
                if char in take_a_value:  # the rest of the cluster is that option's value
                    break
    return False


_PYTHON_VALUE_OPTIONS = frozenset({"-W", "-X", "--check-hash-based-pycs"})
_SHELL_VALUE_OPTIONS = frozenset({"-o", "-O", "+o", "+O", "--rcfile", "--init-file"})


def _shell_code(args: list[str]) -> str | None:
    """The command string of `sh -c`: the first operand, when an option cluster holds a c.

    `sh -ce '…'`, `bash -c -x '…'` and `bash -lc '…'` all run the string. Only the shell's own
    options count: in `bash run.sh -c x` the -c belongs to the script.
    """
    has_c = False
    index = 0
    while index < len(args) and args[index].startswith(("-", "+")) and args[index] != "-":
        arg = args[index]
        has_c = has_c or (arg.startswith("-") and not arg.startswith("--") and "c" in arg)
        index += 2 if arg in _SHELL_VALUE_OPTIONS else 1
    return args[index] if has_c and index < len(args) else None


def _python_code(args: list[str]) -> str | None:
    """The program of `python -c`: the rest of the word after the c, or the next word.

    Only python's own options count: in `python -m pytest -c pyproject.toml` the -c is pytest's.
    """
    index = 0
    while index < len(args) and args[index].startswith("-") and args[index] != "-":
        arg = args[index]
        if not arg.startswith("--") and arg[1] not in "WX":  # -Wonce: the rest is -W's value
            for position, char in enumerate(arg[1:], start=1):
                if char == "c":
                    following = args[index + 1 : index + 2]
                    return arg[position + 1 :] or (following[0] if following else None)
                if char == "m":
                    return None
        index += 2 if arg in _PYTHON_VALUE_OPTIONS else 1
    return None


# ---------------------------------------------------------------------------- paths


def _expand(word: str, cwd: Path) -> Path | None:
    """The absolute path a shell word names in `cwd`, or None when only the shell could tell."""
    if word == "~" or word.startswith("~/"):
        return Path.home() / word[2:]
    if word.startswith("~") or "$" in word or "`" in word:
        return None
    return cwd / word


def _locations(path: Path) -> tuple[Path, Path]:
    """Where a path really is: the directory entry, and what it leads to through symlinks."""
    lexical = Path(os.path.normpath(path))
    return lexical.parent.resolve() / lexical.name, lexical.resolve()


def _relative(path: Path, base: Path) -> Path | None:
    try:
        return path.relative_to(base)
    except ValueError:
        return None


def _is_gate(word: str, ctx: RepoContext, cwd: Path) -> bool:
    """Whether a shell word, read in `cwd`, names a gate file or a glob that can match one."""
    path = _expand(word, cwd)
    if path is None:
        return False
    is_glob = any(char in word for char in "*?[")
    for location in _locations(path):
        inside = _relative(location, ctx.root.resolve())
        if inside is None or not inside.parts:
            continue
        # Compared without case: on a case-insensitive file system `makefile` is the Makefile.
        top, name = inside.parts[0].casefold(), inside.as_posix().casefold()
        if top in GATE_DIRS or name in {gate.casefold() for gate in GATE_FILES}:
            return True
        if is_glob and (
            any(fnmatch.fnmatch(gate.casefold(), name) for gate in GATE_FILES)
            or any(fnmatch.fnmatch(directory, top) for directory in GATE_DIRS)
        ):
            return True
    return False


_BRACES = re.compile(r"\{([^{}]*)\}")
_KEPT_BRACES = str.maketrans("\x00\x01", "{}")


_MOST_EXPANSIONS = 64


def expand_braces(word: str) -> list[str]:
    """The words the shell makes of `Makefil{e,}`, in the shell's order.

    A range, `{a..z}`, becomes a `*`. And so does every group of a word that would make more
    than a few dozen words: eight groups of ten options are 10**8, in a hook that runs before
    every Bash call. The one glob that comes back can only match more than the words would.
    """
    done: list[str] = []
    todo = [word]
    while todo:
        if len(done) + len(todo) > _MOST_EXPANSIONS:
            glob = word
            while _BRACES.search(glob):
                glob = _BRACES.sub("*", glob)
            return [glob]
        current = todo.pop(0)
        match = _BRACES.search(current)  # the first of the innermost groups
        if match is None:
            done.append(current.translate(_KEPT_BRACES))
            continue
        inside = match[1]
        if "," in inside:
            options = inside.split(",")
        else:  # `{x}` expands to nothing else: keep it, out of the next search's way
            options = ["*"] if ".." in inside else [f"\x00{inside}\x01"]
        before, after = current[: match.start()], current[match.end() :]
        todo[:0] = [f"{before}{option}{after}" for option in options]
    return done


def _gate_write(words: list[str], ctx: RepoContext, shell: _Shell) -> str | None:
    """The reason to refuse a write to `words`: one is a gate file where the shell is, or was."""
    words = [expanded for word in words for expanded in expand_braces(word)]
    if any(_is_gate(word, ctx, shell.cwd) for word in words):
        return GATE_MESSAGE
    if any(_is_gate(word, ctx, cwd) for word in words for cwd in shell.earlier):
        return GATE_AFTER_CD_MESSAGE
    return None


def _names_gate(code: str) -> bool:
    """Whether a program's text names a gate file — in any case, as `_is_gate` compares."""
    code = code.casefold()
    return any(name.casefold() in code for name in GATE_FILES) or any(
        f"{directory}/" in code for directory in GATE_DIRS
    )


# ---------------------------------------------------------------------------- the rules


def _check_rm(args: list[str], ctx: RepoContext, shell: _Shell, from_stdin: bool) -> str | None:
    recursive_or_forced = False
    targets: list[str] = []
    for index, arg in enumerate(args):
        if arg == "--":
            targets += args[index + 1 :]
            break
        if arg.startswith("--"):
            recursive_or_forced = recursive_or_forced or arg in ("--recursive", "--force")
        elif arg.startswith("-") and arg != "-":
            recursive_or_forced = recursive_or_forced or any(flag in arg for flag in "rRf")
        else:
            targets.append(arg)
    if from_stdin:
        return "rm refused: cannot resolve targets that arrive through xargs — name them"
    root = ctx.root.resolve()
    tmp_dirs = [tmp.resolve() for tmp in ctx.tmp_dirs]
    for target in targets:
        path = _expand(target, shell.cwd)
        after_cd = bool(shell.earlier) and not target.startswith(("/", "~"))
        if path is None or after_cd or any(char in target for char in "*?[{"):
            return (
                f"rm refused: cannot resolve {target!r} (a variable, a glob, or a path relative "
                "to an earlier cd) — name the path literally, from the repository root"
            )
        for location in _locations(path):
            inside = _relative(location, root)
            if inside is None:
                in_tmp = any(tmp in location.parents for tmp in tmp_dirs)
                if recursive_or_forced and not in_tmp:
                    return (
                        f"rm refused: {target!r} is outside the repository "
                        "(rm -r/-f reaches only the repository and the temp directory)"
                    )
            elif inside.parts and inside.parts[0].casefold() == ".git":  # `.GIT` is the same
                return f"rm refused: {target!r} is inside .git"
            elif ctx.is_tracked(location):
                return (
                    f"rm refused: {target!r} is tracked by git — "
                    "a deletion belongs in a commit (git rm), where the maintainer sees it"
                )
    return None


def _copied(name: str, args: list[str], operands: list[str]) -> list[str]:
    """What cp, mv or install write: the destination, the files landing in it, and mv's sources."""
    directory: str | None = None
    for index, arg in enumerate(args[:-1]):
        if arg in ("-t", "--target-directory"):
            directory = args[index + 1]
    for arg in args:
        if arg.startswith("--target-directory="):
            directory = arg.partition("=")[2]
    if directory is not None:
        sources, destination = [word for word in operands if word != directory], directory
    elif len(operands) >= 2:
        *sources, destination = operands
    else:
        return []
    written = [destination, *(f"{destination}/{Path(source).name}" for source in sources)]
    return written + sources if name == "mv" else written


_WRITERS = frozenset({"tee", "truncate", "sed", "perl", "cp", "mv", "install"})


def _written(name: str, args: list[str]) -> list[str]:
    """The words a command writes to — for the writers brief 002 lists, nothing for the rest."""
    if name not in _WRITERS:  # nothing to judge, so nothing to expand
        return []
    args = [expanded for arg in args for expanded in expand_braces(arg)]  # `mv Makefile{,.old}`
    operands = _operands(args)
    if name in ("tee", "truncate"):
        return operands
    if name == "sed":
        in_place = _has_flag(args, "i", "ef") or any(a.startswith("--in-place") for a in args)
        return operands if in_place else []
    if name == "perl":
        return operands if _has_flag(args, "i", "eEMmIFxCDV") else []
    if name in ("cp", "mv", "install"):
        return _copied(name, args, operands)
    return []


_GIT_VALUE_OPTIONS = frozenset(
    {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--config-env"}
)
_COMMIT_VALUE_OPTIONS = frozenset(
    {
        *("--message", "--file", "--author", "--date", "--template", "--reuse-message"),
        *("--reedit-message", "--fixup", "--squash", "--cleanup", "--trailer"),
        "--pathspec-from-file",
    }
)


def _skips_hooks(args: list[str]) -> bool:
    """Whether `git commit <args>` carries --no-verify or -n as a flag, not as an option's value."""
    is_value = False
    for arg in args:
        if is_value:
            is_value = False
        elif arg == "--":
            break
        elif len(arg) >= len("--no-veri") and "--no-verify".startswith(arg):  # git takes prefixes
            return True
        elif arg in _COMMIT_VALUE_OPTIONS:
            is_value = True
        elif arg.startswith("-") and not arg.startswith("--"):
            for position, char in enumerate(arg[1:], start=1):
                if char == "n":
                    return True
                if char in "uS":  # their value, when given, is attached: -uno
                    break
                if char in "mFCct":  # their value is the rest of the cluster, or the next word
                    is_value = position == len(arg) - 1
                    break
    return False


def _forces(args: list[str]) -> bool:
    # --force-if-includes forces nothing by itself: it only narrows --force-with-lease
    return any(
        arg == "--force"
        or arg.startswith(("--force-w", "+"))
        or (arg.startswith("-") and not arg.startswith("--") and "f" in arg)
        for arg in args
    )


BASE_BRANCH = "main"  # knob: base
# The branches that change only through a merged PR: the base, and the default branch if it differs.
_BASE_BRANCHES = frozenset({BASE_BRANCH, "main"})


def _lands_on_base(args: list[str]) -> bool:
    """Whether `git push <args>` can move a base branch: a refspec ending there, or all branches."""
    # git takes a shortened option: `--al`, `--mir`. Three characters is the least it accepts.
    if any(
        len(arg) > 2 and option.startswith(arg)
        for arg in args
        for option in ("--all", "--branches", "--mirror")
    ):
        return True
    refspecs = [arg for arg in args if not arg.startswith("-")][1:]  # the first word is the remote
    # git resolves `x`, `heads/x` and `refs/heads/x` to the same branch; a `*` names them all
    destinations = (
        spec.rpartition(":")[2].removeprefix("refs/").removeprefix("heads/") for spec in refspecs
    )
    return any(
        fnmatch.fnmatchcase(base, destination)
        for destination in destinations
        for base in _BASE_BRANCHES
    )


def _check_git(args: list[str]) -> str | None:
    match _past_options(args, _GIT_VALUE_OPTIONS):
        case ["commit", *rest] if _skips_hooks(rest):
            return "git commit --no-verify refused: the pre-commit hook is the gate (make check)"
        case ["push", *rest] if _forces(rest):
            return "git push refused: no force-push, in any spelling (--force, -f, +refspec)"
        case ["push", *rest] if _lands_on_base(rest):
            return (
                f"git push refused: {' and '.join(sorted(_BASE_BRANCHES))} change only through "
                "a PR that the maintainer merges"
            )
        case _:
            return None


_GH_API_VALUE_OPTIONS = frozenset(
    {
        *("-X", "--method", "-f", "-F", "--field", "--raw-field", "--input", "-H", "--header"),
        *("-q", "--jq", "-t", "--template", "--hostname", "-p", "--preview", "--cache"),
    }
)
_GH_API_BODY_OPTIONS = ("-f", "-F", "--field", "--raw-field", "--input")
# What the review workflow needs to write: a comment on the PR, a reply to a review comment, and
# a review (one call that carries its inline comments). None of the three can carry a label.
_GH_API_COMMENTS = re.compile(
    r"/?repos/[^/]+/[^/]+/(?:issues/\d+/comments|pulls/\d+/(?:comments(?:/\d+/replies)?|reviews))"
)
# The one mutation that passes, matched in full so that nothing can ride along with it: one or
# more `resolveReviewThread` calls, each with a literal thread ID. No variables, no other field.
_RESOLVE_THREAD = (
    r"\s*(?:\w+\s*:\s*)?resolveReviewThread\s*"
    r'\(\s*input\s*:\s*\{\s*threadId\s*:\s*"[\w=-]+"\s*\}\s*\)\s*'
    r"\{\s*thread\s*\{\s*(?:id|isResolved)(?:\s+(?:id|isResolved))*\s*\}\s*\}\s*"
)
_RESOLVE_THREADS = re.compile(rf"query=\s*mutation\s*\{{(?:{_RESOLVE_THREAD})+\}}\s*")
GH_API_MESSAGE = (
    "gh api refused: it may read, write PR comments and reviews, and resolve review threads — "
    "any other write can carry labels, and labels are the maintainer's"
)


def _only_resolves_threads(args: list[str]) -> bool:
    """Exactly `graphql -f query='mutation { resolveReviewThread(…) { thread { … } } }'`."""
    match args:
        case ["graphql", "-f" | "--raw-field", query]:
            return _RESOLVE_THREADS.fullmatch(query) is not None
        case _:
            return False


def _check_gh_api(args: list[str]) -> str | None:
    """`gh api`: reads pass (except of labels); of the writes, only PR comments and reviews, and
    the resolving of review threads."""
    if any("labels" in arg.lower() for arg in args):
        return LABEL_MESSAGE
    if _only_resolves_threads(args):
        return None
    method: str | None = None
    operands: list[str] = []
    is_value = False
    for index, arg in enumerate(args):
        if is_value:
            is_value = False
            method = arg if args[index - 1] in ("-X", "--method") else method
        elif arg in _GH_API_VALUE_OPTIONS:
            is_value = True
        elif arg.startswith("--method="):
            method = arg.partition("=")[2]
        elif arg.startswith("-X"):
            method = arg[2:]
        elif not arg.startswith("-"):
            operands.append(arg)
    endpoint = operands[0] if operands else ""
    if endpoint == "graphql":  # always a POST; only a query written out on the command line passes
        inline = any("query=" in arg and "query=@" not in arg for arg in args)
        mutates = any("mutation" in arg.lower() for arg in args)
        return None if inline and not mutates and "--input" not in args else GH_API_MESSAGE
    has_body = any(arg.startswith(_GH_API_BODY_OPTIONS) for arg in args)
    writes = method.upper() != "GET" if method is not None else has_body
    return GH_API_MESSAGE if writes and not _GH_API_COMMENTS.fullmatch(endpoint) else None


def _check_gh(args: list[str]) -> str | None:
    """Refuse the ways `gh` changes labels: the agent's gh acts as the maintainer; CI cannot tell.

    Not every way: a script that calls gh, or an alias the maintainer defined, is not seen (not a
    wall).
    """
    rest = _past_options(args, frozenset({"-R", "--repo"}))
    words = [arg for arg in rest if not arg.startswith("-")]
    options = {arg.partition("=")[0] for arg in rest}
    if words[:1] == ["api"]:
        return _check_gh_api(rest[rest.index("api") + 1 :])
    if words[:1] == ["alias"] and words[1:2] in (["set"], ["import"]):
        return (
            "gh alias refused: an alias hides a command from this guard, and labels are the "
            "maintainer's"
        )
    # Where the options sit is not relied on: `gh pr -R o/r edit 5 --add-label x` puts a value
    # between `pr` and `edit`. --add-label and --remove-label exist only to change labels;
    # --label and -l (also as `-l<value>`) set them on `create` and merely filter on `list`.
    # `gh pr new` is `gh pr create`. And the l may sit in a cluster: `-dl gates-approved`.
    sets_on_create = ("create" in words or "new" in words) and (
        "--label" in options
        or any(arg.startswith("-") and not arg.startswith("--") and "l" in arg for arg in rest)
    )
    if words[:1] == ["label"] or options & {"--add-label", "--remove-label"} or sets_on_create:
        return LABEL_MESSAGE
    return None


_SHELLS = frozenset({"sh", "bash", "zsh", "dash", "ksh"})
_PYTHON = re.compile(r"python[\d.]*")


def _change_directory(args: list[str], shell: _Shell) -> None:
    shell.earlier = (*shell.earlier, shell.cwd)
    operands = _operands(args)
    target = _expand(operands[0], shell.cwd) if operands else None
    if target is not None:  # otherwise the last known directory stays the best guess
        shell.cwd = Path(os.path.normpath(target))


def _check(command: _Command, ctx: RepoContext, shell: _Shell, bodies: list[str]) -> str | None:
    reason = _gate_write(command.writes, ctx, shell)
    if reason is not None:
        return reason
    heredocs = [bodies[number] for number in command.heredocs]  # the ones this command reads
    argv, from_stdin = _unwrap(command.argv)
    if not argv:
        return None
    name, args = Path(argv[0]).name, argv[1:]
    if name in ("cd", "pushd", "popd"):
        _change_directory(args, shell)
        return None
    if name == "trap":  # `trap 'rm -rf x' EXIT`: the first operand runs later, as `eval` would
        return _evaluate(next(iter(_operands(args)), ""), ctx, replace(shell))
    if name == "emulate" and "-c" in args[:-1]:  # zsh: `emulate sh -c 'rm -rf x'`
        return _evaluate(args[args.index("-c") + 1], ctx, replace(shell))
    if name in _SHELLS or name == "eval":
        code = " ".join(args) if name == "eval" else _shell_code(args)
        # Without -c a shell reads its script from a here-document: the same action as `sh -c`.
        scripts = heredocs if code is None else [code]
        # `eval` runs in this shell, so a cd inside it lasts; `sh -c` runs in one of its own
        inner = shell if name == "eval" else replace(shell)
        reasons = (_evaluate(script, ctx, inner) for script in scripts)
        return next((reason for reason in reasons if reason is not None), None)
    if name == "rm":
        return _check_rm(args, ctx, shell, from_stdin)
    if name == "git":
        return _check_git(args)
    if name == "gh":
        return _check_gh(args)
    if _PYTHON.fullmatch(name):
        code = _python_code(args)
        programs = heredocs if code is None else [*heredocs, code]
        return GATE_MESSAGE if any(_names_gate(program) for program in programs) else None
    return _gate_write(_written(name, args), ctx, shell)


def _evaluate(command: str, ctx: RepoContext, shell: _Shell) -> str | None:
    reader = _Reader(command)
    try:
        reader.read()
    except ValueError as error:
        return (
            f"cannot parse this command ({error}) — simplify the quoting, "
            "or put the text in a file (git commit -F, gh pr edit --body-file)"
        )
    shells = [shell]  # one per `( … )` the command sits inside: a subshell works on a copy
    for item in _commands(reader.tokens):
        del shells[item.depth + 1 :]  # its `)` ends a subshell, and with it the cds made inside
        while len(shells) <= item.depth:
            shells.append(replace(shells[-1]))
        reason = _check(item, ctx, shells[-1], reader.bodies)
        if reason is not None:
            return reason
    # A `$( … )` or a pair of backticks holds a command line of its own, run in a subshell. It
    # is judged where the shell ends up, and from where it was before.
    for inside in reader.substitutions:
        reason = _evaluate(inside, ctx, replace(shells[0]))
        if reason is not None:
            return reason
    return None


def evaluate(command: str, ctx: RepoContext) -> str | None:
    """The reason to refuse `command`, or None to let it through."""
    return _evaluate(command, ctx, _Shell(cwd=ctx.cwd or ctx.root))


# ---------------------------------------------------------------------------- the hook


def repo_context(root: Path = ROOT, cwd: Path | None = None) -> RepoContext:
    """The context of a real checkout: git answers what is tracked."""

    def is_tracked(path: Path) -> bool:
        relative = _relative(path, root.resolve())
        if relative is None:
            return False
        # `literal`: the name is not a pattern. `icase`: on a case-insensitive file system
        # `rm makefile` removes the Makefile. No pathspec at all asks about the whole tree.
        pathspec = [f":(top,literal,icase){relative.as_posix()}"] if relative.parts else []
        listing = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--", *pathspec],
            capture_output=True,
            text=True,
            check=False,
        )
        return listing.returncode != 0 or bool(listing.stdout)  # git cannot say: assume tracked

    tmp_dirs = (Path(tempfile.gettempdir()), Path("/tmp"), Path("/private/tmp"))
    return RepoContext(root=root, is_tracked=is_tracked, tmp_dirs=tmp_dirs, cwd=cwd)


def main(stdin: IO[str] = sys.stdin) -> int:
    try:
        payload = cast("dict[str, object]", json.load(stdin))
        command = cast("dict[str, object]", payload["tool_input"])["command"]
        cwd = payload.get("cwd")
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        print(f"guard_bash: cannot read the hook input ({error!r}): refusing", file=sys.stderr)
        return 2
    if not isinstance(command, str):
        print("guard_bash: cannot read the hook input (no command text): refusing", file=sys.stderr)
        return 2
    # `cwd` follows the session's `cd`s, so relative paths are resolved where the shell is.
    try:
        reason = evaluate(command, repo_context(cwd=Path(cwd) if isinstance(cwd, str) else None))
    except Exception as error:  # anything at all: a traceback exits 1, and exit 1 does not block
        reason = f"the guard itself failed ({error!r}), so the command is refused"
    if reason is None:
        return 0
    print(f"guard_bash: {reason}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
