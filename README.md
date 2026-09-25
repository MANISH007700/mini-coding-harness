# mini-coding-harness

A minimal terminal coding agent: an LLM loop with tools, skills and a small Rich UI.

## Layout

- `llm.py` - OpenAI-compatible client (OpenRouter by default) and the system prompt.
- `agent/agent.py` - the agent loop: calls the model, runs requested tools, repeats until the model answers.
- `context.py` - late injection: an `<env>` block (time, git branch) plus a list of files changed since the last model call, appended after the history on every request but never stored in it, so the cached prefix is untouched.
- `tools/tools.py` - tools (`bash`, `read_file`, `write_file`, `read_skill`, `math_tool`, `write_todos`) and their schemas.
- `tools/todo.py` - the plan: `write_todos` replaces the whole list (one task `in_progress` at most); it is re-injected every turn inside `<todos>` and drives the spinner label.
- `skills/` - one folder per skill with a `SKILL.md` (frontmatter `name` + `description`); loaded on demand via `read_skill`.
- `ui/ui.py` - terminal rendering.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # then fill in OPENROUTER_API_KEY
python agent/agent.py
```

Logs go to `agent.log` in the current directory.

## Adding a skill

Create `skills/<name>/SKILL.md`:

```markdown
---
name: <name>
description: <when the agent should use it>
---

<instructions>
```
