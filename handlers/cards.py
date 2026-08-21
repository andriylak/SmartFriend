import re
import logging
from html import escape
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import config
import database
import ai_service
from keyboards import (
    get_main_keyboard,
    get_cancel_keyboard,
    get_card_creation_mode_keyboard,
    get_ai_prompt_presets_keyboard,
    get_target_languages_keyboard,
    get_ai_preview_keyboard,
    get_category_selection_reply_keyboard,
    get_ai_topic_keyboard
)

logger = logging.getLogger(__name__)

router = Router()

class CreateCardStates(StatesGroup):
    waiting_for_mode = State()
    waiting_for_category = State()
    waiting_for_question = State()
    waiting_for_answer = State()
    waiting_for_ai_prompt_preset = State()
    waiting_for_target_language = State()
    waiting_for_ai_custom_prompt = State()
    waiting_for_ai_topic = State()
    waiting_for_ai_preview = State()
    waiting_for_edit_question = State()
    waiting_for_edit_answer = State()

# Step 0: Start creation process
@router.message(F.text == "➕ Create Card")
@router.message(Command("create"))
async def start_create_card(message: Message, state: FSMContext):
    await state.set_state(CreateCardStates.waiting_for_mode)
    
    await message.answer(
        "⚙️ **How would you like to create your flashcard?**\n\n"
        "🤖 **AI-Assisted Card**: Generate flashcards automatically using AI (with pre-set prompts like *Language Learning*, *Definitions*, or your own *Custom Prompt*).\n"
        "✍️ **Manual Card**: Type the Question and Answer yourself.",
        reply_markup=get_card_creation_mode_keyboard(),
        parse_mode="Markdown"
    )

# Step 0.5: Handle creation mode selection
@router.message(CreateCardStates.waiting_for_mode)
async def process_creation_mode(message: Message, state: FSMContext):
    choice = message.text.strip()
    user_categories = database.get_user_categories(message.from_user.id)
    category_kb = get_category_selection_reply_keyboard(user_categories)
    
    if user_categories:
        deck_list_str = "\n".join(f"• *{cat}*" for cat in user_categories)
        prompt_intro = (
            "📁 **Select or Enter Category / Deck**\n\n"
            f"**Your Existing Decks:**\n{deck_list_str}\n\n"
            "Choose an existing deck from the keyboard below, or type a new deck name:"
        )
    else:
        prompt_intro = (
            "📁 **Category / Deck**\n\n"
            "Please enter a category/deck for your card (e.g., *Math*, *Python*, *Spanish*), or tap **General** to use default."
        )
    
    if choice == "✍️ Manual Card":
        await state.update_data(is_ai=False)
        await state.set_state(CreateCardStates.waiting_for_category)
        
        await message.answer(
            prompt_intro,
            reply_markup=category_kb,
            parse_mode="Markdown"
        )
        
    elif choice == "🤖 AI-Assisted Card":
        if not config.GEMINI_API_KEY:
            await message.answer(
                "⚠️ **AI API Key Not Found**\n\n"
                "`GEMINI_API_KEY` is not set in `.env`. AI card generation requires a valid Google Gemini API key.\n\n"
                "You can still create cards manually!",
                reply_markup=get_main_keyboard(),
                parse_mode="Markdown"
            )
            await state.clear()
            return
            
        await state.update_data(is_ai=True)
        await state.set_state(CreateCardStates.waiting_for_category)
        
        await message.answer(
            f"🤖 **AI Flashcard Assistant - Step 1: Category**\n\n{prompt_intro}",
            reply_markup=category_kb,
            parse_mode="Markdown"
        )
    else:
        await message.answer("Please select an option from the menu: 🤖 **AI-Assisted Card** or ✍️ **Manual Card**.")

PRESET_NAME_MAP = {
    "language": "🌐 Language Learning",
    "definitions": "📚 Definitions & Concepts",
    "programming": "💻 Programming & Syntax",
    "trivia": "🧠 General Knowledge",
    "custom": "✏️ Custom Prompt"
}

