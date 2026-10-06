"""The Bash guard refuses the commands brief 002 names and lets everything else through."""

import io
import json
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

import guard_bash
from guard_bash import RepoContext, evaluate

ROOT = Path("/repo")
TRACKED = frozenset(
    ROOT / name
    for name in ("Makefile", "pyproject.toml", "src/pkg/main.py", "tests/test_skeleton.py")
)


def is_tracked(path: Path) -> bool:
    """A tracked file, or a directory that contains one."""
    return any(path == tracked or path in tracked.parents for tracked in TRACKED)


CTX = RepoContext(root=ROOT, is_tracked=is_tracked, tmp_dirs=(Path("/tmp"),))

HEREDOC_COMMIT = """git commit -m "$(cat <<'EOF'
guard: refuse "git commit --no-verify" and it's -n spelling
EOF
)\""""

HEREDOC_PYTHON = """python3 - <<'EOF'
from pathlib import Path
Path("pyproject.toml").write_text("")
EOF"""


@pytest.mark.parametrize(
    "command",
    [
        # brief 002, acceptance criterion 1
        "rm -rf mutants",
        "rm -r .venv",
        "rm coverage.xml",
        "rm tests/scratch.py",
        "rm -rf /tmp/pkg-proof",
        "cat .github/workflows/ci.yml",
        "grep -n fail_under pyproject.toml",
        "uv add httpx",
        "uv lock",
        "make mutate",
        'git commit -m "mention --no-verify in the message"',
        "gh pr edit 5 --body-file body.md",
        "git push -u origin main-002-harness",
        # the same rules, other spellings
        "rm -rf mutants 2>/dev/null",
        "rm -rf /tmp/a /tmp/b",
        "rm -rf mutants && make mutate",
        "cd /tmp && rm -rf /tmp/pkg-proof",
        "uv sync --locked --all-groups",
        "uv remove httpx",
        "sed -n 5p Makefile",
        "sed -e s/i/x/ Makefile",
        "perl -ne 'print if /check/' Makefile",
        "echo x > /tmp/out.txt",
        "echo x > notes.txt",
        "make check > /tmp/check.txt 2>&1",
        "cat Makefile | tee /tmp/copy",
        "cp Makefile /tmp/Makefile.bak",
        "cp docs/a.md docs/b.md",
        'echo "$HOME" > "$OUT"',
        "uv run python scripts/integrity.py --base origin/main",
        'uv run python -c "import sys; print(sys.version)"',
        "git commit -F /tmp/message.txt",
        'git commit -am "note"',
        "git commit --amend --no-edit",
        HEREDOC_COMMIT,
        "git push origin main-002-harness",
        "git status --porcelain",
        "gh pr view 5 --json labels",
        "gh pr list --label gates-approved",
        "gh pr ready 5",
        "gh api repos/o/r/pulls/5/comments",
        "echo 'rm -rf /' is what the guard refuses",
        # quoted punctuation is not an operator, and a comment is not a command
        'echo ">" Makefile',
        "grep '>' pyproject.toml",
        'git commit -m "a; rm -rf ~/scratch"',
        "find . -name x.pyc -exec echo {} \\;",
        "make check  # don't stop on the apostrophe",
        "# rm -rf ~/scratch",
        "echo a#b > notes.txt",
        "echo a\\ b # rm -rf ~/scratch",
        # backticks that run nothing harmful, or nothing at all: quoted, escaped, or `$'…'`
        "echo `date`",
        "echo 'use `rm -rf ~/scratch` with care'",
        "echo \\`rm -rf ~/scratch\\`",
        "echo $'it\\'s' > notes.txt",
        # substitutions and arithmetic that run nothing harmful; a `<<` that is only text
        'echo "$(date +%s)" "${HOME:-/tmp}" $(( (1+2) * 3 ))',
        'echo "a $(echo "b") c"',
        "echo '<<X' > notes.txt",
        # a here-document ends at its delimiter exactly: these bodies are data to the end
        "cat <<EOF-1\nrm -rf ~/scratch\nEOF-1\nmake check",
        "cat <<EOF\n EOF\nrm -rf ~/scratch\nEOF",
        "cat <<EOF\r\nrm -rf ~/scratch\nEOF",
        "trap - EXIT",
        # a brace expansion that writes no gate file; a test that is only a test
        "cp Makefile{,.bak}",
        # `cp /tmp/x pyproject.toml pyproject.bak`: the gate file is a source here, and cp
        # fails because the last word is no directory (run: nothing is written)
        "cp /tmp/x pyproject.{toml,bak}",
        "echo {a,b} > notes.txt",
        "[[ -f Makefile ]]",
        "noglob echo *",
        'echo "${(U)HOME}" ${#HOME} ${HOME:-x}',
        "git push --atomic origin main-002-harness",
        "# cleanup; rm -rf ~/scratch",
        "echo \\; rm -rf ~/scratch",
        "cat <<EOF > /tmp/notes.txt\nrm -rf ~/scratch\nEOF",
        "rm notes@Makefile",
        # plain rm outside the repository: only the tracked rule applies to it
        "rm ~/scratch.txt",
        "rm -v ~/scratch.txt",
        "rm -- -f ~/scratch.txt",
        # options that only look like the refused ones
        "git --version",
        "git commit -uno -m x",
        "git push --follow-tags origin main-002-harness",
        "sed --quiet 5p Makefile",
        "perl -MList::Util -e 'print 1' Makefile",
        "cd && make check",
        "bash docs/run.sh",
        # -c belongs to the module being run, not to python (PR #5 review)
        "uv run python -m pytest -c pyproject.toml",
        "python -m pytest -c pyproject.toml tests",
        "python3 tools/report.py -c pyproject.toml",
        "python3 -Wonce docs/tool.py",
        # a here-document belongs to the command that reads it, not to a shell or python that
        # happens to be on the same command line (PR #5 review, round 2)
        "cat <<EOF > /tmp/notes.txt\nrm -rf ~/scratch\nEOF\nbash docs/run.sh",
        "git commit -F - <<EOF\nfix scripts/x.py\nEOF\nuv run python docs/tool.py",
        # pushes that stay on the feature branch
        "git push origin main-002-harness:main-002-harness",
        "git push origin HEAD:main-002-harness",
        "git push origin v1.0.0",
        "git push origin HEAD:heads/main-002-harness",
        # --force-if-includes forces nothing by itself (PR #5 review, round 4)
        "git push --force-if-includes origin main-002-harness",
        "git push origin 'refs/heads/main-*:refs/heads/main-*'",
        # a cd inside ( … ) ends with the subshell; a `)` without a `(` is a case pattern
        # (PR #5 review, round 3)
        "(cd docs && ls); rm -rf mutants",
        "case $x in a) true ;; esac; rm -rf mutants",
        "cd /tmp && echo x > /tmp/Makefile",
        "cd /tmp && echo x > notes.txt",
        # gh api may read, and may write PR comments and reviews
        "gh api repos/o/r/pulls/5/comments/123/replies -f body=ok",
        "gh api -X POST repos/o/r/issues/5/comments -F body=@/tmp/reply.md",
        "gh api -X POST repos/o/r/pulls/5/reviews --input /tmp/review.json",
        "gh api -X GET repos/o/r/pulls -f state=open",
        "gh api graphql -f query='query { viewer { login } }'",
        # the one mutation that passes: resolving review threads, written out, and nothing else
        "gh api graphql -f query='mutation { resolveReviewThread(input: "
        '{threadId: "PRRT_kwDOTbmYgc6oqzUm"}) { thread { isResolved } } }\'',
        "gh api graphql -f query='mutation { "
        'a: resolveReviewThread(input: {threadId: "PRRT_1"}) { thread { id } } '
        'b: resolveReviewThread(input: {threadId: "PRRT_2"}) { thread { id isResolved } } }\'',
        "gh pr list -l bug",
        "gh alias list",
    ],
)
def test_allows(command: str) -> None:
    assert evaluate(command, CTX) is None


