import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not BOT_TOKEN:
    # We will print a clear message, but let's let the bot run and raise/fail with a helpful message
    print("==================================================================")
    print("WARNING: TELEGRAM_BOT_TOKEN is not set in environment or .env file!")
    print("Please create a .env file with: TELEGRAM_BOT_TOKEN=your_token_here")
    print("==================================================================")