# Step 1: Process Category (for both Manual and AI)
@router.message(CreateCardStates.waiting_for_category)
async def process_category(message: Message, state: FSMContext):
    category = message.text.strip()
    if not category:
        await message.answer("Please enter a valid category name.")
        return
        
    await state.update_data(category=category)
    data = await state.get_data()
    is_ai = data.get("is_ai", False)
    
    if is_ai:
        user_id = message.from_user.id
        deck_setting = database.get_deck_setting(user_id, category)
        
        if deck_setting:
            preset_key = deck_setting["preset_key"]
            target_language = deck_setting.get("target_language")
            custom_prompt = deck_setting.get("custom_prompt")
            preset_text = PRESET_NAME_MAP.get(preset_key, "AI Card")
            
            await state.update_data(
                preset_key=preset_key,
                preset_text=preset_text,
                target_language=target_language,
                custom_prompt=custom_prompt,
                has_saved_prompt=True
            )
            await state.set_state(CreateCardStates.waiting_for_ai_topic)
            
            if preset_key == "language" and target_language:
                setting_desc = f"*{preset_text}* (Translate To: *{target_language}*)"
            elif preset_key == "custom" and custom_prompt:
                setting_desc = f"*{preset_text}* (*{custom_prompt}*)"
            else:
                setting_desc = f"*{preset_text}*"
                
            await message.answer(
                f"🤖 **AI Flashcard Assistant** (Deck: *{category}*)\n\n"
                f"📌 **Saved Deck Setting:** {setting_desc}\n\n"
                "What word, phrase, or topic do you want the AI to create a card for?\n\n"
                "*(Tap **⚙️ Change Deck Prompt** below if you want to pick a different prompt for this deck)*",
                reply_markup=get_ai_topic_keyboard(has_saved_prompt=True),
                parse_mode="Markdown"
            )
        else:
            await state.set_state(CreateCardStates.waiting_for_ai_prompt_preset)
            await message.answer(
                f"🎯 **AI Step 2: Choose Prompt Type** (Category: *{category}*)\n\n"
                "Select one of the default AI prompt presets below, or choose ✏️ **Custom Prompt** to write your own instructions:",
                reply_markup=get_ai_prompt_presets_keyboard(),
                parse_mode="Markdown"
            )
    else:
        await state.set_state(CreateCardStates.waiting_for_question)
        await message.answer(
            "❓ **Step 2: Question**\n\n"
            f"Category selected: *{category}*\n\n"
            "Now, type the **Question** or prompt for the front side of your learning card.",
            reply_markup=get_cancel_keyboard(),
            parse_mode="Markdown"
        )

# --- MANUAL CARD FLOW ---
@router.message(CreateCardStates.waiting_for_question)
async def process_question(message: Message, state: FSMContext):
    question = message.text.strip()
    if not question:
        await message.answer("Please enter a valid question.")
        return
        
    await state.update_data(question=question)
    await state.set_state(CreateCardStates.waiting_for_answer)
    
    await message.answer(
        "💡 **Step 3: Answer**\n\n"
        "Now, type the **Answer** or explanation for the back side of your learning card.",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )

@router.message(CreateCardStates.waiting_for_answer)
async def process_answer(message: Message, state: FSMContext):
    answer = message.text.strip()
    if not answer:
        await message.answer("Please enter a valid answer.")
        return
        
    user_data = await state.get_data()
    category = user_data.get("category", "General")
    question = user_data.get("question")
    
    card_id = database.add_card(
        user_id=message.from_user.id,
        question=question,
        answer=answer,
        category=category
    )
    
    await state.clear()
    
    success_text = (
        "🎉 **Card Created Successfully!**\n\n"
        f"**ID:** {card_id}\n"
        f"**Category:** {category}\n"
        f"**Question:** {question}\n"
        f"**Answer:** {answer}\n\n"
        "You can now find this card in your study pool!"
    )
    await message.answer(success_text, reply_markup=get_main_keyboard(), parse_mode="Markdown")

