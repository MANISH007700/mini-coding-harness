import os

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from tools.todo import MARKS

console = Console()
TODO_STYLES = {"done": "dim strike", "in_progress": "bold magenta", "pending": "dim"}
MAX_RESULT_LINES = 8


def _row(mark, mark_style, body):
    """Print `body` with a hanging marker, so wrapped lines stay indented."""
    grid = Table.grid(padding=(0, 1))
    grid.add_column(no_wrap=True)
    grid.add_column()
    grid.add_row(Text(mark, style=mark_style), body)
    console.print(grid)


def banner(model):
    body = Text.assemble(
        ("✻ ", "bold magenta"), ("Manish Code", "bold"), "\n\n",
        ("model  ", "dim"), model or "unknown", "\n",
        ("cwd    ", "dim"), os.getcwd(),
    )
    console.print(Panel(body, border_style="magenta", expand=False, padding=(0, 2)))
    console.print(Text("  enter to send · empty line or ctrl+c to quit", style="dim"))


def prompt():
    console.print()
    return console.input("[bold magenta]❯[/] ")


def thinking(label="Thinking…"):
    return console.status(Text(label, style="dim"), spinner="dots")


def assistant(text):
    console.print()
    _row("⏺", "bold green", Markdown(text))


def injection(text):
    console.print()
    console.print(Panel(
        Text(text.strip(), style="dim"),
        title=Text("late injection", style="italic dim"),
        title_align="left",
        border_style="dim",
        expand=False,
        padding=(0, 1),
    ))


def todos(items):
    """The plan as a checklist. The raw tool output is never worth showing."""
    done = sum(1 for t in items if t["status"] == "done")
    console.print()
    _row("⏺", "bold cyan", Text(f"todos {done}/{len(items)}", style="bold"))
    for t in items:
        style = TODO_STYLES[t["status"]]
        _row("  " + MARKS[t["status"]], style, Text(t["content"], style=style))


def tool(name,args, result, error=False):
    if name == "write_todos" and not error and args.get("todos"):
        return todos(args["todos"])
    shown = args.get("command") or args.get("path") or ", ".join(f"{k}={v!r}" for k, v in args.items())
    console.print()
    _row("⏺", "bold red" if error else "bold cyan", Text.assemble((name, "bold"), f"({shown})"))

    lines = str(result).rstrip().splitlines() or ["(no output)"]
    body = "\n".join(lines[:MAX_RESULT_LINES])
    if len(lines) > MAX_RESULT_LINES:
        body += f"\n… +{len(lines) - MAX_RESULT_LINES} lines"
    _row("  ⎿", "dim", Text(body, style="red" if error else "dim"))


def usage(u):
    parts = [f"{u.get('prompt_tokens')} in", f"{u.get('completion_tokens')} out"]
    if u.get("reasoning_tokens"):
        parts.append(f"{u['reasoning_tokens']} reasoning")
    if u.get("cached_tokens"):
        parts.append(f"{u['cached_tokens']} cached")
    console.print(Text(" · ".join(parts), style="dim"), justify="right")


def goodbye():
    console.print(Text("\n  bye 👋", style="dim"))
