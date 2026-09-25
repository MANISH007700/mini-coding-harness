"""Slash commands. Anything typed starting with / lands here."""

from manish_code import compact as compaction
from manish_code import config
from manish_code import session
from manish_code.permissions import sandbox
from manish_code.ui import ui

COMMANDS = {
    "/rewind": "jump back to an earlier point in this chat",
    "/sessions": "open a past chat",
    "/compact": "summarise the history so far and free up the context window",
}


def preview(message):
    if message.get("tool_calls"):
        return "-> " + message["tool_calls"][0]["function"]["name"]
    return " ".join(str(message.get("content") or "").split())[:70]


def redraw(messages, label):
    """The screen no longer matches the history, so wipe it and draw again."""
    ui.clear()
    ui.banner(config.MODEL, sandbox.name())
    ui.resumed(messages, label)
    ui.replay(messages)
    return messages


def rewind(messages):
    rows = [f"{m['role']:<9} {preview(m)}" for m in messages]
    choice = ui.pick("rewind to", rows)
    if choice is None:
        return messages
    session.rewind_to(choice + 1)
    return redraw(messages[: choice + 1], "rewound")


def sessions(messages):
    saved = session.all_sessions()
    if not saved:
        ui.note("no saved chats yet")
        return messages
    rows = [f"{s['id']}  {s['title']}" for s in saved]
    choice = ui.pick("open chat", rows)
    if choice is None:
        return messages

    return redraw(session.open_session(saved[choice]["id"]), "opened")


def compact(messages):
    before = len(messages)
    try:
        with ui.thinking("compacting"):
            compacted = compaction.compact(messages)
    except Exception as failure:  # noqa: BLE001
        # Compaction is one more API call, and it fires when the window is
        # nearly full - the worst moment to lose the session over a rate limit.
        ui.note(f"compaction failed ({type(failure).__name__}); transcript kept as is")
        return messages
    if len(compacted) == before:
        ui.note("nothing old enough to compact yet")
        return messages
    session.compacted(compacted)
    ui.compacted(before, compacted)
    return compacted


def handle(command, messages):
    if command == "/compact":
        return compact(messages)
    if command == "/rewind":
        return rewind(messages)
    if command == "/sessions":
        return sessions(messages)
    ui.note("\n".join(f"{name}  -  {help}" for name, help in COMMANDS.items()))
    return messages
