"""Subagents: exploration that happens somewhere else.

A subagent is a whole agent loop with its own message list. That list is never
shown to the main agent and never outlives the call - the only thing that
crosses back is the final report.

Exploring a repo burns tens of thousands of tokens of tool output to produce a
few hundred tokens of answer. compact.py throws context away after it has been
spent; a subagent spends it somewhere that gets thrown away by design, so the
main transcript never pays for the difference at all.

Four rules, and the code below is really just these:

  1. it starts from an empty history          (no memory of anything)
  2. it holds every tool but a few            (no recursion, no plan, no edits)
  3. it runs the same loop as the main agent  (nothing special happens here)
  4. only its last message comes back         (the rest is discarded)
"""

import logging
import os

logger = logging.getLogger("agent.subagent")

MAX_TURNS = 12  # a runaway explorer is worse than a missing answer

# --- rule 2 -----------------------------------------------------------------
# `task` would let a subagent spawn subagents, forever. `write_todos` writes to
# the main agent's plan. The edit tools are withheld so "read only" is
# structural, not just a request in the prompt.
WITHHELD = {"task", "write_todos", "write_file", "str_replace"}


SYSTEM_PROMPT = f"""
You are an exploration subagent of Manish Code. You were given one question by
a lead agent and you answer it. That is the whole job.

You cannot see the conversation that spawned you, and the lead agent cannot
see anything you do here. Only your final message crosses back, so it has to
stand on its own.

You are working in {os.getcwd()}. Search inside it. Never search from / or
from the home directory - that scans the whole machine and will time out.

How to work:
- Use bash, read_file and read_skill to find out what is actually true.
  Prefer rg, grep and find to guessing where things live.
- You are here to read and report, not to change anything. Do not run
  commands with side effects.
- Search in batches. Several greps in one turn beats one grep per turn.
- Stop as soon as you can answer. Do not keep looking to be thorough.

Your final message is the entire report, and it is the only thing that costs
the lead agent anything - so keep it short. Aim for under 150 words. Findings
only: file paths with line numbers, names, values. No preamble, no restating
the question, no long code blocks - cite the path and line and let the lead
agent open it. Say plainly what you could not find; a gap is useful, a guess
is not.
"""


def toolset():
    """Every tool except the ones a guest should not hold."""
    from manish_code.tools.tools import TOOL_SCHEMAS

    return [s for s in TOOL_SCHEMAS if s["function"]["name"] not in WITHHELD]


def task(description: str) -> str:
    """Run a fresh agent on one question and return only its final answer."""
    # Imported here, not at the top: llm imports tools, and tools imports us.
    from manish_code.history import fit
    from manish_code.llm import call_llm
    from manish_code.tools.tools import execute
    from manish_code.ui import ui

    # --- rule 1 --- a list born here that dies at the return statement.
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": description},
    ]
    ui.subagent(description)
    logger.info("[Subagent Start] %s", description)

    report = None  # newest thing it has said, kept in case we run out of turns

    # --- rule 3 --- the same call / append / run tools / append loop as agent.py.
    for _ in range(MAX_TURNS):
        fit(messages)  # its context can overflow too, and nobody compacts it

        with ui.thinking("subagent exploring"):
            message, usage = call_llm(messages, tools=toolset())

        messages.append(message.model_dump(exclude_none=True))
        ui.usage(usage)
        report = message.content or report

        # --- rule 4 --- no tool calls means it is answering; the rest is dropped.
        if not message.tool_calls:
            logger.info("[Subagent Report]\n%s", report)
            return report or "(the subagent came back with nothing)"

        for tool_call in message.tool_calls:
            # Same executor as the main loop: same permissions, same sandbox.
            args, result, error = execute(tool_call)
            ui.tool(tool_call.function.name, args, result, error, nested=True)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })

    # Out of turns. A partial finding still beats starting the search over.
    if report:
        return (
            f"(stopped after {MAX_TURNS} turns, before finishing. Partial "
            f"findings below - narrow the question and ask again.)\n\n{report}"
        )
    return f"(stopped after {MAX_TURNS} turns with nothing to report.)"


TASK_SCHEMA = {
    "type": "function",
    "function": {
        "name": "task",
        "description": (
            "Hand a self-contained exploration question to a fresh agent that "
            "has its own context window, and get back its findings. Use this "
            "to learn how the codebase works - tracing behaviour, locating "
            "where something is implemented, surveying files - so the search "
            "costs you one answer instead of dozens of tool results. It cannot "
            "see this conversation, so include every detail it needs. It reads "
            "and reports; it never edits. Do your own editing."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": (
                        "The question, written to stand alone: what to find "
                        "out, where to start looking, and what the answer "
                        "should contain."
                    ),
                }
            },
            "required": ["description"],
        },
    },
}