@pytest.mark.parametrize(
    ("command", "word"),
    [
        # brief 002, acceptance criterion 2
        ("rm -rf ~/scratch", "outside"),
        ("rm -rf /", "outside"),
        ("rm -r src/pkg", "tracked"),
        ("rm -fr tests/test_skeleton.py", "tracked"),
        ("rm -f Makefile", "tracked"),
        ("rm Makefile", "tracked"),
        ("cd /tmp && rm -rf x", "resolve"),
        ('rm -rf "$TMPDIR/x"', "resolve"),
        ("sed -i '' 's/90/50/' pyproject.toml", "gate file"),
        ("echo x >> Makefile", "gate file"),
        ("python -c \"open('Makefile','w')\"", "gate file"),
        ("cp /tmp/ci.yml .github/workflows/ci.yml", "gate file"),
        ("git commit -m x --no-verify", "no-verify"),
        ("git commit -n -m x", "no-verify"),
        ("git push --force-with-lease origin main-002-harness", "force"),
        ("gh pr edit 5 --add-label gates-approved", "the maintainer"),
        ("gh label create x", "the maintainer"),
        ("gh api -X POST repos/o/r/issues/5/labels -f 'labels[]=x'", "the maintainer"),
        # rm: other spellings of the same action
        ("rm -R ~/scratch", "outside"),
        ("rm --recursive ~/scratch", "outside"),
        ("rm --force ~/scratch", "outside"),
        ("rm -rf ~", "outside"),
        ("rm -f Makefile -- notes.txt", "tracked"),
        ("rm -rf `pwd`/x", "resolve"),
        ("pushd /tmp && rm -rf x", "resolve"),
        ("cd docs && rm -rf ~/scratch", "outside"),
        ("rm -rf -- ~/scratch", "outside"),
        ("rm -rf ..", "outside"),
        ("rm -rf /tmp", "outside"),
        ("rm -rf .", "tracked"),
        ("rm -rf /repo/src", "tracked"),
        ("rm -rf .git", ".git"),
        ("rm .git/hooks/pre-commit", ".git"),
        ("rm -rf build/*", "resolve"),
        ("rm tests/test_*.py", "resolve"),
        ("rm $FILE", "resolve"),
        ("rm -rf ~other/x", "resolve"),
        ("ls | xargs rm -rf", "resolve"),
        # rm: wherever the command sits
        ("make check; rm -rf ~/scratch", "outside"),
        ("make check\nrm -rf ~/scratch", "outside"),
        ("make check || rm -rf ~/scratch", "outside"),
        ("true | rm -rf ~/scratch", "outside"),
        ("(rm -rf ~/scratch)", "outside"),
        ("echo $(rm -rf ~/scratch)", "outside"),
        ("rm -rf \\\n  ~/scratch", "outside"),
        ("FOO=1 rm -rf ~/scratch", "outside"),
        ("sudo rm -rf ~/scratch", "outside"),
        ("env FOO=1 rm -rf ~/scratch", "outside"),
        ("command rm -rf ~/scratch", "outside"),
        ("timeout 5 rm -rf ~/scratch", "outside"),
        ("/bin/rm -rf ~/scratch", "outside"),
        ('bash -c "rm -rf ~/scratch"', "outside"),
        ("sh -c 'cd /tmp && rm -rf x'", "resolve"),
        ("eval rm -rf ~/scratch", "outside"),
        # a shell that reads its script from a here-document is the same action as `sh -c`
        ("bash <<'EOF'\nrm -rf ~/scratch\nEOF", "outside"),
        ("bash -s <<EOF\nrm -rf ~/scratch\nEOF", "outside"),
        ("sh <<EOF\necho hi > Makefile\nEOF", "gate file"),
        ("bash -o pipefail -c 'rm -rf ~/scratch'", "outside"),
        # a here-document piped into a shell is that shell's script
        ("cat <<EOF | sh\nrm -rf ~/scratch\nEOF", "outside"),
        ("cat <<EOF | tee /tmp/copy.sh | bash\nrm -rf ~/scratch\nEOF", "outside"),
        ("sh -ce 'rm -rf ~/scratch'", "outside"),
        ("bash -cx 'rm -rf ~/scratch'", "outside"),
        ("bash -c -x 'rm -rf ~/scratch'", "outside"),
        ("for d in a b; do rm -rf $d; done", "resolve"),
        ("if true; then rm -rf ~/scratch; fi", "outside"),
        ("! rm -rf ~/scratch", "outside"),
        ("{ rm -rf ~/scratch; }", "outside"),
        ('rm -rf ";" ~/scratch', "outside"),
        ("echo a#b; rm -rf ~/scratch", "outside"),
        ("make check # a comment\nrm -rf ~/scratch", "outside"),
        ("x=$((1<<2))\nrm -rf ~/scratch", "outside"),
        ("cat <<EOF > /tmp/x\nbody\nEOF\nrm -rf ~/scratch", "outside"),
        ("echo \\\\; rm -rf ~/scratch", "outside"),
        ("echo '\\'; rm -rf ~/scratch", "outside"),
        ('echo "a"; rm -rf ~/scratch', "outside"),
        ("sudo -u nobody rm -rf ~/scratch", "outside"),
        # gate files: every writer the brief lists, every kind of gate path
        ("echo x > .claude/settings.json", "gate file"),
        ("echo x > ./docs/../Makefile", "gate file"),
        ("echo x > /repo/uv.lock", "gate file"),
        ("echo x >.python-version", "gate file"),
        ("make check &> .gitignore", "gate file"),
        ("echo x >| .betterleaks.toml", "gate file"),
        ("cat /tmp/x | tee -a .betterleaksignore", "gate file"),
        ("sed -i.bak s/a/b/ .pre-commit-config.yaml", "gate file"),
        ("sed -Ei s/a/b/ scripts/guard_bash.py", "gate file"),
        ("sed --in-place s/a/b/ Makefile", "gate file"),
        ("sed -i '' s/a/b/ scripts/*.py", "gate file"),
        ("sed -i '' s/a/b/ *.toml", "gate file"),
        ("perl -pi -e 's/a/b/' Makefile", "gate file"),
        ("truncate -s 0 uv.lock", "gate file"),
        ("mv /tmp/guard.py scripts/guard_bash.py", "gate file"),
        ("mv Makefile /tmp/Makefile", "gate file"),
        ("cp /tmp/Makefile .", "gate file"),
        ("cp -t .github /tmp/pull_request_template.md", "gate file"),
        ("install -m 644 /tmp/x.yml .github/workflows/ci.yml", "gate file"),
        ("cp /tmp/ci.yml .github/workflows/ci.yml 2>/dev/null", "gate file"),
        ("python3 -c \"open('.gitignore','a').write('x')\"", "gate file"),
        ("uv run python -c \"open('scripts/x.py','w')\"", "gate file"),
        ("uv run --with rich python -c \"open('uv.lock','w')\"", "gate file"),
        (HEREDOC_PYTHON, "gate file"),
        ("cd docs && echo x > ../Makefile", "gate file"),
        ("cat > Makefile <<EOF\nall:\nEOF", "gate file"),
        ("sed -e s/a/b/ -i Makefile", "gate file"),
        ("sed -i '' s/a/b/ .git*/workflows/ci.yml", "gate file"),
        ("cp --target-directory=scripts /tmp/x.py", "gate file"),
        ("cp -v -t .github /tmp/x.md", "gate file"),
        ("mv -t /tmp Makefile", "gate file"),
        ("python3 -u -c \"open('Makefile','w')\"", "gate file"),
        ("python3 -W ignore -c \"open('Makefile','w')\"", "gate file"),
        ("python3 -c\"open('Makefile','w')\"", "gate file"),
        ("python3 -Bc\"open('Makefile','w')\"", "gate file"),
        ("python3 -c \"open('Makefile','w')\" now", "gate file"),
        # git commit: the hook is skipped however the flag is spelled
        ("git commit -nm x", "no-verify"),
        ("git commit -anm x", "no-verify"),
        ("git commit --no-veri -m x", "no-verify"),
        ("git -C . commit --no-verify -m x", "no-verify"),
        ("git -c user.name=x commit -m x -n", "no-verify"),
        ("make check && git commit -m x --no-verify", "no-verify"),
        ("git -C . -c user.name=x commit -n -m x", "no-verify"),
        ("git --no-pager commit --no-verify -m x", "no-verify"),
        ("git commit -uno --no-verify", "no-verify"),
        ("git commit -m x --no-ver\\\nify", "no-verify"),
        # git push
        ("git push --force", "force"),
        ("git push -f origin main-002-harness", "force"),
        ("git push -uf origin main-002-harness", "force"),
        ("git push origin +main-002-harness", "force"),
        ("git commit -m x && git push --force-with-lease", "force"),
        ("git push --force-with-lease --force-if-includes origin main-002-harness", "force"),
        ("git push --force-with-lease=main-002-harness origin main-002-harness", "force"),
        ("git push --force-w origin main-002-harness", "force"),
        # a push that lands on the base branch skips every gate (PR #5 review, round 2)
        ("git push origin main", "merges"),
        ("git push -u origin main", "merges"),
        ("git push origin main-002-harness:main", "merges"),
        ("git push origin HEAD:main", "merges"),
        ("git push origin HEAD:refs/heads/main", "merges"),
        ("git push origin :main", "merges"),
        ("git push origin main-002-harness main-x:main", "merges"),
        ("git push --all origin", "merges"),
        ("git push --mirror", "merges"),
        # round 3: git also resolves `heads/main` to the branch; --branches is --all's newer name
        ("git push origin main-x:heads/main", "merges"),
        ("git push origin HEAD:heads/main", "merges"),
        ("git push --branches origin", "merges"),
        ("git push origin 'refs/heads/*:refs/heads/*'", "merges"),
        # round 3: a cd may not last — it ends with its ( … ), `cd -` undoes it, it can fail, or
        # it is never reached — so a write after it is judged from where the shell was, too
        ("(cd /tmp && true); echo x > Makefile", "gate file"),
        ("(cd /tmp); echo x >> pyproject.toml", "gate file"),
        ("cd /tmp; cd -; echo x > Makefile", "gate file"),
        ("cd /no/such/directory; echo x > Makefile", "gate file"),
        ("false && cd /tmp; sed -i '' s/a/b/ Makefile", "gate file"),
        ("(cd /tmp && true); rm -r src/pkg", "tracked"),
        # labels
        ("gh pr edit 5 --remove-label gates-approved", "the maintainer"),
        ("gh pr edit 5 --add-label=gates-approved", "the maintainer"),
        ("gh issue edit 5 --add-label gates-approved", "the maintainer"),
        ("gh pr create --base main --title x --label gates-approved", "the maintainer"),
        ("gh -R o/r pr edit 5 --add-label gates-approved", "the maintainer"),
        ("gh --repo o/r pr edit 5 --add-label gates-approved", "the maintainer"),
        # an option with a value between `pr` and `edit` (PR #5 review)
        ("gh pr -R o/r edit 5 --add-label gates-approved", "the maintainer"),
        ("gh pr --repo o/r edit 5 --remove-label gates-approved", "the maintainer"),
        ("gh issue -R o/r create --title x --label gates-approved", "the maintainer"),
        ("gh pr -R o/r create --base main -l gates-approved", "the maintainer"),
        # round 2: the value attached to -l, an alias, and gh api writes that can carry labels
        ("gh pr create --base main --title x -lgates-approved", "the maintainer"),
        ("gh alias set lab 'pr edit 5 --add-label gates-approved'", "the maintainer"),
        ("gh alias import /tmp/aliases.yml", "the maintainer"),
        ("gh api -X PATCH repos/o/r/issues/5 --input /tmp/body.json", "the maintainer"),
        ("gh api -XPATCH repos/o/r/issues/5 --input /tmp/body.json", "the maintainer"),
        ("gh api --method=PUT repos/o/r/issues/5 --input /tmp/body.json", "the maintainer"),
        ("gh api repos/o/r/issues/5 -f title=x", "the maintainer"),
        ("gh api repos/o/r/issues/5 -ftitle=x", "the maintainer"),
        ("gh api repos/o/r/issues/5/comments/../../5 -f title=x", "the maintainer"),
        (
            "gh api graphql -f query='mutation{updateIssue(input:{id:1,labelIds:[2]})}'",
            "the maintainer",
        ),
        ("gh api graphql -F query=@/tmp/query.graphql", "the maintainer"),
        ("gh api graphql --input /tmp/query.json", "the maintainer"),
        ("gh label delete gates-approved --yes", "the maintainer"),
        ("gh api -X DELETE repos/o/r/issues/5/labels/gates-approved", "the maintainer"),
        (
            "gh api graphql -f query='mutation { addLabelsToLabelable(input: {}) }'",
            "the maintainer",
        ),
        ("gh api -X PUT repos/o/r/pulls/5/reviews/7/dismissals -f message=x", "the maintainer"),
        # round 4: a `#` after an escaped space or an escaped `;` is part of the word, not a
        # comment — the shell runs what follows the next `;`
        ("echo a\\ #; rm Makefile", "tracked"),
        ("echo a\\ #; git push origin HEAD:main", "merges"),
        ("echo a\\ #; gh pr edit 5 --add-label gates-approved", "the maintainer"),
        ("echo a\\;#b; rm -rf ~/scratch", "outside"),
        # found while checking that fix: in `$'…'` a backslash escapes the quote, and what
        # sits between backticks is a command line of its own, also inside double quotes
        ("echo $'\\'' ; rm -rf ~/scratch #'", "outside"),
        ("echo `rm -rf ~/scratch`", "outside"),
        ("x=`git push origin HEAD:main`", "merges"),
        ('echo "`gh pr edit 5 --add-label gates-approved`"', "the maintainer"),
        ("cd /tmp; echo `echo x > Makefile`", "gate file"),
        # round 5: inside "$( … )" quotes open and close on their own, and a `<<X` in quotes,
        # in a comment or in arithmetic is no here-document — what follows still runs
        ("echo \"$(echo '\"')\"; rm Makefile; : \\'", "tracked"),
        ("echo \"$(echo '\"')\"; gh pr edit 5 --add-label gates-approved; : \\'", "the maintainer"),
        ("echo '<<X'\nrm -rf src\nX", "tracked"),
        ("echo hi # <<X\nrm -rf src\nX", "tracked"),
        ("echo $((1<<2))\nrm -rf src\n2", "tracked"),
        ("echo '<<X'\ngh pr edit 5 --add-label gates-approved\nX", "the maintainer"),
        # a substitution runs inside double quotes and inside an unquoted here-document
        ('echo "$(rm -rf ~/scratch)"', "outside"),
        ("cat <<EOF\n$(rm -rf ~/scratch)\nEOF", "outside"),
        # what the guard cannot read the way the shell does, it refuses
        ("((x<<2))\nrm -rf src\n2", "parse"),
        ("echo \"$(case x in x) echo '\"' ;; esac)\"; rm -rf ~/scratch; : \\'", "parse"),
        ('echo "${x:-"a"}"; rm -rf ~/scratch', "parse"),
        # round 8: `gh pr new` is `gh pr create`; `-dl x` carries the l in a cluster
        ("gh pr new --base main --title x --label gates-approved", "the maintainer"),
        ("gh pr create --base main --title x -dl gates-approved", "the maintainer"),
        # round 8: `eval` runs in the shell itself, so its cd lasts
        ("eval 'cd ..'; rm -rf outside/keep", "resolve"),
        # round 7: a protected name by another case, or through a brace expansion
        ("rm -rf .GIT", ".git"),
        ("rm .Git/HEAD", ".git"),
        ("python3 -c \"open('MAKEFILE','w').write('x')\"", "gate file"),
        ("tee Makefil{e,} </dev/null", "gate file"),
        ("tee pyproject.{toml,bak} </dev/null", "gate file"),
        ("echo x > Makefil{e,}", "gate file"),
        ("mv Makefile{,.old}", "gate file"),
        ("tee Makefil{e..e}", "gate file"),
        # round 7: the tool's shell is zsh; these run the command after them
        ("noglob rm Makefile", "tracked"),
        ("nocorrect rm Makefile", "tracked"),
        ("repeat 1 rm Makefile", "tracked"),
        ("=rm Makefile", "tracked"),
        ("coproc rm Makefile", "tracked"),
        ("- rm Makefile", "tracked"),
        ("if [[ 1 == 1 ]] rm Makefile", "tracked"),
        ("emulate sh -c 'rm Makefile'", "tracked"),
        ("echo ${(e):-'$(rm Makefile)'}", "parse"),
        # round 7: zsh's redirections that overwrite whatever `noclobber` says
        ("echo x >! Makefile", "gate file"),
        ("echo x >>| Makefile", "gate file"),
        ("echo x &>! pyproject.toml", "gate file"),
        # round 6: to the shell a carriage return is no blank, so `a<CR>#` is a word
        ("echo a\r#; rm Makefile", "tracked"),
        ("echo a\r#; gh pr edit 5 --add-label gates-approved", "the maintainer"),
        # round 6: `function` and `trap` run what follows them; git takes shortened options
        ("function f { rm Makefile; }; f", "tracked"),
        ("trap 'rm -rf ~/scratch' EXIT", "outside"),
        ("git push --al origin", "merges"),
        ("git push --mir", "merges"),
        ("git push --bra origin", "merges"),
        # round 5: the directory as a word of its own
        ("cp --target-directory scripts /tmp/x.py", "gate file"),
        ("install --target-directory .github /tmp/x.yml", "gate file"),
        # round 4: a tool's own config file is read before pyproject.toml or the Makefile
        ("echo '[pytest]' > pytest.ini", "gate file"),
        ("echo '{}' > pyrightconfig.json", "gate file"),
        ("cp /tmp/ruff.toml ruff.toml", "gate file"),
        ("cp /tmp/ruff.toml .ruff.toml", "gate file"),
        ("printf 'check:\\n\\ttrue\\n' > GNUmakefile", "gate file"),
        ("echo '[coverage:report]' >> setup.cfg", "gate file"),
        ("tee .coveragerc < /tmp/rc", "gate file"),
        ("mv /tmp/uv.toml uv.toml", "gate file"),
        # resolveReviewThread passes only alone: no second mutation, no variable, no file
        (
            "gh api graphql -f query='mutation { resolveReviewThread(input: "
            '{threadId: "PRRT_1"}) { thread { id } } '
            'updateIssue(input: {id: "I_1", title: "x"}) { issue { id } } }\'',
            "the maintainer",
        ),
        (
            "gh api graphql -f query='mutation($id: ID!) { resolveReviewThread(input: "
            "{threadId: $id}) { thread { id } } }' -f id=PRRT_1",
            "the maintainer",
        ),
        (
            "gh api graphql -f query='mutation { resolveReviewThread(input: "
            '{threadId: "PRRT_1"}) { thread { id } } }\' --input /tmp/more.json',
            "the maintainer",
        ),
        (
            "gh api graphql -f query='mutation { unresolveReviewThread(input: "
            '{threadId: "PRRT_1"}) { thread { id } } }\'',
            "the maintainer",
        ),
        (
            "gh api graphql -f query='mutation { resolveReviewThread(input: "
            '{threadId: "PRRT_1"}) { thread { pullRequest { id } } } }\'',
            "the maintainer",
        ),
        # a command the guard cannot read is refused, not waved through
        ("rm -rf 'unbalanced", "parse"),
    ],
)
def test_refuses(command: str, word: str) -> None:
    reason = evaluate(command, CTX)
    assert reason is not None
    assert word in reason