# --- AI-ASSISTED CARD FLOW ---
@router.message(CreateCardStates.waiting_for_ai_prompt_preset)
async def process_ai_preset(message: Message, state: FSMContext):
    preset_text = message.text.strip()
    
    preset_map = {
        "🌐 Language Learning": "language",
        "📚 Definitions & Concepts": "definitions",
        "💻 Programming & Syntax": "programming",
        "🧠 General Knowledge": "trivia",
        "✏️ Custom Prompt": "custom"
    }
    
    preset_key = preset_map.get(preset_text)
    if not preset_key:
        await message.answer("Please select a valid preset from the keyboard below.")
        return
        
    await state.update_data(preset_key=preset_key, preset_text=preset_text)
    
    if preset_key == "language":
        await state.set_state(CreateCardStates.waiting_for_target_language)
        await message.answer(
            "🌐 **AI Step 3: Choose Target Translation Language**\n\n"
            "What language do you want the word, phrase, and example sentences translated **TO**?\n"
            "(e.g., *English*, *Ukrainian*, *Spanish*, *German*, *French*)",
            reply_markup=get_target_languages_keyboard(),
            parse_mode="Markdown"
        )
    elif preset_key == "custom":
        await state.set_state(CreateCardStates.waiting_for_ai_custom_prompt)
        await message.answer(
            "✏️ **AI Step 3: Your Custom Prompt**\n\n"
            "Please type your custom instructions for generating the flashcard.\n"
            "For example: *Create a flashcard comparing synchronous vs asynchronous execution in Python*",
            reply_markup=get_cancel_keyboard(),
            parse_mode="Markdown"
        )
    else:
        data = await state.get_data()
        category = data.get("category", "General")
        database.save_deck_setting(message.from_user.id, category, preset_key)
        await state.update_data(has_saved_prompt=True)
        
        await state.set_state(CreateCardStates.waiting_for_ai_topic)
        await message.answer(
            f"📝 **AI Step 3: Enter Topic or Phrase**\n\n"
            f"Selected Preset: *{preset_text}*\n\n"
            "What word, phrase, or topic do you want the AI to create a card for? "
            "(e.g., *Photosynthesis*, *Python list comprehension*, *World War II*)",
            reply_markup=get_ai_topic_keyboard(has_saved_prompt=True),
            parse_mode="Markdown"
        )

@router.message(CreateCardStates.waiting_for_target_language)
async def process_target_language(message: Message, state: FSMContext):
    raw_lang = message.text.strip()
    if not raw_lang:
        await message.answer("Please enter or select a valid target language.")
        return
        
    # Remove emoji flag icons if user clicked keyboard button (e.g. "🇬🇧 English" -> "English")
    clean_lang = re.sub(r"^[^\w\s]+", "", raw_lang).strip()
    target_language = clean_lang if clean_lang else raw_lang
    
    await state.update_data(target_language=target_language)
    
    data = await state.get_data()
    category = data.get("category", "General")
    database.save_deck_setting(message.from_user.id, category, "language", target_language=target_language)
    await state.update_data(has_saved_prompt=True)
    
    await state.set_state(CreateCardStates.waiting_for_ai_topic)
    
    await message.answer(
        "📝 **AI Step 4: Enter Topic, Word, or Phrase**\n\n"
        f"Selected Preset: *🌐 Language Learning*\n"
        f"Translate To: *{target_language}*\n\n"
        "What word, phrase, or sentence do you want to learn? "
        "(e.g., *el gato*, *la manzana*, *ordering food in Spanish*)",
        reply_markup=get_ai_topic_keyboard(has_saved_prompt=True),
        parse_mode="Markdown"
    )

@router.message(CreateCardStates.waiting_for_ai_custom_prompt)
async def process_ai_custom_prompt(message: Message, state: FSMContext):
    custom_prompt = message.text.strip()
    if not custom_prompt:
        await message.answer("Please enter a non-empty custom prompt.")
        return
        
    await state.update_data(custom_prompt=custom_prompt)
    
    data = await state.get_data()
    category = data.get("category", "General")
    database.save_deck_setting(message.from_user.id, category, "custom", custom_prompt=custom_prompt)
    await state.update_data(has_saved_prompt=True)
    
    await state.set_state(CreateCardStates.waiting_for_ai_topic)
    
    await message.answer(
        "📝 **AI Step 4: Enter Topic or Content**\n\n"
        "Now enter the specific topic, word, or text for your card:",
        reply_markup=get_ai_topic_keyboard(has_saved_prompt=True),
        parse_mode="Markdown"
    )

@router.message(CreateCardStates.waiting_for_ai_topic)
async def process_ai_topic(message: Message, state: FSMContext):
    topic = message.text.strip()
    
    if topic == "⚙️ Change Deck Prompt":
        data = await state.get_data()
        category = data.get("category", "General")
        await state.set_state(CreateCardStates.waiting_for_ai_prompt_preset)
        await message.answer(
            f"⚙️ **Change Deck Prompt** (Category: *{category}*)\n\n"
            "Select a new prompt preset below to update the AI instructions for this deck:",
            reply_markup=get_ai_prompt_presets_keyboard(),
            parse_mode="Markdown"
        )
        return
        
    if not topic:
        await message.answer("Please enter a valid topic.")
        return
        
    await state.update_data(topic=topic)
    await generate_and_show_ai_preview(message, state)

