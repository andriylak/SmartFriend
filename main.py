#!/usr/bin/env python3

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

import config
import database
from handlers import common, cards, quiz

async def main():
    # Setup logging to console
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    
    # 1. Initialize SQLite Database
    database.init_db()
    logging.info("Database initialized.")
    
    # 2. Check Bot Token
    if not config.BOT_TOKEN:
        logging.critical("Telegram Bot Token is missing! Exiting...")
        raise RuntimeError("Please define TELEGRAM_BOT_TOKEN in a .env file.")
        
    # 3. Setup Bot and Dispatcher
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    
    # 4. Include Handlers/Routers
    # Order matters: common router handles help, start and cancel commands.
    dp.include_router(common.router)
    dp.include_router(cards.router)
    dp.include_router(quiz.router)
    
    logging.info("Bot handlers registered. Starting polling...")
    
    # 5. Delete webhook to ensure no conflicts and start polling
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped.")