# Each line has a SLOT where a command stands. bash runs the line with a harmless command there;
# the guard reads it with a command it refuses. The lines are harmless themselves: echo, cat, `:`.
SHELL_LINES = [
    "echo a; SLOT",
    "true && SLOT",
    "(echo a); SLOT",
    "if true; then SLOT; fi",
    "case x in x) SLOT ;; esac",
    "echo a >/dev/null 2>&1; SLOT",
    "echo a \\\n; SLOT",
    # comments
    "echo a # ; SLOT",
    "echo a\\ #; SLOT",
    "echo a\\;#b; SLOT",
    "echo a\\ b # SLOT",
    # quotes
    'echo "x" \'y\'"z"; SLOT',
    'echo "a\\"; SLOT; echo \\"b"',
    "echo $'\\'' ; SLOT #'",
    'echo ${x:-"a; b"}; SLOT',
    # substitutions
    "echo `SLOT`",
    'echo "`SLOT`"',
    "echo '`SLOT`'",
    "echo \\`SLOT\\`",
    'echo "$(SLOT)"',
    'echo "a $(echo "b"; SLOT) c"',
    'echo "${HOME:-$(SLOT)}"',
    "x=$(( 1 + $(SLOT; echo 1) ))",
    "echo \"$(echo '\"')\"; SLOT; : \\'",
    "echo \"$(echo ')' )\"; SLOT",
    "echo $(echo a # )\n); SLOT",
    "echo \"$(case x in x) echo '\"' ;; esac)\"; SLOT; : \\'",
    # here-documents
    "cat <<X\nSLOT\nX",
    "cat <<X\n$(SLOT)\nX",
    "cat <<'X'\n$(SLOT)\nX",
    "cat <<X | cat\nbody\nX\nSLOT",
    "cat <<-X\n\tbody\n\tX\nSLOT",
    "cat <<X\n X\ndon't\nX\nSLOT; echo 'x' ' '",
    "cat <<X-1\ndon't\nX-1\nSLOT; echo 'x' ' '",
    "echo \"$(cat <<'X'\nit's (odd\nX\n)\"; SLOT",
    "echo '<<X'\nSLOT\nX",
    "echo hi # <<X\nSLOT\nX",
    "echo $((1<<2))\nSLOT\n2",
    # round 6: a carriage return is an ordinary character to the shell, also in a delimiter
    "echo a\r#; SLOT",
    "cat <<X\r\nX\ndon't\nX\r\nSLOT; : \\'",
    # round 6: commands that run a command
    "function f { SLOT; }; f",
    "trap 'SLOT' EXIT",
    # round 7: zsh puts these in front of a command, or needs no `then`/`do`
    "noglob SLOT",
    "nocorrect SLOT",
    "repeat 1 SLOT",
    "coproc SLOT",
    "- SLOT",
    "=SLOT",
    "if [[ 1 == 1 ]] SLOT",
    "if [[ 1 == 1 ]] { SLOT }",
    "while [[ ! -e slot-ran ]] { SLOT }",
    "for x (a) SLOT",
    "f() SLOT; f",
    "() { SLOT }",
    "emulate sh -c 'SLOT'",
    "echo a >! out.txt; SLOT",
    "echo a &| SLOT",
    "echo ${(e):-'$(SLOT)'}",
    "echo \"${(e):-'$(SLOT)'}\"",
]

