"""The tools the model can call, their schemas, and the executor that runs them."""

import json
import logging
import re
import subprocess

from manish_code import history
from manish_code.permissions import sandbox
from manish_code.permissions.permissions import check
from manish_code.skills.skills import read_skill, skills_prompt
from manish_code.tools.subagent import TASK_SCHEMA, task
from manish_code.tools.todo import TODO_SCHEMA, write_todos

logger = logging.getLogger("agent.tools")


def bash(command: str) -> str:
    """Run a shell command in the sandbox and return its combined stdout and stderr."""
    try:
        result = sandbox.run(command)
    except subprocess.TimeoutExpired as expired:
        return (
            f"Timed out after {expired.timeout}s and was killed. "
            "Narrow it down - search inside the working directory rather than /."
        )
    return history.cap((result.stdout + result.stderr) or "(no output)")


def read_file(path: str) -> str:
    """Read a file and return its contents."""
    with open(path) as file:
        return history.cap(file.read())


def write_file(path: str, content: str) -> str:
    """Write content to a file, replacing what was there."""
    with open(path, "w") as file:
        file.write(content)
    return f"Wrote {len(content)} characters to {path}"


def str_replace(path: str, old_str: str, new_str: str, allow_multi_edit: bool = False) -> str:
    """Swap exact text in a file. old_str must match exactly once."""
    with open(path) as file:
        content = file.read()

    count = content.count(old_str)
    if count == 0:
        return f"Error: old_str was not found in {path}"
    if count > 1 and not allow_multi_edit:
        return (
            f"Error: old_str matches {count} times in {path}. "
            "Add surrounding lines to make it unique, "
            "or set allow_multi_edit to replace them all."
        )

    with open(path, "w") as file:
        file.write(content.replace(old_str, new_str))
    return f"Replaced {count} match(es) in {path}"


def math_tool(expression: str) -> str:
    """Evaluate an arithmetic expression. Only digits, operators and parentheses."""
    if not re.match(r"^[0-9.+\-*/%() ]+$", expression):
        return "Error: Expression contains unsupported characters or unsafe operations."
    try:
        return str(eval(expression, {"__builtins__": None}, {}))
    except Exception as e:
        return f"Error evaluating expression: {e}"


def function(name, description, properties, required):
    """One OpenAI-style tool schema."""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


TOOL_SCHEMAS = [
    function(
        "bash",
        "Run a shell command and return its combined stdout and stderr.",
        {"command": {"type": "string", "description": "The shell command to run"}},
        ["command"],
    ),
    function(
        "read_file",
        "Read a file and return its contents.",
        {"path": {"type": "string", "description": "The path to the file to read"}},
        ["path"],
    ),
    function(
        "write_file",
        "Write content to a file, replacing what was there.",
        {
            "path": {"type": "string", "description": "The path to the file to write"},
            "content": {"type": "string", "description": "The content to write to the file"},
        },
        ["path", "content"],
    ),
    function(
        "str_replace",
        "Replace exact text in a file. old_str must appear exactly once, "
        "so include surrounding lines if needed.",
        {
            "path": {"type": "string", "description": "File to edit"},
            "old_str": {"type": "string", "description": "Exact text to find"},
            "new_str": {"type": "string", "description": "Text to put in its place"},
            "allow_multi_edit": {
                "type": "boolean",
                "description": "Replace every match instead of failing",
            },
        },
        ["path", "old_str", "new_str"],
    ),
    function(
        "read_skill",
        "Load the full instructions for a skill. Call it before starting a task "
        "that matches a skill below, then follow what it returns.\n\n"
        "Available skills:\n" + skills_prompt(),
        {"name": {"type": "string", "description": "The skill to load"}},
        ["name"],
    ),
    function(
        "math_tool",
        "Evaluate an arithmetic expression. Supports +, -, *, /, %, ** and parentheses.",
        {"expression": {"type": "string", "description": "The expression, e.g. '34 + 73'"}},
        ["expression"],
    ),
    TODO_SCHEMA,
    TASK_SCHEMA,
]

TOOLS = {
    "bash": bash,
    "read_file": read_file,
    "write_file": write_file,
    "str_replace": str_replace,
    "read_skill": read_skill,
    "math_tool": math_tool,
    "write_todos": write_todos,
    "task": task,
}

# Appended to every denied or blocked call, so a "no" ends that line of attack.
STOP = (
    "Do not retry it and do not try another command, tool or script to get "
    "the same result. Stop and ask the user how they want to proceed."
)


def execute(tool_call):
    """Run one tool call through the permission layer. Returns (args, result, error).

    Shared by the main loop and by subagents, so a subagent is fenced in by
    exactly the same rules. A tool call is text the model wrote, so the name,
    the JSON and the arguments are all untrusted: every failure comes back as
    a result the model can read, never as a crash.
    """
    from manish_code.ui import ui

    name = tool_call.function.name
    logger.info("[Tool Call Request] Name: '%s' | Call ID: %s\nArguments: %s",
                name, tool_call.id, tool_call.function.arguments)
    try:
        args = json.loads(tool_call.function.arguments)
    except json.JSONDecodeError as broken:
        return {}, f"Error: arguments were not valid JSON ({broken}).", True

    if name not in TOOLS:
        return args, f"Error: no tool named '{name}'. Available: {', '.join(TOOLS)}.", True

    try:
        action, reason = check(name, args)
        if action == "deny":
            logger.warning("[Tool Blocked] %s", reason)
            return args, f"Blocked by policy: {reason}. {STOP}", True
        if action == "ask" and not ui.approve(reason):
            logger.info("[Tool Denied By User] %s", reason)
            return args, f"The user denied this tool call. {STOP}", True
        result = str(TOOLS[name](**args))
        logger.info("[Tool Execution Success] Name: '%s'\nResult:\n%s", name, result)
        return args, result, False
    except TypeError as mismatch:
        result = f"Error: wrong arguments for {name} ({mismatch})."
    except KeyError as missing:
        result = f"Error: {name} needs an argument you did not send: {missing}."
    except Exception as failure:  # noqa: BLE001 - the model gets to see and retry
        result = f"Error: {name} failed - {type(failure).__name__}: {failure}"
    logger.error("[Tool Execution Failed] Name: '%s' | %s", name, result)
    return args, result, True
