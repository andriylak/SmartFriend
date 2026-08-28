from html import escape
import random
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database
import ai_service
from ai_service import format_comment
from keyboards import (
    get_main_keyboard,
    get_cancel_keyboard,
    get_categories_keyboard,
    get_reveal_keyboard,
    get_evaluation_keyboard,
    get_study_ahead_keyboard,
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
        
    due_counts = database.get_due_card_counts(user_id)
    await state.set_state(QuizStates.selecting_category)
    await state.update_data(study_all=False)
    
    await message.answer(
        "🎯 <b>Spaced Repetition Study Mode (Anki SRS)</b>\n\n"
        "Select a deck below to review your due flashcards:",
        reply_markup=get_categories_keyboard(categories, due_counts),
        parse_mode="HTML"
    )

@router.callback_query(QuizStates.selecting_category, F.data.startswith("quiz_cat_"))
async def select_category(callback: CallbackQuery, state: FSMContext):
    category_data = callback.data.split("quiz_cat_")[1]
    category = None if category_data == "all" else category_data
    
    await state.update_data(active_category=category, category_data=category_data, study_all=False)
    await state.set_state(QuizStates.studying)
    
    cat_display = escape(category) if category else 'All Decks'
    await callback.message.answer(
        f"🏁 Starting SRS study session! Deck: <b>{cat_display}</b>\n"
        "You can tap <b>❌ Cancel</b> at any time to end the session.",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    
    # Fetch first card
    await send_next_card(callback.message, callback.from_user.id, category, state)
    await callback.answer()

@router.callback_query(F.data.startswith("study_ahead_"))
async def process_study_ahead(callback: CallbackQuery, state: FSMContext):
    cat_param = callback.data.split("study_ahead_")[1]
    category = None if cat_param == "all" else cat_param
    
    await state.set_state(QuizStates.studying)
    await state.update_data(active_category=category, category_data=cat_param, study_all=True)
    
    cat_display = escape(category) if category else 'All Decks'
    await callback.message.answer(
        f"⚡ <b>Study Ahead Mode Enabled!</b> Deck: <b>{cat_display}</b>\n"
        "Studying all cards regardless of due dates.",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    await send_next_card(callback.message, callback.from_user.id, category, state)
    await callback.answer()

@router.callback_query(F.data == "study_back_decks")
async def process_study_back_decks(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    categories = database.get_user_categories(user_id)
    if not categories:
        await callback.message.edit_text("📭 No cards found.", reply_markup=get_main_keyboard())
        await callback.answer()
        return
        
    due_counts = database.get_due_card_counts(user_id)
    await state.set_state(QuizStates.selecting_category)
    await state.update_data(study_all=False)
    
    await callback.message.edit_text(
        "🎯 <b>Spaced Repetition Study Mode (Anki SRS)</b>\n\n"
        "Select a deck below to review your due flashcards:",
        reply_markup=get_categories_keyboard(categories, due_counts),
        parse_mode="HTML"
    )
    await callback.answer()

async def send_next_card(message: Message, user_id: int, category: str, state: FSMContext):
    state_data = await state.get_data()
    study_all = state_data.get("study_all", False)
    category_data = state_data.get("category_data", "all")
    
    due_cards = database.get_due_cards(user_id, category, study_all=study_all)
    if not due_cards:
        cat_display = escape(category) if category else 'All Decks'
        if not study_all:
            completion_text = (
                f"🎉 <b>All Caught Up!</b>\n\n"
                f"You have reviewed all due cards in <b>{cat_display}</b>.\n"
                "Great job! Check back later for your next scheduled reviews."
            )
            await message.answer(
                completion_text,
                reply_markup=get_study_ahead_keyboard(category_data),
                parse_mode="HTML"
            )
        else:
            await message.answer(
                f"📭 <b>No cards found in {cat_display}!</b>",
                reply_markup=get_main_keyboard(),
                parse_mode="HTML"
            )
        return
        
    card = due_cards[0]
    is_reversed = card.get("direction") == "reverse"
    stats = f"({card['correct_count']}✅ / {card['incorrect_count']}❌)"
    q_escaped = escape(card['question'])
    a_escaped = escape(card['answer'])
    cat_escaped = escape(card['category'])
    
    if is_reversed:
        mode_badge = " [Mode: ⬅️ Answer ➔ Question]"
        prompt_label = "💡 <b>Answer / Clue:</b>"
        prompt_content = f"<i>{q_escaped}</i>"
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
            f"{card['question']}"
        )
        await message.answer(
            plain_text,
            reply_markup=get_reveal_keyboard(card["id"], is_reversed=is_reversed)
        )

@router.callback_query(QuizStates.studying, F.data.startswith("reveal_"))
async def reveal_answer(callback: CallbackQuery, state: FSMContext):
    cb_data = callback.data
    card_id = int(cb_data.split("_")[-1])

    user_id = callback.from_user.id
    
    cards = database.get_user_cards(user_id)
    card = next((c for c in cards if c["id"] == card_id), None)
    
    if not card:
        await callback.message.edit_text("❌ This card was deleted or is no longer available.")
        await callback.answer()
        return
        
    is_reversed = card.get("direction") == "reverse" or cb_data.startswith("reveal_rev_")
    stats = f"({card['correct_count']}✅ / {card['incorrect_count']}❌)"
    q_escaped = escape(card['question'])
    a_escaped = escape(card['answer'])
    cat_escaped = escape(card['category'])
    comment = card.get('comment', '')
    comment_html = f"\n\n📌 <b>Additional Info:</b>\n{format_comment(comment, fmt='html')}" if comment else ""
    comment_plain = f"\n\nAdditional Info:\n{format_comment(comment, fmt='plain')}" if comment else ""
    
    if is_reversed:
        revealed_text = (
            f"📝 <b>Quiz Card</b> (ID: {card['id']}) {stats}\n"
            f"📁 Category: <i>{cat_escaped}</i>\n\n"
            f"💡 <b>Answer / Clue:</b>\n"
            f"<i>{q_escaped}</i>\n\n"
            f"❓ <b>Question / Target:</b>\n"
            f"<b>{a_escaped}</b>"
            f"{comment_html}\n\n"
            "Rate your recall difficulty:"
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
            "Rate your recall difficulty:"
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
            "Rate your recall difficulty:"
        )
        await callback.message.edit_text(
            plain_text,
            reply_markup=get_evaluation_keyboard(card_id)
        )
    await callback.answer()

@router.callback_query(QuizStates.studying, F.data.startswith("srs_"))
@router.callback_query(QuizStates.studying, F.data.startswith("grade_"))
async def process_grading(callback: CallbackQuery, state: FSMContext):
    cb_data = callback.data
    user_id = callback.from_user.id
    
    if cb_data.startswith("srs_"):
        parts = cb_data.split("_")
        rating = parts[1]  # again, hard, good, easy
        card_id = int(parts[2])
    else:
        # Backward compatibility fallback for old grade_ buttons
        parts = cb_data.split("_")
        rating = "good" if parts[1] == "correct" else "again"
        card_id = int(parts[2])
        
    srs_res = database.update_card_srs(card_id, user_id, rating)
    
    interval = srs_res.get("interval_days", 0)
    if rating == "again":
        toast_msg = "🔴 Again! Card scheduled for review now (~10m)."
    elif rating == "hard":
        toast_msg = f"🟠 Hard! Next review in {interval} day(s)."
    elif rating == "easy":
        toast_msg = f"🔵 Easy! Next review in {interval} day(s)."
    else:
        toast_msg = f"🟢 Good! Next review in {interval} day(s)."
        
    await callback.answer(toast_msg, show_alert=False)
    
    state_data = await state.get_data()
    active_category = state_data.get("active_category")
    
    # Send next card
    await send_next_card(callback.message, user_id, active_category, state)
