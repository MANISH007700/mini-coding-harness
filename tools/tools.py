import json
import subprocess
import re

from skills.skills import SKILLS, skills_prompt, read_skill


def bash(command: str) -> str:
    """Run a shell command and return its combined stdout and stderr."""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired as expired:
        return f"Timed out after {expired.timeout}s and was killed. Narrow it down - search inside the working directory rather than /."
    return result.stdout + result.stderr

def read_file(path: str) -> str:
    """Read a file and return its contents."""
    with open(path, "r") as file:
        return file.read()

def write_file(path: str, content: str) -> str:
    """Write content to a file, replacing what was there."""
    with open(path, "w") as file:
        file.write(content)
    return f"Wrote {len(content)} characters to {path}"

def math_tool(expression: str) -> str:
    """Evaluate a mathematical expression safely."""
    # Restrict expression to basic math operators and numbers
    if not re.match(r"^[0-9.+\-*/%() ]+$", expression):
        return "Error: Expression contains unsupported characters or unsafe operations."
    try:
        result = eval(expression, {"__builtins__": None}, {})
        return str(result)
    except Exception as e:
        return f"Error evaluating expression: {e}"


TOOLS = {
    "bash": bash,
    "read_file": read_file,
    "write_file": write_file,
    "read_skill": read_skill,
    "math_tool": math_tool,
}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
        "name": "bash",
        "description": "Run a shell command and return its combined stdout and stderr.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to run",
                }
            },
            "required": ["command"],
            },
        }
    },
    {
        "type": "function",
        "function": {
        "name": "read_file",
        "description": "Read a file and return its contents.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The path to the file to read",
                }
            },
            "required": ["path"],
            },
        }
    },
    {
        "type": "function",
        "function": {
        "name": "write_file",
        "description": "Write content to a file, replacing what was there.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The path to the file to write",
                },
                "content": {
                    "type": "string",
                    "description": "The content to write to the file",
                }
            },
            "required": ["path", "content"],
            },
        }
    },
    {
        "type": "function",
        "function": {
        "name": "read_skill",
        "description": "Load the full instructions for a skill. Call it before starting a task that matches a skill below, then follow what it returns.\n\nAvailable skills:\n" + skills_prompt(),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The skill to load",
                }
            },
            "required": ["name"],
            },
        }
    },
    {
        "type": "function",
        "function": {
        "name": "math_tool",
        "description": "Evaluate a mathematical expression safely. Supports standard arithmetic operators: +, -, *, /, %, **, and parentheses.",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "The mathematical expression to evaluate, e.g., '34 + 73'",
                }
            },
            "required": ["expression"],
            },
        }
    },
]
