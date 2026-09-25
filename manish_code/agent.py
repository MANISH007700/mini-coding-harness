import argparse
import logging

import openai

# Configure logging to a file 'agent.log' in the current working directory
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("agent.log", encoding="utf-8"),
    ]
)
logger = logging.getLogger("agent")

from manish_code import commands
from manish_code import compact
from manish_code import config
from manish_code import history
from manish_code import session
from manish_code.context import reminder
from manish_code.llm import call_llm, SYSTEM_PROMPT
from manish_code.permissions import sandbox
from manish_code.tools.todo import active_form
from manish_code.tools.tools import execute
from manish_code.ui import ui


def main():
    parser = argparse.ArgumentParser(prog="manish-code", description="A minimal terminal coding agent.")
    parser.add_argument("--resume", action="store_true", help="continue the last session")
    parser.add_argument("--debug", action="store_true", help="show the late injection and raw model response")
    cli = parser.parse_args()
    if not (config.API_KEY and config.MODEL):
        parser.exit(1, (
            "manish-code: OPENROUTER_API_KEY and MODEL are not set.\n"
            f"Put them in ./.env or {config.HOME / 'env'} (see .env.example).\n"
        ))

    logger.info("=" * 80)
    logger.info("Agent Session Started")
    logger.info("Model: %s | Sandbox: %s", config.MODEL or "unknown", sandbox.name())
    logger.info("System Prompt:\n%s", SYSTEM_PROMPT)
    logger.info("=" * 80)

    ui.banner(config.MODEL, sandbox.name())
    # Inform the user about the log file
    print("  Logs are being recorded in agent.log\n")

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if cli.resume:
        saved = session.all_sessions()
        if saved:
            messages = session.open_session(saved[0]["id"])
            history.strip(messages)
            ui.resumed(messages)
            ui.replay(messages)
            logger.info("Resumed session %s (%d messages)", saved[0]["id"], len(messages))

    while True:
        user_input = ui.prompt()
        if not user_input:
            logger.info("Agent session ended (empty input or exit command received)")
            break

        if user_input.startswith("/"):
            logger.info("[Command] %s", user_input)
            messages = commands.handle(user_input, messages)
            session.save(messages)
            continue

        logger.info("[User Input] %s", user_input)
        messages.append({"role": "user", "content": user_input})

        # Keep calling the model until it answers without asking for a tool.
        while True:
            injection = reminder()
            logger.info("[Late Injection]\n%s", injection["content"])
            if cli.debug:
                ui.injection(injection["content"])

            dropped = history.fit(messages)
            if dropped:
                logger.warning("Dropped %d old tool results to fit the context window", dropped)
                ui.note("dropped old tool output to make this request fit")

            logger.info("[LLM Request] Calling LLM with %d messages...", len(messages))
            try:
                with ui.thinking(active_form()):
                    message, usage = call_llm(messages=messages + [injection])
            except openai.APIError as failure:
                # Out of credits, rate limited, network down: report it and hand
                # the prompt back instead of taking the session down.
                logger.error("[LLM Request Failed] %s", failure)
                ui.note(f"model call failed: {failure}")
                usage = None
                break

            messages.append(message.model_dump(exclude_none=True))
            session.save(messages)

            if cli.debug:
                ui.debug(message.model_dump(exclude_none=True))

            if message.content:
                logger.info("[LLM Response Content]\n%s", message.content)
                ui.assistant(message.content)

            logger.info(
                "[LLM Token Usage] Prompt: %s | Completion: %s | Reasoning: %s | Cached: %s",
                usage.get("prompt_tokens"),
                usage.get("completion_tokens"),
                usage.get("reasoning_tokens"),
                usage.get("cached_tokens"),
            )
            ui.usage(usage)

            if not message.tool_calls:
                break

            for tool_call in message.tool_calls:
                args, result, error = execute(tool_call)
                ui.tool(tool_call.function.name, args, result, error)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })
                session.save(messages)

        history.sweep()          # the turn is over: bin its temp files
        history.strip(messages)  # ...and shrink the tool output it produced

        if usage and compact.needed(usage):
            logger.info("Prompt at %s tokens, compacting", usage["prompt_tokens"])
            messages = commands.compact(messages)


def run():
    """Entry point for `manish-code` and `python -m manish_code`."""
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        logger.info("Agent session ended (KeyboardInterrupt or EOFError)")
    except Exception as e:
        logger.exception("Agent process crashed with unhandled exception: %s", str(e))
        raise
    ui.goodbye()