# Every ASCII character that is not a letter or a digit, in the places where the reader has to
# know what it is: before a `#`, between two words, after a here-document's delimiter, in front
# of a word. Round 6 found the carriage return by hand; this asks about all of them.
CHARACTERS = [chr(code) for code in range(1, 128) if not chr(code).isalnum()]
CHARACTER_LINES = [
    "echo a{}#; SLOT",
    "echo a{}SLOT",
    "echo a {}# b\nSLOT",
    "echo {}; SLOT",
    "cat <<X{}\nbody\nX\nSLOT",
]


# Claude Code runs the Bash tool through the user's shell: zsh on a Mac, bash on CI's runner
# (PR #5 review, round 7). Each shell that is installed is asked; `zsh -f` reads no startup file.
SHELLS = [shell for shell in (["bash", "-c"], ["zsh", "-f", "-c"]) if shutil.which(shell[0])]
SHELL_NAMES = [shell[0] for shell in SHELLS]


def shell_runs_the_slot(shell: list[str], line: str, directory: Path) -> bool:
    command = line.replace("SLOT", "touch slot-ran")
    subprocess.run([*shell, command], cwd=directory, capture_output=True, check=False, timeout=30)
    return (directory / "slot-ran").exists()


@pytest.mark.parametrize("shell", SHELLS, ids=SHELL_NAMES)
@pytest.mark.parametrize("char", CHARACTERS, ids=[f"0x{ord(char):02x}" for char in CHARACTERS])
def test_the_guard_reads_each_character_as_the_shell_does(
    shell: list[str], char: str, tmp_path: Path
) -> None:
    for number, template in enumerate(CHARACTER_LINES):
        line = template.replace("{}", char)
        directory = tmp_path / str(number)
        directory.mkdir()
        guard_refused = evaluate(line.replace("SLOT", "rm -rf ~/scratch"), CTX) is not None

        assert guard_refused or not shell_runs_the_slot(shell, line, directory), repr(line)