async def generate_and_show_ai_preview(message: Message, state: FSMContext):
    data = await state.get_data()
    preset_key = data.get("preset_key", "language")
    preset_text = data.get("preset_text", "Default Preset")
    topic = data.get("topic", "")
    custom_prompt = data.get("custom_prompt")
    target_language = data.get("target_language")
    category = data.get("category", "General")
    
    wait_msg = await message.answer("🤖 *Generating flashcard with AI... Please wait a moment.*", parse_mode="Markdown")
    
    try:
        card_data = await ai_service.generate_ai_card(
            preset_key=preset_key,
            topic=topic,
            custom_prompt=custom_prompt,
            target_language=target_language
        )
        question = card_data["question"]
        answer = card_data["answer"]
        
        await state.update_data(question=question, answer=answer)
        await state.set_state(CreateCardStates.waiting_for_ai_preview)
        
        # Delete status message
        try:
            await wait_msg.delete()
        except Exception:
            pass
            
        target_lang_str = f"🌐 **Translate To:** {target_language}\n" if preset_key == "language" and target_language else ""
        preview_text = (
            "🤖 **AI Flashcard Preview**\n\n"
            f"📁 **Category:** {category}\n"
            f"🎯 **Preset:** {preset_text}\n"
            f"{target_lang_str}\n"
            f"❓ **Question:**\n{question}\n\n"
            f"💡 **Answer:**\n{answer}\n\n"
            "✨ *Would you like to save this card, edit it, or regenerate?*"
        )
        await message.answer(preview_text, reply_markup=get_ai_preview_keyboard(), parse_mode="Markdown")
        
    except Exception as e:
        logger.exception("Error generating AI card")
        try:
            await wait_msg.delete()
        except Exception:
            pass
            
        await message.answer(
            f"❌ **AI Generation Failed**\n\nError: `{str(e)}`\n\n"
            "You can try again, enter a different topic, or cancel.",
            reply_markup=get_cancel_keyboard(),
            parse_mode="Markdown"
        )

