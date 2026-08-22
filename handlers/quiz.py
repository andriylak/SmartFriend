from html import escape
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
            "Please create some cards first using <b>➕ Create Card</b>.",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
        return
        
    await state.set_state(QuizStates.selecting_category)
    
    await message.answer(
        "🎯 <b>Study Mode</b>\n\n"
        "Please select a category you would like to study:",
        reply_markup=get_categories_keyboard(categories),
        parse_mode="HTML"
    )

@router.callback_query(QuizStates.selecting_category, F.data.startswith("quiz_cat_"))
async def select_category(callback: CallbackQuery, state: FSMContext):
    category_data = callback.data.split("quiz_cat_")[1]
    category = None if category_data == "all" else category_data
    
    await state.update_data(active_category=category)
    await state.set_state(QuizStates.studying)
    
    cat_display = escape(category) if category else 'All'
    await callback.message.answer(
        f"🏁 Starting study session! Category: <b>{cat_display}</b>\n"
        "You can tap <b>❌ Cancel</b> at any time to end the session.",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    
    # Fetch first card
    await send_next_card(callback.message, callback.from_user.id, category)
    await callback.answer()

import random

async def send_next_card(message: Message, user_id: int, category: str):
    card = database.get_random_card(user_id, category)
    if not card:
        await message.answer(
            "📭 No cards found in this category! Ending study session.",
            reply_markup=get_main_keyboard()
        )
        return
        
    is_reversed = random.choice([True, False])
    stats = f"({card['correct_count']}✅ / {card['incorrect_count']}❌)"
    q_escaped = escape(card['question'])
    a_escaped = escape(card['answer'])
    cat_escaped = escape(card['category'])
    
    if is_reversed:
        mode_badge = " [Mode: ⬅️ Answer ➔ Question]"
        prompt_label = "💡 <b>Answer / Clue:</b>"
        prompt_content = f"<i>{a_escaped}</i>"
    else:
        mode_badge = " [Mode: ➡️ Question ➔ Answer]"
        prompt_label = "❓ <b>Question:</b>"
        prompt_content = f"<i>{q_escaped}</i>"
        
    card_text = (
        f"📝 <b>Quiz Card</b> (ID: {card['id']}) {stats}{mode_badge}\n"
        f"📁 Category: <i>{cat_escaped}</i>\n\n"
        f"{prompt_label}\n"
        f"{prompt_content}"
    )
    try:
        await message.answer(
            card_text,
            reply_markup=get_reveal_keyboard(card["id"], is_reversed=is_reversed),
            parse_mode="HTML"
        )
    except Exception:
        plain_text = (
            f"📝 Quiz Card (ID: {card['id']}) {stats}\n"
            f"📁 Category: {card['category']}\n\n"
            f"{'Answer' if is_reversed else 'Question'}:\n"
            f"{card['answer'] if is_reversed else card['question']}"
        )
        await message.answer(
            plain_text,
            reply_markup=get_reveal_keyboard(card["id"], is_reversed=is_reversed)
        )

@router.callback_query(QuizStates.studying, F.data.startswith("reveal_"))
async def reveal_answer(callback: CallbackQuery, state: FSMContext):
    cb_data = callback.data
    is_reversed = cb_data.startswith("reveal_rev_")
    
    if is_reversed:
        card_id = int(cb_data.split("reveal_rev_")[1])
    elif cb_data.startswith("reveal_std_"):
        card_id = int(cb_data.split("reveal_std_")[1])
    else:
        card_id = int(cb_data.split("reveal_")[1])

    user_id = callback.from_user.id
    
    # We find this card in the db to make sure we show the correct answer
    cards = database.get_user_cards(user_id)
    card = next((c for c in cards if c["id"] == card_id), None)
    
    if not card:
        await callback.message.edit_text("❌ This card was deleted or is no longer available.")
        await callback.answer()
        return
        
    stats = f"({card['correct_count']}✅ / {card['incorrect_count']}❌)"
    q_escaped = escape(card['question'])
    a_escaped = escape(card['answer'])
    cat_escaped = escape(card['category'])
    comment = card.get('comment', '')
    comment_html = f"\n\n📌 <b>Additional Info:</b>\n{escape(comment)}" if comment else ""
    comment_plain = f"\n\nAdditional Info:\n{comment}" if comment else ""
    
    if is_reversed:
        revealed_text = (
            f"📝 <b>Quiz Card</b> (ID: {card['id']}) {stats}\n"
            f"📁 Category: <i>{cat_escaped}</i>\n\n"
            f"💡 <b>Answer / Clue:</b>\n"
            f"<i>{a_escaped}</i>\n\n"
            f"❓ <b>Question / Target:</b>\n"
            f"<b>{q_escaped}</b>"
            f"{comment_html}\n\n"
            "How did you do?"
        )
    else:
        revealed_text = (
            f"📝 <b>Quiz Card</b> (ID: {card['id']}) {stats}\n"
            f"📁 Category: <i>{cat_escaped}</i>\n\n"
            f"❓ <b>Question:</b>\n"
            f"<i>{q_escaped}</i>\n\n"
            f"💡 <b>Answer:</b>\n"
            f"<b>{a_escaped}</b>"
            f"{comment_html}\n\n"
            "How did you do?"
        )
    try:
        await callback.message.edit_text(
            revealed_text,
            reply_markup=get_evaluation_keyboard(card_id),
            parse_mode="HTML"
        )
    except Exception:
        plain_text = (
            f"📝 Quiz Card (ID: {card['id']}) {stats}\n"
            f"📁 Category: {card['category']}\n\n"
            f"Question: {card['question']}\n"
            f"Answer: {card['answer']}"
            f"{comment_plain}\n\n"
            "How did you do?"
        )
        await callback.message.edit_text(
            plain_text,
            reply_markup=get_evaluation_keyboard(card_id)
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
        q_escaped = escape(card['question'])
        a_escaped = escape(card['answer'])
        summary_text = (
            f"👍 <b>Response Recorded!</b>\n\n"
            f"<b>Question:</b> {q_escaped}\n"
            f"<b>Answer:</b> {a_escaped}\n\n"
            f"Your grade: {result_emoji}\n"
            f"New Stats: {card['correct_count']}✅ / {card['incorrect_count']}❌"
        )
        try:
            await callback.message.edit_text(summary_text, parse_mode="HTML")
        except Exception:
            plain_text = (
                f"👍 Response Recorded!\n\n"
                f"Question: {card['question']}\n"
                f"Answer: {card['answer']}\n\n"
                f"Your grade: {result_emoji}\n"
                f"New Stats: {card['correct_count']}✅ / {card['incorrect_count']}❌"
            )
            await callback.message.edit_text(plain_text)
    else:
        summary_text = f"👍 Response recorded as {result_emoji}!"
        await callback.message.edit_text(summary_text)
        
    # Now, check if we should send the next card
    state_data = await state.get_data()
    active_category = state_data.get("active_category")
    
    await send_next_card(callback.message, user_id, active_category)
    await callback.answer()