@pytest.mark.parametrize("shell", SHELLS, ids=SHELL_NAMES)
@pytest.mark.parametrize("line", SHELL_LINES)
def test_the_guard_loses_no_command_that_the_shell_runs(
    shell: list[str], line: str, tmp_path: Path
) -> None:
    """The guard and the shell must agree on where commands are: quoting, comments,
    substitutions, here-documents, words in front of a command. Asked of the shells themselves
    (PR #5 review, rounds 4 to 7)."""
    guard_refused = evaluate(line.replace("SLOT", "rm -rf ~/scratch"), CTX) is not None

    assert guard_refused or not shell_runs_the_slot(shell, line, tmp_path)


@pytest.mark.parametrize("shell", SHELLS, ids=SHELL_NAMES)
def test_most_shell_lines_do_run_their_slot(shell: list[str], tmp_path: Path) -> None:
    """Otherwise the test above would pass by proving nothing."""
    ran = 0
    for number, line in enumerate(SHELL_LINES):
        directory = tmp_path / str(number)
        directory.mkdir()
        ran += shell_runs_the_slot(shell, line, directory)

    assert ran >= 25


def test_bash_is_among_the_shells_asked() -> None:
    assert "bash" in SHELL_NAMES


def test_gate_file_and_label_messages_are_the_ones_the_brief_words() -> None:
    assert (
        evaluate("echo x >> Makefile", CTX)
        == "gate file — use the editor so the maintainer sees the diff"
    )
    assert evaluate("gh label create x", CTX) == "labels are the maintainer's"


