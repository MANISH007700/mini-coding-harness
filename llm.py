import json
import os

from openai import OpenAI
from pydantic import config
import dotenv   
dotenv.load_dotenv()

from tools.tools import TOOLS, TOOL_SCHEMAS

client = OpenAI(
    base_url=os.getenv("BASE_URL"),
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

SYSTEM_PROMPT = f"""
You are a coding agent. Your job is to code. Always code.

# tools info
1 - Bash tool : use the bash tool to inspect files.

# planning
For any task that takes more than one step, call write_todos first and plan it
out. Send the whole list every time you call it - it replaces the old one.
Keep exactly one task in_progress, mark it done the moment it is finished, and
move the next one to in_progress in the same call. Do not batch up completions
at the end. Skip the tool entirely for single-step tasks; it is noise there.

The current list is injected back to you every turn inside <todos> tags, so
that block - not the transcript - is the truth about where you are.
"""

def call_llm(messages, tools=None):
    response = client.chat.completions.create(
        model=os.getenv("MODEL"),
        messages=messages,
        tools=tools or TOOL_SCHEMAS,
    )

    response_message = response.choices[0].message
    completion_details = response.usage.completion_tokens_details
    prompt_details = response.usage.prompt_tokens_details

    usage = {
        "prompt_tokens": response.usage.prompt_tokens,
        "completion_tokens": response.usage.completion_tokens,
        "reasoning_tokens": getattr(completion_details, "reasoning_tokens", None),
        "cached_tokens": getattr(prompt_details, "cached_tokens", None),
    }
    return response_message, usage

if __name__ == "__main__":
    user_input = input("Enter your prompt> ")
    message, usage = call_llm(  
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_input},
        ]
    )
    print("Agent: ", message.content, "\n")
    if message.tool_calls:
        tool_call = message.tool_calls[0]
        args = json.loads(tool_call.function.arguments)
        result = TOOLS[tool_call.function.name](**args)
        print(result, "\n")

    print(usage)