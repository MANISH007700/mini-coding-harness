"""Which tool calls need a human.

The sandbox decides what is *possible*. These rules only decide what is worth
interrupting you for - so read-only commands run silently, and the risky ones
still stop and ask.
"""

import re
import shlex
from fnmatch import fnmatch
from pathlib import Path

PROJECT = Path.cwd().resolve()

# Last matching rule wins, so put the catch-all first.
BASH_RULES = {
    "*": "ask",
    # read-only: let them through
    "ls*": "allow",
    "pwd": "allow",
    "cd *": "allow",
    "echo *": "allow",
    "cut *": "allow",
    "basename *": "allow",
    "dirname *": "allow",
    "date": "allow",
    "env": "allow",
    "cat *": "allow",
    "head *": "allow",
    "tail *": "allow",
    "wc *": "allow",
    "which *": "allow",
    "grep *": "allow",
    "rg *": "allow",
    "find *": "allow",
    "git status*": "allow",
    "git diff*": "allow",
    "git log*": "allow",
    "git show*": "allow",
    "git ls-files*": "allow",
    "git branch": "allow",
    "git branch -a": "allow",
    "git branch --show-current": "allow",
    "pytest*": "allow",
    "python -m pytest*": "allow",
    "python3 -m pytest*": "allow",
    # risky: never, even if the user says yes
    "rm *": "deny",
    "sudo *": "deny",
    "chmod *": "deny",
    "chown *": "deny",
    "curl *": "deny",
    "wget *": "deny",
    "git push*": "deny",
    "git reset*": "deny",
    "git clean*": "deny",
    "cat .env*": "deny",  # the OpenRouter key lives there
}

# An "allow" rule only means "this command is read-only". These turn any
# command into one that writes or runs something else, so they force "ask".
UNSAFE = re.compile(r"[<>`]|\$\(")  # redirection, command substitution

# Flags that make an otherwise read-only command write files or run commands.
WRITE_FLAGS = {
    "find": ("-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprint", "-fprint0", "-fprintf", "-fls"),
    "rg": ("--pre",),
    "git": ("--output",),
}


def writes(part):
    """Does this single command write or execute despite matching an allow rule?"""
    if UNSAFE.search(part):
        return True
    try:
        tokens = shlex.split(part)
    except ValueError:
        return True  # unbalanced quotes: cannot tell, so do not trust it
    flags = WRITE_FLAGS.get(tokens[0], ()) if tokens else ()
    return any(t == f or t.startswith(f + "=") for t in tokens for f in flags)


def split_command(command):
    """Split a compound command on the separators that actually separate.

    A naive split on | and ; also cuts inside quotes, so `rg "cap|max"` breaks
    into fragments that match no rule and fall through to "ask". Anything
    quoted or backslash-escaped is an argument, not a separator.
    """
    parts, current, quote = [], [], None
    index = 0
    while index < len(command):
        char = command[index]
        if quote:
            current.append(char)
            quote = None if char == quote else quote
        elif char == "\\":
            current.append(char)
            index += 1
            if index < len(command):
                current.append(command[index])
        elif char in "\"'":
            quote = char
            current.append(char)
        elif char in "&|;\n":
            parts.append("".join(current))
            current = []
            while index + 1 < len(command) and command[index + 1] in "&|":
                index += 1
        else:
            current.append(char)
        index += 1

    parts.append("".join(current))
    return [part.strip() for part in parts if part.strip()]


def decide(command):
    """Rate every part of a compound command; the strictest verdict wins."""
    verdicts = []
    for part in split_command(command):
        action = "ask"
        for pattern, rule in BASH_RULES.items():
            if fnmatch(part, pattern):
                action = rule
        if action == "allow" and writes(part):
            action = "ask"
        verdicts.append(action)

    for strictest in ("deny", "ask"):
        if strictest in verdicts:
            return strictest
    return "allow"


def inside_project(path):
    return PROJECT in Path(path).resolve().parents


def check(name, args):
    """Return (action, reason). Action is allow, ask or deny."""
    if name == "bash":
        return decide(args["command"]), f"run: {args['command']}"

    if name in ("write_file", "str_replace") and Path(args["path"]).name.startswith(".env"):
        return "deny", f"{name} on a secrets file: {args['path']}"

    if name in ("write_file", "str_replace") and not inside_project(args["path"]):
        return "ask", f"{name} outside {PROJECT}: {args['path']}"

    return "allow", None


if __name__ == "__main__":
    assert split_command('rg "cap|max" x && ls') == ['rg "cap|max" x', "ls"]
    assert decide("ls -la") == "allow"
    assert decide("git status && cat README.md") == "allow"
    assert decide("ls; rm -rf x") == "deny"
    assert decide("python3 script.py") == "ask"
    assert decide("cat .env") == "deny"
    assert check("write_file", {"path": "notes.txt"})[0] == "allow"
    assert check("write_file", {"path": "/etc/hosts"})[0] == "ask"
    assert check("write_file", {"path": ".env"})[0] == "deny"
    # read-only commands turned into writers must not run silently
    for sneaky in [
        "find .env -delete", "find . -name x -exec rm {} ;", "echo x > .env",
        "cat a > .env", "echo $(rm .env)", "ls `rm .env`", "git branch -D main",
        "rg --pre rm x .", "git diff --output=.env", "ls\nrm .env", "grep 'x",
    ]:
        assert decide(sneaky) != "allow", sneaky
    assert decide("ls\nrm .env") == "deny"
    assert decide("find . -name '*.py'") == "allow"
    assert decide("git branch --show-current") == "allow"
    print("permissions ok")
