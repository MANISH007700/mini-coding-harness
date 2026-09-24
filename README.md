# mini-coding-harness

A minimal terminal coding agent: an LLM loop with tools, skills and a small Rich UI.

## Layout

- `llm.py` - OpenAI-compatible client (OpenRouter by default) and the system prompt.
- `agent/agent.py` - the agent loop: calls the model, runs requested tools, repeats until the model answers.
- `tools/tools.py` - tools (`bash`, `read_file`, `write_file`, `read_skill`, `math_tool`) and their schemas.
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
