import json
import logging
import os
import sys

# Configure logging to a file 'agent.log' in the current working directory
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("agent.log", encoding="utf-8"),
    ]
)
logger = logging.getLogger("agent")

# llm.py, tools/ and ui/ live one level up, in manish-code/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm import call_llm, SYSTEM_PROMPT
from tools.tools import TOOLS, TOOL_SCHEMAS
from ui import ui


def main():
    logger.info("=" * 80)
    logger.info("Agent Session Started")
    logger.info("Model: %s", os.getenv("MODEL") or "unknown")
    logger.info("System Prompt:\n%s", SYSTEM_PROMPT)
    logger.info("=" * 80)

    ui.banner(os.getenv("MODEL"))
    # Inform the user about the log file
    print("  Logs are being recorded in agent.log\n")

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    while True:
        user_input = ui.prompt()
        if not user_input:
            logger.info("Agent session ended (empty input or exit command received)")
            break

        logger.info("[User Input] %s", user_input)
        messages.append({"role": "user", "content": user_input})

        # Keep calling the model until it answers without asking for a tool.
        while True:
            logger.info("[LLM Request] Calling LLM with %d messages...", len(messages))
            with ui.thinking():
                message, usage = call_llm(messages=messages, tools=TOOL_SCHEMAS)
            
            messages.append(message.model_dump(exclude_none=True))

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
                args, error = {}, False
                logger.info(
                    "[Tool Call Request] Name: '%s' | Call ID: %s\nArguments: %s",
                    tool_call.function.name,
                    tool_call.id,
                    tool_call.function.arguments
                )
                try:
                    args = json.loads(tool_call.function.arguments)
                    result = TOOLS[tool_call.function.name](**args)
                except Exception as e:
                    result, error = f"Error: {e}", True
                    logger.exception(
                        "[Tool Exception] Name: '%s' | Error: %s",
                        tool_call.function.name,
                        str(e)
                    )

                if error:
                    logger.error(
                        "[Tool Execution Failed] Name: '%s' | Error result:\n%s",
                        tool_call.function.name,
                        result
                    )
                else:
                    logger.info(
                        "[Tool Execution Success] Name: '%s'\nResult:\n%s",
                        tool_call.function.name,
                        result
                    )

                ui.tool(tool_call.function.name, args, result, error)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": str(result),
                })


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        logger.info("Agent session ended (KeyboardInterrupt or EOFError)")
    except Exception as e:
        logger.exception("Agent process crashed with unhandled exception: %s", str(e))
        raise
    ui.goodbye()
