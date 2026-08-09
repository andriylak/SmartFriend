from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from keyboards import get_main_keyboard

router = Router()

@router.message(CommandStart())
@router.message(F.text == "ℹ️ Help")
@router.message(Command("help"))
async def cmd_start_or_help(message: Message, state: FSMContext):
    # Clear any active state
    await state.clear()
    
    welcome_text = (
        "👋 **Welcome to the Learning Companion Bot!**\n\n"
        "This bot is designed to help you study and retain knowledge using interactive flashcards/learning cards.\n\n"
        "**Available Features:**\n"
        "➕ **Create Card**: Create a new learning card with a question, answer, and optional category (default: 'General').\n"
        "📚 **My Cards**: View and delete your existing learning cards.\n"
        "🎯 **Study/Quiz**: Start a quiz. The bot will show a question, allow you to reveal the answer, and track your correct/incorrect attempts.\n"
        "❌ **Cancel**: You can type `/cancel` or tap \"❌ Cancel\" at any time to cancel the current setup/quiz.\n\n"
        "Use the menu below to get started!"
    )
    await message.answer(welcome_text, reply_markup=get_main_keyboard(), parse_mode="Markdown")

@router.message(Command("cancel"))
@router.message(F.text == "❌ Cancel")
@router.message(F.text.casefold() == "cancel")
async def cmd_cancel(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Nothing is currently active.", reply_markup=get_main_keyboard())
        return
        
    await state.clear()
    await message.answer("Action cancelled.", reply_markup=get_main_keyboard())
