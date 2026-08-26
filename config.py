import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = "gemini-3.6-flash"  # Default primary model
FALLBACK_MODEL_NAME = "gemini-3.1-flash-lite"  # Primary fallback model
FALLBACK_MODELS = [
    "gemini-3.1-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-flash-latest"
]  # Ordered fallback models to try if primary model fails


if not BOT_TOKEN:
    # We will print a clear message, but let's let the bot run and raise/fail with a helpful message
    print("==================================================================")
    print("WARNING: TELEGRAM_BOT_TOKEN is not set in environment or .env file!")
    print("Please create a .env file with: TELEGRAM_BOT_TOKEN=your_token_here")
    print("==================================================================")

