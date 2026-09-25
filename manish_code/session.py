"""Transcripts on disk. One JSONL file per chat, under ~/.manish-code/sessions/."""

import json
from datetime import datetime
from pathlib import Path

from manish_code import config

PROJECT = str(Path.cwd().resolve()).replace("/", "-")
SESSION_DIR = config.HOME / "sessions" / PROJECT
CURRENT = datetime.now().strftime("%Y%m%d-%H%M%S")
WRITTEN = 0  # how many messages are already on disk


def path_for(session_id):
    return SESSION_DIR / f"{session_id}.jsonl"


def save(messages):
    """Append what is new. Never rewrite what is already on disk."""
    global WRITTEN
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    with path_for(CURRENT).open("a") as f:
        for message in messages[WRITTEN:]:
            f.write(json.dumps(message) + "\n")
    WRITTEN = len(messages)


def rewind_to(count):
    """Record a rewind as an entry, so the old messages stay in the file."""
    global WRITTEN
    with path_for(CURRENT).open("a") as f:
        f.write(json.dumps({"rewind_to": count}) + "\n")
    WRITTEN = count


def compacted(messages):
    """Compaction rewrites history, so record the result and start from it."""
    global WRITTEN
    with path_for(CURRENT).open("a") as f:
        f.write(json.dumps({"compacted": messages}) + "\n")
    WRITTEN = len(messages)


def load(session_id):
    """Replay the log: messages accumulate, rewinds cut them back."""
    messages = []
    for line in path_for(session_id).read_text().splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            # A half-written last line, usually from a kill mid-save. Skipping
            # it costs one message; raising would break /sessions for every
            # chat in the project, because listing them all calls load().
            continue
        if "rewind_to" in entry:
            del messages[entry["rewind_to"]:]
        elif "compacted" in entry:
            messages = list(entry["compacted"])
        else:
            messages.append(entry)
    return messages


def open_session(session_id):
    """Switch to a past chat and become it."""
    global CURRENT, WRITTEN
    CURRENT = session_id
    messages = load(session_id)
    WRITTEN = len(messages)
    return messages


def title(messages):
    for message in messages:
        if message["role"] == "user":
            return " ".join(str(message.get("content") or "").split())[:60]
    return "(empty)"


def all_sessions():
    """Newest first."""
    if not SESSION_DIR.exists():
        return []
    files = sorted(
        SESSION_DIR.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    return [{"id": p.stem, "title": title(load(p.stem))} for p in files]
