import json
import os

from rich.console import Console
from rich.json import JSON
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from manish_code.tools.todo import MARKS
from manish_code.ui import prompt as line

console = Console()
TODO_STYLES = {"done": "dim strike", "in_progress": "bold magenta", "pending": "dim"}
MAX_RESULT_LINES = 8
TOTALS = {}  # token usage summed over the session, shown on exit


def _row(mark, mark_style, body, indent=0):
    """Print `body` with a hanging marker, so wrapped lines stay indented."""
    grid = Table.grid(padding=(0, 1))
    if indent:
        grid.add_column(width=indent)
    grid.add_column(no_wrap=True)
    grid.add_column()
    grid.add_row(*([""] if indent else []), Text(mark, style=mark_style), body)
    console.print(grid)


def _panel(body, title, style="dim"):
    console.print()
    console.print(Panel(
        body,
        title=Text(title, style=f"italic {style}"),
        title_align="left",
        border_style=style,
        expand=False,
        padding=(0, 1),
    ))


# ---------------------------------------------------------------- input


def banner(model, sandbox_name="none"):
    body = Text.assemble(
        ("✻ ", "bold magenta"), ("Manish Code", "bold"), "\n\n",
        ("model    ", "dim"), model or "unknown", "\n",
        ("cwd      ", "dim"), os.getcwd(), "\n",
        ("sandbox  ", "dim"), sandbox_name,
    )
    console.print(Panel(body, border_style="magenta", expand=False, padding=(0, 2)))
    console.print(Text(
        "  enter to send · opt+enter for a newline · /help for commands · empty line or ctrl+d to quit",
        style="dim",
    ))


def prompt():
    console.print()
    try:
        return line.read().strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def approve(reason):
    console.print()
    _row("?", "bold yellow", Text(reason, style="bold yellow"))
    try:
        answer = line.read("  allow? (y/n) ").strip()
    except (EOFError, KeyboardInterrupt):
        return False
    return answer.lower().startswith("y")


def pick(title, rows):
    """Numbered list; returns the chosen index or None."""
    console.print()
    _row("⏺", "bold magenta", Text(title, style="bold"))
    for i, row in enumerate(rows):
        console.print(Text(f"  {i:>3}  {row}", style="dim"))
    try:
        answer = line.read("\n  number> ").strip()
    except (EOFError, KeyboardInterrupt):
        return None
    return int(answer) if answer.isdigit() and int(answer) < len(rows) else None


# --------------------------------------------------------------- output


def clear():
    console.clear()


def note(text):
    console.print()
    console.print(Text(text, style="dim"))


def resumed(messages, label="resumed"):
    turns = sum(1 for m in messages if m["role"] == "user")
    console.print(Text(f"  {label} · {len(messages)} messages · {turns} turns", style="dim"))


def replay(messages):
    """Redraw a loaded transcript so the screen matches the history."""
    results = {m["tool_call_id"]: m["content"] for m in messages if m["role"] == "tool"}
    for message in messages:
        if message["role"] == "user":
            user(message["content"])
        elif message["role"] == "assistant":
            if message.get("content"):
                assistant(message["content"])
            for call in message.get("tool_calls") or []:
                tool(
                    call["function"]["name"],
                    json.loads(call["function"]["arguments"]),
                    results.get(call["id"], ""),
                )


def user(text):
    console.print()
    _row("❯", "bold magenta", Text(text.strip(), style="bold"))


def thinking(label="Thinking…"):
    return console.status(Text(label, style="dim"), spinner="dots")


def assistant(text):
    console.print()
    _row("⏺", "bold green", Markdown(text))


def injection(text):
    _panel(Text(text.strip(), style="dim"), "late injection")


def debug(data):
    _panel(JSON.from_data(data), "raw response", "yellow")


def subagent(description):
    """Shown to you, never to the main agent - it only gets the report."""
    _panel(Text(description.strip(), style="dim"), "subagent · own context", "magenta")


def compacted(before, messages):
    summary = next(
        (m["content"] for m in messages if "<summary>" in (m.get("content") or "")),
        "",
    )
    body = Markdown(summary.replace("<summary>", "").replace("</summary>", ""))
    _panel(body, f"compacted · {before} → {len(messages)} messages", "yellow")


def todos(items):
    """The plan as a checklist. The raw tool output is never worth showing."""
    done = sum(1 for t in items if t["status"] == "done")
    console.print()
    _row("⏺", "bold cyan", Text(f"todos {done}/{len(items)}", style="bold"))
    for t in items:
        style = TODO_STYLES[t["status"]]
        _row("  " + MARKS[t["status"]], style, Text(t["content"], style=style))


def tool(name, args, result, error=False, nested=False):
    if name == "write_todos" and not error and args.get("todos"):
        return todos(args["todos"])
    indent = 4 if nested else 0
    shown = args.get("command") or args.get("path") or ", ".join(f"{k}={v!r}" for k, v in args.items())
    console.print()
    _row("⏺", "bold red" if error else "bold cyan", Text.assemble((name, "bold"), f"({shown})"), indent)

    lines = str(result).rstrip().splitlines() or ["(no output)"]
    body = "\n".join(lines[:MAX_RESULT_LINES])
    if len(lines) > MAX_RESULT_LINES:
        body += f"\n… +{len(lines) - MAX_RESULT_LINES} lines"
    _row("  ⎿", "dim", Text(body, style="red" if error else "dim"), indent)


def usage(u):
    for key, value in u.items():
        TOTALS[key] = TOTALS.get(key, 0) + (value or 0)
    parts = [f"{u.get('prompt_tokens')} in", f"{u.get('completion_tokens')} out"]
    if u.get("reasoning_tokens"):
        parts.append(f"{u['reasoning_tokens']} reasoning")
    if u.get("cached_tokens"):
        parts.append(f"{u['cached_tokens']} cached")
    console.print(Text(" · ".join(parts), style="dim"), justify="right")


def summary():
    """Session token totals, printed once on exit."""
    if not TOTALS:
        return
    table = Table.grid(padding=(0, 2))
    table.add_column(style="dim")
    table.add_column(style="bold magenta", justify="right")
    for key, value in TOTALS.items():
        table.add_row(key.replace("_", " "), f"{value:,}")
    console.print()
    console.print(table)


def goodbye():
    summary()
    console.print(Text("\n  bye 👋", style="dim"))