# --- AI PREVIEW CALLBACK HANDLERS ---
@router.callback_query(CreateCardStates.waiting_for_ai_preview, F.data == "ai_save")
async def process_ai_save(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    category = data.get("category", "General")
    question = data.get("question")
    answer = data.get("answer")
    
    if not question or not answer:
        await callback.answer("Error: Missing card content.", show_alert=True)
        return
        
    card_id = database.add_card(
        user_id=callback.from_user.id,
        question=question,
        answer=answer,
        category=category
    )
    
    await state.clear()
    await callback.message.edit_text(
        "🎉 **AI Card Saved Successfully!**\n\n"
        f"**ID:** {card_id}\n"
        f"**Category:** {category}\n"
        f"**Question:** {question}\n"
        f"**Answer:** {answer}\n\n"
        "Saved to your flashcards pool!",
        parse_mode="Markdown"
    )
    await callback.message.answer("Main Menu", reply_markup=get_main_keyboard())
    await callback.answer()

@router.callback_query(CreateCardStates.waiting_for_ai_preview, F.data == "ai_edit_q")
async def start_edit_ai_question(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CreateCardStates.waiting_for_edit_question)
    await callback.message.answer(
        "✏️ **Edit Question**\n\nPlease type the updated **Question** text below:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(CreateCardStates.waiting_for_ai_preview, F.data == "ai_edit_a")
async def start_edit_ai_answer(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CreateCardStates.waiting_for_edit_answer)
    await callback.message.answer(
        "✏️ **Edit Answer**\n\nPlease type the updated **Answer** text below:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(CreateCardStates.waiting_for_ai_preview, F.data == "ai_regen")
async def process_ai_regenerate(callback: CallbackQuery, state: FSMContext):
    await callback.answer("Regenerating AI card...")
    await callback.message.delete()
    await generate_and_show_ai_preview(callback.message, state)

@router.callback_query(CreateCardStates.waiting_for_ai_preview, F.data == "ai_cancel")
async def process_ai_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ AI card creation cancelled.")
    await callback.message.answer("Main Menu", reply_markup=get_main_keyboard())
    await callback.answer()

# --- EDIT RESPONSES HANDLERS ---
@router.message(CreateCardStates.waiting_for_edit_question)
async def process_edited_question(message: Message, state: FSMContext):
    new_q = message.text.strip()
    if not new_q:
        await message.answer("Please enter a valid non-empty question.")
        return
        
    await state.update_data(question=new_q)
    await state.set_state(CreateCardStates.waiting_for_ai_preview)
    
    data = await state.get_data()
    category = data.get("category", "General")
    preset_text = data.get("preset_text", "AI Card")
    answer = data.get("answer", "")
    
    preview_text = (
        "🤖 **AI Flashcard Preview (Updated Question)**\n\n"
        f"📁 **Category:** {category}\n"
        f"🎯 **Preset:** {preset_text}\n\n"
        f"❓ **Question:**\n{new_q}\n\n"
        f"💡 **Answer:**\n{answer}\n\n"
        "✨ *Would you like to save this card, edit it further, or regenerate?*"
    )
    await message.answer(preview_text, reply_markup=get_ai_preview_keyboard(), parse_mode="Markdown")

@router.message(CreateCardStates.waiting_for_edit_answer)
async def process_edited_answer(message: Message, state: FSMContext):
    new_a = message.text.strip()
    if not new_a:
        await message.answer("Please enter a valid non-empty answer.")
        return
        
    await state.update_data(answer=new_a)
    await state.set_state(CreateCardStates.waiting_for_ai_preview)
    
    data = await state.get_data()
    category = data.get("category", "General")
    preset_text = data.get("preset_text", "AI Card")
    question = data.get("question", "")
    
    preview_text = (
        "🤖 **AI Flashcard Preview (Updated Answer)**\n\n"
        f"📁 **Category:** {category}\n"
        f"🎯 **Preset:** {preset_text}\n\n"
        f"❓ **Question:**\n{question}\n\n"
        f"💡 **Answer:**\n{new_a}\n\n"
        "✨ *Would you like to save this card, edit it further, or regenerate?*"
    )
    await message.answer(preview_text, reply_markup=get_ai_preview_keyboard(), parse_mode="Markdown")

# --- LIST & DELETE CARDS HANDLERS ---
@router.message(F.text == "📚 My Cards")
@router.message(Command("list"))
async def list_cards(message: Message):
    user_id = message.from_user.id
    cards = database.get_user_cards(user_id)
    
    if not cards:
        await message.answer(
            "📭 You don't have any learning cards yet!\n\n"
            "Tap <b>➕ Create Card</b> to start creating your first flashcard.",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
        return
        
    response = "📚 <b>Your Learning Cards:</b>\n\n"
    
    by_category = {}
    for card in cards:
        cat = card["category"]
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(card)
        
    for cat, cat_cards in by_category.items():
        cat_escaped = escape(cat)
        response += f"📁 <b>{cat_escaped}</b> ({len(cat_cards)} cards):\n"
        for card in cat_cards:
            q_escaped = escape(card['question'])
            a_escaped = escape(card['answer'])
            stats = f"🎯 Stats: {card['correct_count']}✅ / {card['incorrect_count']}❌"
            response += f"• <b>Q:</b> {q_escaped}\n"
            response += f"  <b>A:</b> {a_escaped}\n"
            response += f"  {stats}\n"
            response += f"  🗑️ Delete: /delete_{card['id']}\n\n"
            
    chunks = [response[i:i+4000] for i in range(0, len(response), 4000)]
    for chunk in chunks:
        try:
            await message.answer(chunk, parse_mode="HTML")
        except Exception as err:
            logger.warning(f"Failed to send HTML formatted list_cards message: {err}. Falling back to plain text.")
            await message.answer(chunk)

@router.message(F.text.regexp(r"^/delete_(\d+)$"))
async def process_delete_command(message: Message):
    match = re.match(r"^/delete_(\d+)$", message.text)
    if not match:
        return
        
    card_id = int(match.group(1))
    user_id = message.from_user.id
    
    success = database.delete_card(card_id, user_id)
    if success:
        await message.answer(f"🗑️ Card ID **{card_id}** has been deleted.", reply_markup=get_main_keyboard(), parse_mode="Markdown")
    else:
        await message.answer(f"❌ Could not delete card. Card ID **{card_id}** was not found or is not owned by you.", reply_markup=get_main_keyboard(), parse_mode="Markdown")
