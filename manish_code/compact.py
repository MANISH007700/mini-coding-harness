"""The compaction agent.

A second agent with one job: read a transcript that has grown too big and
write the handoff note a fresh agent would need to carry on.

The result replaces the messages it summarised, so this is the only place in
the codebase that throws information away for good. It runs rarely and cuts
deep - trimming just enough to fit would put us back over the line next turn,
and every trim costs the whole prompt cache.
"""

from manish_code import config
from manish_code.history import estimate, strip
from manish_code.llm import client

SYSTEM_PROMPT = """
You are compacting the transcript of a coding session. The session is out of
context window. Write the handoff note that lets a fresh agent pick the work up
without re-reading anything.

Use these sections, in this order. Skip any that would be empty.

## Goal
What the user asked for. Quote them where the exact wording matters.

## What happened
Decisions taken and the reasoning behind them. Include approaches that were
tried and abandoned, and why - those are the expensive lessons, and an agent
without them will try the same dead end again.

## Files
Every file touched: path, and what changed in it.

## State
What works, what is broken, what was left half-finished.

## Next
The immediate next step.

Rules:
- Be specific. Real paths, function names, error text, exact commands.
- Keep anything the user explicitly asked for, corrected, or rejected.
- Never invent progress. If something was not finished, say it was not.
- No preamble and no sign-off. Start at the first heading.
"""

HANDOFF = """<summary>
Everything before this point has been compacted out of the context window to
free up room. This is the record of it - treat it as your own memory of the
work so far, not as something the user told you.

{summary}
</summary>"""


def needed(usage):
    """Has the last request grown past the point where we rebuild?"""
    return usage["prompt_tokens"] > config.CONTEXT_WINDOW * config.COMPACT_AT


ROLES = {"user": "USER", "assistant": "ASSISTANT", "tool": "TOOL RESULT"}


def render(messages):
    """Flatten the transcript into something the summariser can read."""
    lines = []
    for message in messages:
        if message["role"] == "system":
            continue

        content = message.get("content") or ""
        for call in message.get("tool_calls") or []:
            function = call["function"]
            content += f"\n[called {function['name']}: {function['arguments']}]"

        lines.append(f"{ROLES.get(message['role'], message['role'])}: {content}")
    return "\n\n".join(lines)


def summarize(messages):
    """One LLM call, no tools. Returns the handoff note."""
    response = client().chat.completions.create(
        model=config.MODEL,
        max_tokens=config.MAX_TOKENS,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": render(messages)},
        ],
    )
    return response.choices[0].message.content


def safe_boundary(messages, start):
    """First index at or after `start` where cutting cannot orphan a tool call.

    A tool result has to keep the assistant message that asked for it, so the
    only safe cut points are the messages that open a fresh exchange.
    """
    for index in range(max(start, 1), len(messages)):
        previous = messages[index - 1]
        if messages[index]["role"] == "tool" or previous.get("tool_calls"):
            continue
        return index
    return len(messages)


def tail_start(messages, budget):
    """Walk back from the end, taking messages until the tail fills `budget`."""
    total = 0
    for index in range(len(messages) - 1, 0, -1):
        total += estimate([messages[index]])
        if total > budget:
            return safe_boundary(messages, index)
    return safe_boundary(messages, 1)


def compact(messages):
    """system + summary + a recent tail. The caller freezes what comes back."""
    cut = tail_start(messages, config.CONTEXT_WINDOW * config.COMPACT_TO)
    if cut <= 1:
        return messages  # nothing old enough to be worth summarising

    summary = summarize(messages[1:cut])
    kept = [
        messages[0],
        {"role": "user", "content": HANDOFF.format(summary=summary)},
        *messages[cut:],
    ]

    # Shrink the retained tail now, while we are already paying for a rebuilt
    # prefix. Stripping is idempotent, so from here the frozen block is final
    # and stays byte-identical - and cached - until the next compaction.
    strip(kept)
    return kept
