"""Late injection: a small block appended just before we send.

It goes at the END of the message list and is never stored in `messages`,
so the stable prefix in front of it stays cached.
"""

import hashlib
import logging
import subprocess
from datetime import datetime
from pathlib import Path

from manish_code.tools.todo import todos_prompt

# Create a logger that inherits settings from the main "agent" logger
logger = logging.getLogger("agent.context")

LABELS = {"M": "modified", "D": "deleted", "A": "added", "??": "new"}


def git(*args):
    result = subprocess.run(["git", *args], capture_output=True, text=True)
    return result.stdout


def file_hash(path):
    file = Path(path)
    return hashlib.md5(file.read_bytes()).hexdigest() if file.is_file() else None


def git_state():
    """path -> (status, content hash) for every file git sees as changed."""
    state = {}
    lines = git("status", "--porcelain").splitlines()
    logger.debug("git status --porcelain returned %d lines", len(lines))
    for line in lines:
        if len(line) < 4:
            continue
        path = line[3:]
        state[path] = (line[:2].strip(), file_hash(path))
    return state


LAST_STATE = git_state()


def file_changes():
    """Files whose status or contents moved since the previous turn."""
    global LAST_STATE
    now = git_state()
    changed = {p: v[0] for p, v in now.items() if LAST_STATE.get(p) != v}
    if changed:
        logger.info("Detected file changes since last turn: %s", changed)
    else:
        logger.debug("No file changes detected since last turn.")
    LAST_STATE = now
    return changed


def changes_note():
    changed = file_changes()
    if not changed:
        return ""
    lines = [f"{LABELS.get(code, code)}: {path}" for path, code in changed.items()]
    return (
        "\n<system-reminder>\n"
        "These files changed since your last turn. Read them again before "
        "editing:\n" + "\n".join(lines) + "\n</system-reminder>"
    )


def todos_note():
    plan = todos_prompt()
    return f"\n<todos>\n{plan}\n</todos>" if plan else ""


def reminder():
    """The block we append to the messages on every model call."""
    branch = git("branch", "--show-current").strip() or "(detached)"
    time_str = f"{datetime.now():%Y-%m-%d %H:%M}"
    logger.info("Generating reminder block (time: %s, branch: %s)", time_str, branch)
    return {
        "role": "user",
        "content": (
            "<env>\n"
            f"time: {time_str}\n"
            f"git branch: {branch}\n"
            "</env>" + todos_note() + changes_note()
        ),
    }
