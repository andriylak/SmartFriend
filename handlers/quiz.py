from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database
from keyboards import (
    get_main_keyboard,
    get_cancel_keyboard,
    get_categories_keyboard,
    get_reveal_keyboard,
    get_evaluation_keyboard,
)

router = Router()

class QuizStates(StatesGroup):
    selecting_category = State()
    studying = State()

@router.message(F.text == "🎯 Study/Quiz")
@router.message(Command("study"))
async def start_quiz(message: Message, state: FSMContext):
    user_id = message.from_user.id
    categories = database.get_user_categories(user_id)
    
    if not categories:
        await message.answer(
            "📭 You don't have any learning cards to study yet!\n\n"
            "Please create some cards first using **➕ Create Card**.",
            reply_markup=get_main_keyboard()
        )
        return
        
    await state.set_state(QuizStates.selecting_category)
    
    await message.answer(
        "🎯 **Study Mode**\n\n"
        "Please select a category you would like to study:",
        reply_markup=get_categories_keyboard(categories)
    )

@router.callback_query(QuizStates.selecting_category, F.data.startswith("quiz_cat_"))
async def select_category(callback: CallbackQuery, state: FSMContext):
    category_data = callback.data.split("quiz_cat_")[1]
    category = None if category_data == "all" else category_data
    
    await state.update_data(active_category=category)
    await state.set_state(QuizStates.studying)
    
    # Send a separate message with the first card and transition keyboard to 'Cancel'
    await callback.message.answer(
        f"🏁 Starting study session! Category: *{category if category else 'All'}*\n"
        "You can tap **❌ Cancel** at any time to end the session.",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )
    
    # Fetch first card
    await send_next_card(callback.message, callback.from_user.id, category)
    await callback.answer()

async def send_next_card(message: Message, user_id: int, category: str):
    card = database.get_random_card(user_id, category)
    if not card:
        await message.answer(
            "📭 No cards found in this category! Ending study session.",
            reply_markup=get_main_keyboard()
        )
        return
        
    stats = f"({card['correct_count']}✅ / {card['incorrect_count']}❌)"
    card_text = (
        f"📝 **Quiz Card** (ID: {card['id']}) {stats}\n"
        f"📁 Category: *{card['category']}*\n\n"
        f"❓ **Question:**\n"
        f"_{card['question']}_"
    )
    await message.answer(
        card_text,
        reply_markup=get_reveal_keyboard(card["id"]),
        parse_mode="Markdown"
    )

@router.callback_query(QuizStates.studying, F.data.startswith("reveal_"))
async def reveal_answer(callback: CallbackQuery, state: FSMContext):
    card_id = int(callback.data.split("reveal_")[1])
    user_id = callback.from_user.id
    
    # We find this card in the db to make sure we show the correct answer
    cards = database.get_user_cards(user_id)
    card = next((c for c in cards if c["id"] == card_id), None)
    
    if not card:
        await callback.message.edit_text("❌ This card was deleted or is no longer available.")
        await callback.answer()
        return
        
    stats = f"({card['correct_count']}✅ / {card['incorrect_count']}❌)"
    revealed_text = (
        f"📝 **Quiz Card** (ID: {card['id']}) {stats}\n"
        f"📁 Category: *{card['category']}*\n\n"
        f"❓ **Question:**\n"
        f"_{card['question']}_\n\n"
        f"💡 **Answer:**\n"
        f"**{card['answer']}**\n\n"
        "How did you do?"
    )
    await callback.message.edit_text(
        revealed_text,
        reply_markup=get_evaluation_keyboard(card_id),
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(QuizStates.studying, F.data.startswith("grade_"))
async def process_grading(callback: CallbackQuery, state: FSMContext):
    data_parts = callback.data.split("_")
    correct = data_parts[1] == "correct"
    card_id = int(data_parts[2])
    user_id = callback.from_user.id
    
    # Update stats
    database.update_card_stats(card_id, user_id, correct)
    
    # Get updated stats to show
    cards = database.get_user_cards(user_id)
    card = next((c for c in cards if c["id"] == card_id), None)
    
    result_emoji = "✅" if correct else "❌"
    
    if card:
        summary_text = (
            f"👍 **Response Recorded!**\n\n"
            f"**Question:** {card['question']}\n"
            f"**Answer:** {card['answer']}\n\n"
            f"Your grade: {result_emoji}\n"
            f"New Stats: {card['correct_count']}✅ / {card['incorrect_count']}❌"
        )
    else:
        summary_text = f"👍 Response recorded as {result_emoji}!"
        
    await callback.message.edit_text(summary_text, parse_mode="Markdown")
    
    # Now, check if we should send the next card
    state_data = await state.get_data()
    active_category = state_data.get("active_category")
    
    await send_next_card(callback.message, user_id, active_category)
    await callback.answer()
