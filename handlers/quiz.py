from html import escape
import random
import logging
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
    get_deck_config_list_keyboard,
    get_deck_config_menu_keyboard,
    get_card_edit_menu_keyboard,
    get_reveal_keyboard,
    get_evaluation_keyboard,
    get_study_ahead_keyboard,
)

logger = logging.getLogger(__name__)

router = Router()

class QuizStates(StatesGroup):
    selecting_category = State()
    studying = State()
    configuring_deck = State()
    waiting_daily_limit = State()
    editing_q = State()
    editing_a = State()
    editing_c = State()
    editing_cat = State()


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
    
    sent_msg = await message.answer(
        "🎯 <b>Spaced Repetition Study Mode (Anki SRS)</b>\n\n"
        "Select a deck below to review your due flashcards:",
        reply_markup=get_categories_keyboard(categories, due_counts),
        parse_mode="HTML"
    )
    await state.update_data(study_msg_id=sent_msg.message_id)

@router.callback_query(QuizStates.selecting_category, F.data == "quiz_cfg_list")
@router.callback_query(F.data == "quiz_cfg_list")
async def process_quiz_cfg_list(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    categories = database.get_user_categories(user_id)
    await state.set_state(QuizStates.configuring_deck)
    await callback.message.edit_text(
        "⚙️ <b>Configure Deck Settings</b>\n\n"
        "Select a deck below to adjust its daily new card limit and settings:",
        reply_markup=get_deck_config_list_keyboard(categories),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("cfg_deck_"))
async def process_cfg_deck(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    category = callback.data.split("cfg_deck_")[1]
    setting = database.get_deck_setting(user_id, category)
    studied_today = database.get_new_cards_studied_today(user_id, category)
    
    limit = setting.get("daily_new_limit", 20)
    limit_str = "Unlimited" if limit <= 0 else f"{limit} cards/day"
    preset = setting.get("preset_key", "general")

    await state.update_data(active_config_deck=category)
    await callback.message.edit_text(
        f"⚙️ <b>Deck Settings: {escape(category)}</b>\n\n"
        f"• 🆕 <b>Daily New Limit:</b> {limit_str} (studied today: {studied_today})\n"
        f"• 🤖 <b>AI Preset:</b> {escape(preset)}\n\n"
        "Choose an option below to update deck settings:",
        reply_markup=get_deck_config_menu_keyboard(category),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("cfg_limit_"))
async def process_cfg_limit(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split("cfg_limit_")[1]
    await state.set_state(QuizStates.waiting_daily_limit)
    await state.update_data(active_config_deck=category)
    
    await callback.message.edit_text(
        f"🔢 <b>Set Daily New Cards Limit for '{escape(category)}'</b>\n\n"
        "Please type a number for how many new cards you want to study each day in this deck.\n\n"
        "• Reply with <b>10</b>, <b>20</b>, <b>50</b>, etc.\n"
        "• Reply with <b>0</b> for unlimited new cards.",
        reply_markup=None,
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(QuizStates.waiting_daily_limit)
async def process_daily_limit_input(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit():
        await message.answer("⚠️ Please reply with a valid integer number (e.g. 20 or 0).")
        return
        
    new_limit = int(text)
    state_data = await state.get_data()
    category = state_data.get("active_config_deck", "General")
    user_id = message.from_user.id
    
    database.save_deck_setting(user_id, category, daily_new_limit=new_limit)
    
    await state.set_state(QuizStates.selecting_category)
    limit_display = "Unlimited" if new_limit <= 0 else f"{new_limit} cards/day"
    
    await message.answer(
        f"✅ Daily new card limit for <b>{escape(category)}</b> set to <b>{limit_display}</b>.",
        reply_markup=get_deck_config_menu_keyboard(category),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("cfg_preset_"))
async def process_cfg_preset(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split("cfg_preset_")[1]
    await callback.answer(
        f"To change AI presets for '{category}', create an AI card in '{category}' and select your preset.",
        show_alert=True
    )

@router.callback_query(QuizStates.selecting_category, F.data.startswith("quiz_cat_"))
async def select_category(callback: CallbackQuery, state: FSMContext):
    category_data = callback.data.split("quiz_cat_")[1]
    category = None if category_data == "all" else category_data
    
    await state.update_data(active_category=category, category_data=category_data, study_all=False, study_msg_id=callback.message.message_id)
    await state.set_state(QuizStates.studying)
    
    await send_next_card(callback.message, callback.from_user.id, category, state, edit_existing=True)
    await callback.answer()

@router.callback_query(F.data.startswith("study_ahead_"))
async def process_study_ahead(callback: CallbackQuery, state: FSMContext):
    cat_param = callback.data.split("study_ahead_")[1]
    category = None if cat_param == "all" else cat_param
    
    await state.set_state(QuizStates.studying)
    await state.update_data(active_category=category, category_data=cat_param, study_all=True, study_msg_id=callback.message.message_id)
    
    await send_next_card(callback.message, callback.from_user.id, category, state, edit_existing=True)
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
    await state.update_data(study_all=False, study_msg_id=callback.message.message_id)
    
    await callback.message.edit_text(
        "🎯 <b>Spaced Repetition Study Mode (Anki SRS)</b>\n\n"
        "Select a deck below to review your due flashcards:",
        reply_markup=get_categories_keyboard(categories, due_counts),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "study_stop")
async def process_stop_study(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback.message.edit_text(
            "🏁 <b>Study session ended.</b>",
            reply_markup=None,
            parse_mode="HTML"
        )
    except Exception:
        pass
    await callback.answer("Study session ended.")

async def send_next_card(message: Message, user_id: int, category: str, state: FSMContext, edit_existing: bool = True):
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
            markup = get_study_ahead_keyboard(category_data)
        else:
            completion_text = f"📭 <b>No cards found in {cat_display}!</b>"
            markup = get_study_ahead_keyboard(category_data)
            
        if edit_existing:
            try:
                await message.edit_text(completion_text, reply_markup=markup, parse_mode="HTML")
                await state.update_data(study_msg_id=message.message_id)
                return
            except Exception as e:
                logger.warning(f"Failed to edit completion text message in-place: {e}")
                try:
                    await message.delete()
                except Exception:
                    pass
        new_msg = await message.answer(completion_text, reply_markup=markup, parse_mode="HTML")
        await state.update_data(study_msg_id=new_msg.message_id)
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
    reply_kb = get_reveal_keyboard(card["id"], is_reversed=is_reversed)
    
    if edit_existing:
        try:
            await message.edit_text(card_text, reply_markup=reply_kb, parse_mode="HTML")
            await state.update_data(study_msg_id=message.message_id)
            return
        except Exception as e:
            logger.warning(f"Failed to edit card message in-place, using delete/answer fallback: {e}")
            try:
                await message.delete()
            except Exception:
                pass
                
    try:
        new_msg = await message.answer(card_text, reply_markup=reply_kb, parse_mode="HTML")
    except Exception:
        plain_text = (
            f"📝 Quiz Card (ID: {card['id']}) {stats}\n"
            f"📁 Category: {card['category']}\n\n"
            f"{'Answer' if is_reversed else 'Question'}:\n"
            f"{card['question']}"
        )
        new_msg = await message.answer(plain_text, reply_markup=reply_kb)
    await state.update_data(study_msg_id=new_msg.message_id)

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
    
    eval_kb = get_evaluation_keyboard(card_id)
    try:
        await callback.message.edit_text(
            revealed_text,
            reply_markup=eval_kb,
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
        try:
            await callback.message.edit_text(
                plain_text,
                reply_markup=eval_kb
            )
        except Exception:
            try:
                await callback.message.delete()
            except Exception:
                pass
            new_msg = await callback.message.answer(plain_text, reply_markup=eval_kb)
            await state.update_data(study_msg_id=new_msg.message_id)

    await state.update_data(study_msg_id=callback.message.message_id)
    await callback.answer()

def format_interval_display(interval: float) -> str:
    if not isinstance(interval, (int, float)) or interval <= 0:
        return "10 min(s)"
    if interval < 1.0:
        mins = int(round(interval * 24 * 60))
        if mins < 60:
            return f"{max(1, mins)} min(s)"
        else:
            hrs = int(round(interval * 24))
            return f"{max(1, hrs)} hour(s)"
    else:
        days = int(round(interval))
        return f"{days} day(s)"

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
    time_str = format_interval_display(interval)
    
    if rating == "again":
        toast_msg = f"🔴 Again! Next review in {time_str}."
    elif rating == "hard":
        toast_msg = f"🟠 Hard! Next review in {time_str}."
    elif rating == "easy":
        toast_msg = f"🔵 Easy! Next review in {time_str}."
    else:
        toast_msg = f"🟢 Good! Next review in {time_str}."
        
    await callback.answer(toast_msg, show_alert=False)
    
    state_data = await state.get_data()
    active_category = state_data.get("active_category")
    
    # Edit current message in-place to display next card
    await send_next_card(callback.message, user_id, active_category, state, edit_existing=True)


@router.callback_query(QuizStates.studying, F.data.startswith("study_delete_"))
@router.callback_query(F.data.startswith("study_delete_"))
async def process_study_delete(callback: CallbackQuery, state: FSMContext):
    card_id = int(callback.data.split("study_delete_")[1])
    user_id = callback.from_user.id
    
    database.delete_card(card_id, user_id)
    await callback.answer("🗑️ Card deleted (both sides)!", show_alert=False)
    
    state_data = await state.get_data()
    active_category = state_data.get("active_category")
    await send_next_card(callback.message, user_id, active_category, state, edit_existing=True)

@router.callback_query(QuizStates.studying, F.data.startswith("study_edit_"))
@router.callback_query(F.data.startswith("study_edit_"))
async def process_study_edit(callback: CallbackQuery, state: FSMContext):
    card_id = int(callback.data.split("study_edit_")[1])
    user_id = callback.from_user.id
    cards = database.get_user_cards(user_id)
    card = next((c for c in cards if c["id"] == card_id), None)
    
    if not card:
        await callback.answer("Card not found.", show_alert=True)
        return
        
    await state.update_data(editing_card_id=card_id)
    msg_text = (
        f"✏️ <b>Edit Card #{card_id}</b> (Deck: <b>{escape(card['category'])}</b>)\n\n"
        f"<b>Question:</b>\n{escape(card['question'])}\n\n"
        f"<b>Answer:</b>\n{escape(card['answer'])}\n\n"
        f"<b>Comment:</b>\n{escape(card.get('comment') or 'None')}\n\n"
        "Select what you would like to edit:"
    )
    await callback.message.edit_text(msg_text, reply_markup=get_card_edit_menu_keyboard(card_id), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("edit_field_q_"))
async def process_edit_field_q(callback: CallbackQuery, state: FSMContext):
    card_id = int(callback.data.split("edit_field_q_")[1])
    await state.set_state(QuizStates.editing_q)
    await state.update_data(editing_card_id=card_id)
    await callback.message.edit_text(
        "✍️ <b>Edit Question</b>\n\nPlease reply with the new Question text for this card:",
        reply_markup=None,
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("edit_field_a_"))
async def process_edit_field_a(callback: CallbackQuery, state: FSMContext):
    card_id = int(callback.data.split("edit_field_a_")[1])
    await state.set_state(QuizStates.editing_a)
    await state.update_data(editing_card_id=card_id)
    await callback.message.edit_text(
        "✍️ <b>Edit Answer</b>\n\nPlease reply with the new Answer text for this card:",
        reply_markup=None,
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("edit_field_c_"))
async def process_edit_field_c(callback: CallbackQuery, state: FSMContext):
    card_id = int(callback.data.split("edit_field_c_")[1])
    await state.set_state(QuizStates.editing_c)
    await state.update_data(editing_card_id=card_id)
    await callback.message.edit_text(
        "✍️ <b>Edit Comment</b>\n\nPlease reply with the new Comment text for this card (or reply '-' to clear):",
        reply_markup=None,
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("edit_field_cat_"))
async def process_edit_field_cat(callback: CallbackQuery, state: FSMContext):
    card_id = int(callback.data.split("edit_field_cat_")[1])
    await state.set_state(QuizStates.editing_cat)
    await state.update_data(editing_card_id=card_id)
    await callback.message.edit_text(
        "📁 <b>Change Deck / Category</b>\n\nPlease reply with the new Category / Deck name for this card:",
        reply_markup=None,
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(QuizStates.editing_q)
async def save_edited_q(message: Message, state: FSMContext):
    state_data = await state.get_data()
    card_id = state_data.get("editing_card_id")
    user_id = message.from_user.id
    new_text = message.text.strip()
    
    database.update_card(card_id, user_id, question=new_text)
    await state.set_state(QuizStates.studying)
    await message.answer("✅ Question updated!", parse_mode="HTML")
    active_category = state_data.get("active_category")
    await send_next_card(message, user_id, active_category, state, edit_existing=False)

@router.message(QuizStates.editing_a)
async def save_edited_a(message: Message, state: FSMContext):
    state_data = await state.get_data()
    card_id = state_data.get("editing_card_id")
    user_id = message.from_user.id
    new_text = message.text.strip()
    
    database.update_card(card_id, user_id, answer=new_text)
    await state.set_state(QuizStates.studying)
    await message.answer("✅ Answer updated!", parse_mode="HTML")
    active_category = state_data.get("active_category")
    await send_next_card(message, user_id, active_category, state, edit_existing=False)

@router.message(QuizStates.editing_c)
async def save_edited_c(message: Message, state: FSMContext):
    state_data = await state.get_data()
    card_id = state_data.get("editing_card_id")
    user_id = message.from_user.id
    new_text = "" if message.text.strip() == "-" else message.text.strip()
    
    database.update_card(card_id, user_id, comment=new_text)
    await state.set_state(QuizStates.studying)
    await message.answer("✅ Comment updated!", parse_mode="HTML")
    active_category = state_data.get("active_category")
    await send_next_card(message, user_id, active_category, state, edit_existing=False)

@router.message(QuizStates.editing_cat)
async def save_edited_cat(message: Message, state: FSMContext):
    state_data = await state.get_data()
    card_id = state_data.get("editing_card_id")
    user_id = message.from_user.id
    new_cat = message.text.strip()
    
    database.update_card(card_id, user_id, category=new_cat)
    await state.set_state(QuizStates.studying)
    await message.answer(f"✅ Card moved to deck <b>{escape(new_cat)}</b>!", parse_mode="HTML")
    active_category = state_data.get("active_category")
    await send_next_card(message, user_id, active_category, state, edit_existing=False)

@router.callback_query(F.data == "study_resume")
async def process_study_resume(callback: CallbackQuery, state: FSMContext):
    await state.set_state(QuizStates.studying)
    state_data = await state.get_data()
    active_category = state_data.get("active_category")
    await send_next_card(callback.message, callback.from_user.id, active_category, state, edit_existing=True)
    await callback.answer()