def test_a_write_after_a_cd_says_how_to_name_another_directorys_file() -> None:
    """Judged from where the shell was, `Makefile` is the gate file; the reason says what to do."""
    assert evaluate("cd /tmp && echo x > Makefile", CTX) == guard_bash.GATE_AFTER_CD_MESSAGE
    assert "absolute" in guard_bash.GATE_AFTER_CD_MESSAGE
    # where the shell is now comes first: this one is the gate file whether or not the cd lasts
    assert evaluate("cd docs && echo x > ../Makefile", CTX) == guard_bash.GATE_MESSAGE


def test_a_brace_expansion_is_made_in_the_shells_order() -> None:
    assert guard_bash.expand_braces("Makefile{,.old}") == ["Makefile", "Makefile.old"]
    assert guard_bash.expand_braces("{a,b}{c,d}") == ["ac", "ad", "bc", "bd"]
    assert guard_bash.expand_braces("a{x}b") == ["a{x}b"]
    assert guard_bash.expand_braces("plain") == ["plain"]
    assert guard_bash.expand_braces("x{1..3}") == ["x*"]


def test_a_brace_expansion_is_never_made_large() -> None:
    """Eight groups of ten options are 10**8 words: a minute and gigabytes, in a hook that runs
    before every Bash call — and a hook that is killed does not block (PR #5 review, round 8).
    Past a few dozen words the word is read as a glob instead: every group a `*`."""
    group = "{" + ",".join("abcdefghij") + "}"
    many = "Makefil" + group * 8
    nested = "{a,{b,{c,{d,{e,{f,{g,{h,i}}}}}}}}" * 6

    assert guard_bash.expand_braces(many) == ["Makefil********"]
    assert len(guard_bash.expand_braces(nested)) == 1
    assert len(guard_bash.expand_braces("{" + ",".join(["x"] * 5000) + "}")) == 1
    # a command that writes nothing is not expanded at all; one that writes is judged as a glob
    assert evaluate(f"echo {many}", CTX) is None
    assert evaluate(f"tee {many}", CTX) == guard_bash.GATE_MESSAGE


