"""Settings. Real environment variables win, then ./.env, then ~/.manish-code/env."""

import os
from pathlib import Path

import dotenv

# Sessions, input history, user-level skills and the fallback env file live here.
HOME = Path.home() / ".manish-code"

dotenv.load_dotenv(dotenv.find_dotenv(usecwd=True))
dotenv.load_dotenv(HOME / "env")

BASE_URL = os.getenv("BASE_URL", "https://openrouter.ai/api/v1")
API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = os.getenv("MODEL")
# Cap on each reply. OpenRouter reserves credit for this many tokens per request.
MAX_TOKENS = int(os.getenv("MAX_TOKENS", 8192))

# How much room the model has, and how we spend it.
CONTEXT_WINDOW = int(os.getenv("CONTEXT_WINDOW", 128_000))
COMPACT_AT = 0.85  # compact once the prompt crosses this much of the window
COMPACT_TO = 0.35  # and cut back to this much, so it does not retrigger soon
