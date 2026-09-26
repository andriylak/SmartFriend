import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# Models tried in order of priority (index 0 = best/primary, subsequent = fallbacks from best to worst)
DEFAULT_GEMINI_MODELS = [
    # --- Tier 1: Pro & Deep Reasoning (Best quality) ---
    "gemini-2.5-pro",
    "gemini-1.5-pro",

    # --- Tier 2: Flash Workhorses (High performance & speed) ---
    "gemini-2.5-flash",
    "gemini-3.6-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-flash-latest",

    # --- Tier 3: Flash-Lite & Fast Fallbacks (Lightweight & high throughput) ---
    "gemini-3.1-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-1.5-flash-8b",
]

env_models = os.getenv("GEMINI_MODELS")
if env_models:
    GEMINI_MODELS = [m.strip() for m in env_models.split(",") if m.strip()]
else:
    GEMINI_MODELS = DEFAULT_GEMINI_MODELS

# Backwards compatibility aliases
MODEL_NAME = GEMINI_MODELS[0]
FALLBACK_MODELS = GEMINI_MODELS[1:]
FALLBACK_MODEL_NAME = GEMINI_MODELS[1] if len(GEMINI_MODELS) > 1 else GEMINI_MODELS[0]
GEMINI_MAX_RETRIES = int(os.getenv("GEMINI_MAX_RETRIES", "5"))


if not BOT_TOKEN:
    # We will print a clear message, but let's let the bot run and raise/fail with a helpful message
    print("==================================================================")
    print("WARNING: TELEGRAM_BOT_TOKEN is not set in environment or .env file!")
    print("Please create a .env file with: TELEGRAM_BOT_TOKEN=your_token_here")
    print("==================================================================")