def test_a_quoted_flag_in_the_message_is_not_a_flag() -> None:
    assert evaluate('git commit -m "--no-verify"', CTX) is None
    assert evaluate("git commit --message -n", CTX) is None
    assert evaluate("git commit -m x -- -n", CTX) is None


def test_relative_paths_are_resolved_against_the_shell_directory() -> None:
    in_src = replace(CTX, cwd=ROOT / "src")
    assert "tracked" in (evaluate("rm -r pkg", in_src) or "")
    assert evaluate("rm -r pkg", CTX) is None
    assert evaluate("echo x > ../Makefile", in_src) == guard_bash.GATE_MESSAGE
    assert evaluate("echo x > Makefile", in_src) is None

    elsewhere = replace(CTX, cwd=Path("/elsewhere"))
    assert "outside" in (evaluate("rm -rf x", elsewhere) or "")
    assert evaluate("rm -rf x", replace(CTX, cwd=Path("/tmp/work"))) is None


def test_a_symlink_that_leaves_the_repository_is_followed(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    outside = tmp_path / "outside"
    (outside / "keep").mkdir(parents=True)
    root.mkdir()
    (root / "link").symlink_to(outside)
    ctx = RepoContext(root=root, is_tracked=lambda _path: False, tmp_dirs=())
    assert "outside" in (evaluate("rm -rf link/keep", ctx) or "")
    assert evaluate("rm -rf plain", ctx) is None


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def test_repo_context_asks_git_what_is_tracked(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "pkg").mkdir(parents=True)
    (root / "kept.py").write_text("x = 1\n", "utf-8")
    (root / "pkg" / "mod.py").write_text("y = 2\n", "utf-8")
    (root / "we*rd.py").write_text("z = 3\n", "utf-8")
    git(root, "init", "-q")
    git(root, "add", "kept.py", "pkg/mod.py")
    (root / "scratch.txt").write_text("", "utf-8")
    (root / "build").mkdir()

    ctx = guard_bash.repo_context(root)

    assert ctx.root == root
    assert Path("/tmp") in ctx.tmp_dirs
    assert Path("/private/tmp") in ctx.tmp_dirs
    assert not ctx.is_tracked(tmp_path / "elsewhere")
    assert "tracked" in (evaluate("rm kept.py", ctx) or "")
    assert "tracked" in (evaluate("rm -r pkg", ctx) or "")
    assert "tracked" in (evaluate("rm -rf .", ctx) or "")
    assert evaluate("rm scratch.txt", ctx) is None
    assert evaluate("rm -rf build", ctx) is None
    # the name is passed to git literally: a `*` in it is not a pattern that matches kept.py
    assert evaluate("rm -f 'we*rd.py'", ctx) is not None
    assert not ctx.is_tracked(root / "we*rd.py")
    assert not ctx.is_tracked(root / "*.py")


def test_repo_context_treats_a_path_as_tracked_when_git_cannot_answer(tmp_path: Path) -> None:
    ctx = guard_bash.repo_context(tmp_path)  # not a repository: git fails
    assert ctx.is_tracked(tmp_path / "anything")


def hook_input(command: object, **extra: object) -> io.StringIO:
    return io.StringIO(
        json.dumps({"tool_name": "Bash", "tool_input": {"command": command}} | extra)
    )


def test_main_refuses_with_exit_2_and_the_reason_on_stderr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert guard_bash.main(hook_input("rm -rf ~/x")) == 2
    err = capsys.readouterr().err
    assert err.startswith("guard_bash: ")
    assert "outside" in err
    assert err.count("\n") == 1


def test_main_allows_with_exit_0_and_says_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    assert guard_bash.main(hook_input("make check")) == 0
    assert capsys.readouterr() == ("", "")


def test_main_uses_the_directory_the_hook_reports(capsys: pytest.CaptureFixture[str]) -> None:
    assert guard_bash.main(hook_input("rm -rf x", cwd=str(Path.home()))) == 2
    assert "outside" in capsys.readouterr().err


def test_main_refuses_when_the_guard_itself_fails(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A traceback would exit 1, and exit 1 does not block: the command would run unchecked."""

    def broken(command: str, ctx: RepoContext) -> str | None:
        raise ValueError("embedded null byte")

    monkeypatch.setattr(guard_bash, "evaluate", broken)

    assert guard_bash.main(hook_input("make check")) == 2
    err = capsys.readouterr().err
    assert err.startswith("guard_bash: ")
    assert "embedded null byte" in err
    assert err.count("\n") == 1


@pytest.mark.parametrize(
    "stdin",
    ["not json", "[]", "{}", '{"tool_input": {}}', '{"tool_input": {"command": 7}}'],
)
def test_main_fails_closed_on_input_it_cannot_read(
    stdin: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert guard_bash.main(io.StringIO(stdin)) == 2
    assert "cannot read the hook input" in capsys.readouterr().err
