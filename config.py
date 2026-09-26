import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# Models tried in order of priority (index 0 = best/primary, subsequent = fallbacks from best to worst)
# Only Gemini 3+ models from https://ai.google.dev/gemini-api/docs/models
DEFAULT_GEMINI_MODELS = [
    # --- Tier 1: Pro & Deep Reasoning (Highest Quality) ---
    "gemini-3.1-pro-preview",

    # --- Tier 2: Flash Workhorses (High Performance & Speed) ---
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3-flash-preview",

    # --- Tier 3: Flash-Lite (Lightweight & Rapid Fallback) ---
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
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

