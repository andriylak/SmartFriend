import re
import math
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
from ai_service import format_comment
from keyboards import (
    get_main_keyboard,
    get_cancel_keyboard,
    get_skip_keyboard,
    get_card_creation_mode_keyboard,
    get_ai_prompt_presets_keyboard,
    get_source_languages_keyboard,
    get_target_languages_keyboard,
    get_ai_preview_keyboard,
    get_category_selection_reply_keyboard,
    get_ai_topic_keyboard,
    get_list_categories_keyboard,
    get_pagination_keyboard
)

logger = logging.getLogger(__name__)

router = Router()

PRESET_NAME_MAP = {
    "language": "🌐 Language Learning",
    "definitions": "📚 Definitions & Concepts",
    "programming": "💻 Programming & Syntax",
    "trivia": "🧠 General Knowledge",
    "custom": "✏️ Custom Prompt"
}

class CreateCardStates(StatesGroup):
    waiting_for_mode = State()
    waiting_for_category = State()
    waiting_for_question = State()
    waiting_for_answer = State()
    waiting_for_comment = State()
    waiting_for_ai_prompt_preset = State()
    waiting_for_source_language = State()
    waiting_for_target_language = State()
    waiting_for_ai_custom_prompt = State()
    waiting_for_ai_topic = State()
    waiting_for_ai_preview = State()
    waiting_for_edit_question = State()
    waiting_for_edit_answer = State()
    waiting_for_edit_comment = State()
    waiting_for_edit_question = State()
    waiting_for_edit_answer = State()

class ListCardsStates(StatesGroup):
    browsing_deck = State()

# Step 0: Start creation process (Deck-First)
@router.message(F.text == "➕ Create Card")
@router.message(Command("create"))
async def start_create_card(message: Message, state: FSMContext):
    await state.clear()
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
        
    await state.set_state(CreateCardStates.waiting_for_category)
    await message.answer(
        prompt_intro,
        reply_markup=category_kb,
        parse_mode="Markdown"
    )

# Step 1: Process Category and check for saved deck settings
@router.message(CreateCardStates.waiting_for_category)
async def process_category(message: Message, state: FSMContext):
    category = message.text.strip()
    if not category:
        await message.answer("Please enter a valid category name.")
        return
        
    await state.update_data(category=category)
    user_id = message.from_user.id
    deck_setting = database.get_deck_setting(user_id, category)
    
    if deck_setting:
        preset_key = deck_setting["preset_key"]
        source_language = deck_setting.get("source_language")
        target_language = deck_setting.get("target_language")
        custom_prompt = deck_setting.get("custom_prompt")
        preset_text = PRESET_NAME_MAP.get(preset_key, "AI Card")
        
        await state.update_data(
            is_ai=True,
            preset_key=preset_key,
            preset_text=preset_text,
            source_language=source_language,
            target_language=target_language,
            custom_prompt=custom_prompt,
            has_saved_prompt=True
        )
        await state.set_state(CreateCardStates.waiting_for_ai_topic)
        
        if preset_key == "language":
            s_lang = source_language or "Spanish"
            t_lang = target_language or "English"
            setting_desc = f"*{preset_text}* (FROM: *{s_lang}* ➔ TO: *{t_lang}*)"
        elif preset_key == "custom" and custom_prompt:
            setting_desc = f"*{preset_text}* (*{custom_prompt}*)"
        else:
            setting_desc = f"*{preset_text}*"
            
        await message.answer(
            f"🤖 **AI Flashcard Assistant** (Deck: *{category}*)\n\n"
            f"📌 **Saved Deck Setting:** {setting_desc}\n\n"
            "What word, phrase, or topic do you want the AI to create a card for?\n\n"
            "*(Or tap **✍️ Manual Card** below to write a manual question/answer)*",
            reply_markup=get_ai_topic_keyboard(has_saved_prompt=True),
            parse_mode="Markdown"
        )
    else:
        await state.set_state(CreateCardStates.waiting_for_mode)
        await message.answer(
            f"⚙️ **How would you like to create your flashcard for *{category}*?**\n\n"
            "🤖 **AI-Assisted Card**: Generate flashcards automatically using AI (with pre-set prompts like *Language Learning*, *Definitions*, or your own *Custom Prompt*).\n"
            "✍️ **Manual Card**: Type the Question and Answer yourself.",
            reply_markup=get_card_creation_mode_keyboard(),
            parse_mode="Markdown"
        )

# Step 2: Handle creation mode selection if deck has no saved setting
@router.message(CreateCardStates.waiting_for_mode)
async def process_creation_mode(message: Message, state: FSMContext):
    choice = message.text.strip()
    data = await state.get_data()
    category = data.get("category", "General")
    
    if choice == "✍️ Manual Card":
        await state.update_data(is_ai=False)
        await state.set_state(CreateCardStates.waiting_for_question)
        
        await message.answer(
            f"✍️ **Manual Flashcard** (Category: *{category}*)\n\n"
            "Please type the **Question** or prompt for the front side of your learning card:",
            reply_markup=get_cancel_keyboard(),
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
        await state.set_state(CreateCardStates.waiting_for_ai_prompt_preset)
        
        await message.answer(
            f"🎯 **AI Step 2: Choose Prompt Type** (Category: *{category}*)\n\n"
            "Select one of the default AI prompt presets below, or choose ✏️ **Custom Prompt** to write your own instructions:",
            reply_markup=get_ai_prompt_presets_keyboard(),
            parse_mode="Markdown"
        )
    else:
        await message.answer("Please select an option from the menu: 🤖 **AI-Assisted Card** or ✍️ **Manual Card**.")

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
        
    await state.update_data(answer=answer)
    await state.set_state(CreateCardStates.waiting_for_comment)
    
    await message.answer(
        "📌 **Step 3: Additional Info / Comment (Optional)**\n\n"
        "Enter any additional details, phonetics, or example sentences for this card, or tap **⏩ Skip**:",
        reply_markup=get_skip_keyboard(),
        parse_mode="Markdown"
    )

@router.message(CreateCardStates.waiting_for_comment)
async def process_comment(message: Message, state: FSMContext):
    text = message.text.strip()
    comment = "" if text == "⏩ Skip" else text
    
    user_data = await state.get_data()
    category = user_data.get("category", "General")
    question = user_data.get("question")
    answer = user_data.get("answer")
    
    card_id = database.add_card(
        user_id=message.from_user.id,
        question=question,
        answer=answer,
        category=category,
        comment=comment
    )
    
    # Stay in deck creation loop for the active category
    await state.set_state(CreateCardStates.waiting_for_question)
    await state.update_data(category=category, question=None, answer=None, comment=None)
    
    comment_info = f"\n**Comment:** {comment}" if comment else ""
    success_text = (
        f"🎉 **Card #{card_id} Saved!** (Deck: *{category}*)\n\n"
        f"**Question:** {question}\n"
        f"**Answer:** {answer}"
        f"{comment_info}\n\n"
        "✍️ **Add another card to this deck:** Type the **Question** for your next card below\n"
        "*(or tap **❌ Cancel** when finished)*:"
    )
    await message.answer(success_text, reply_markup=get_cancel_keyboard(), parse_mode="Markdown")

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
        await state.set_state(CreateCardStates.waiting_for_source_language)
        await message.answer(
            "🌐 **AI Step 3: Choose Source (Learning) Language**\n\n"
            "What language are you translating **FROM**?\n"
            "(e.g., *Spanish*, *German*, *Ukrainian*, *English*, *French*)",
            reply_markup=get_source_languages_keyboard(),
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

@router.message(CreateCardStates.waiting_for_source_language)
async def process_source_language(message: Message, state: FSMContext):
    raw_lang = message.text.strip()
    if not raw_lang:
        await message.answer("Please enter or select a valid source language.")
        return
        
    clean_lang = re.sub(r"^[^\w\s]+", "", raw_lang).strip()
    source_language = clean_lang if clean_lang else raw_lang
    
    await state.update_data(source_language=source_language)
    await state.set_state(CreateCardStates.waiting_for_target_language)
    
    await message.answer(
        "🌐 **AI Step 4: Choose Target Translation Language**\n\n"
        f"Translate FROM: *{source_language}*\n\n"
        "What language do you want the word, phrase, and example sentences translated **TO**?\n"
        "(e.g., *English*, *Ukrainian*, *Spanish*, *German*, *French*)",
        reply_markup=get_target_languages_keyboard(),
        parse_mode="Markdown"
    )

@router.message(CreateCardStates.waiting_for_target_language)
async def process_target_language(message: Message, state: FSMContext):
    raw_lang = message.text.strip()
    if not raw_lang:
        await message.answer("Please enter or select a valid target language.")
        return
        
    clean_lang = re.sub(r"^[^\w\s]+", "", raw_lang).strip()
    target_language = clean_lang if clean_lang else raw_lang
    
    await state.update_data(target_language=target_language)
    
    data = await state.get_data()
    category = data.get("category", "General")
    source_language = data.get("source_language", "Spanish")
    
    database.save_deck_setting(
        message.from_user.id,
        category,
        "language",
        source_language=source_language,
        target_language=target_language
    )
    await state.update_data(has_saved_prompt=True)
    
    await state.set_state(CreateCardStates.waiting_for_ai_topic)
    
    await message.answer(
        "📝 **AI Step 5: Enter Topic, Word, or Phrase**\n\n"
        f"Selected Preset: *🌐 Language Learning*\n"
        f"Translate FROM: *{source_language}*\n"
        f"Translate TO: *{target_language}*\n\n"
        "What word, phrase, or sentence do you want to learn? "
        "(e.g., *el gato*, *la manzana*, *gatoo*)",
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
        user_id = message.from_user.id
        data = await state.get_data()
        category = data.get("category", "General")
        deck_setting = database.get_deck_setting(user_id, category)
        
        current_setting_str = "None"
        full_instruction = ""
        
        target_dict = deck_setting if deck_setting else data
        preset_key = target_dict.get("preset_key")
        
        if preset_key:
            preset_text = PRESET_NAME_MAP.get(preset_key, "AI Card")
            s_lang = target_dict.get("source_language") or "Spanish"
            t_lang = target_dict.get("target_language") or "English"
            c_prompt = target_dict.get("custom_prompt")
            
            if preset_key == "language":
                current_setting_str = f"*{preset_text}* (FROM: *{s_lang}* ➔ TO: *{t_lang}*)"
            elif preset_key == "custom" and c_prompt:
                current_setting_str = f"*{preset_text}* (*{c_prompt}*)"
            else:
                current_setting_str = f"*{preset_text}*"
                
            full_instruction = ai_service.get_full_prompt_text(
                preset_key=preset_key,
                source_language=s_lang,
                target_language=t_lang,
                custom_prompt=c_prompt
            )
            
        await state.set_state(CreateCardStates.waiting_for_ai_prompt_preset)
        
        prompt_detail = f"\n\n📜 **Full AI System Instruction Prompt:**\n```\n{full_instruction}\n```" if full_instruction else ""
        
        await message.answer(
            f"⚙️ **Change Deck Prompt** (Category: *{category}*)\n\n"
            f"📌 **Current Preset:** {current_setting_str}"
            f"{prompt_detail}\n\n"
            "Select a new prompt preset below to update the AI instructions for this deck:",
            reply_markup=get_ai_prompt_presets_keyboard(),
            parse_mode="Markdown"
        )
        return

    if topic == "✍️ Manual Card":
        data = await state.get_data()
        category = data.get("category", "General")
        await state.update_data(is_ai=False)
        await state.set_state(CreateCardStates.waiting_for_question)
        await message.answer(
            f"✍️ **Manual Flashcard** (Category: *{category}*)\n\n"
            "Please type the **Question** or prompt for the front side of your learning card:",
            reply_markup=get_cancel_keyboard(),
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
    source_language = data.get("source_language")
    target_language = data.get("target_language")
    category = data.get("category", "General")
    
    wait_msg = await message.answer("🤖 *Generating flashcard with AI... Please wait a moment.*", parse_mode="Markdown")
    
    try:
        card_data = await ai_service.generate_ai_card(
            preset_key=preset_key,
            topic=topic,
            custom_prompt=custom_prompt,
            source_language=source_language,
            target_language=target_language
        )
        question = card_data["question"]
        answer = card_data["answer"]
        comment = card_data.get("comment", "")
        correction_note = card_data.get("correction_note")
        
        await state.update_data(question=question, answer=answer, comment=comment)
        await state.set_state(CreateCardStates.waiting_for_ai_preview)
        
        # Delete status message
        try:
            await wait_msg.delete()
        except Exception:
            pass
            
        if preset_key == "language":
            s_lang = source_language or "Spanish"
            t_lang = target_language or "English"
            lang_str = f"🌐 **Translate:** {s_lang} ➔ {t_lang}\n"
        else:
            lang_str = ""

        correction_str = f"💡 **Note:** {correction_note}\n" if correction_note else ""
        comment_formatted = format_comment(comment, fmt="markdown") if comment else ""
        comment_str = f"📌 **Additional Info:**\n{comment_formatted}\n\n" if comment else ""
            
        preview_text = (
            "🤖 **AI Flashcard Preview**\n\n"
            f"📁 **Category:** {category}\n"
            f"🎯 **Preset:** {preset_text}\n"
            f"{lang_str}"
            f"{correction_str}\n"
            f"❓ **Question:**\n{question}\n\n"
            f"💡 **Answer:**\n{answer}\n\n"
            f"{comment_str}"
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
    comment = data.get("comment", "")
    
    if not question or not answer:
        await callback.answer("Error: Missing card content.", show_alert=True)
        return
        
    card_id = database.add_card(
        user_id=callback.from_user.id,
        question=question,
        answer=answer,
        category=category,
        comment=comment
    )
    
    # Stay in deck creation loop for the active category with saved prompt settings
    await state.set_state(CreateCardStates.waiting_for_ai_topic)
    await state.update_data(
        category=category,
        topic=None,
        question=None,
        answer=None,
        comment=None
    )
    
    comment_formatted = format_comment(comment, fmt="markdown") if comment else ""
    comment_info = f"\n**Comment:**\n{comment_formatted}" if comment else ""
    await callback.message.edit_text(
        f"🎉 **Card Pair Saved!** (Dual SRS: Q ➔ A & A ➔ Q | Deck: *{category}*)\n\n"
        f"**Question:** {question}\n"
        f"**Answer:** {answer}"
        f"{comment_info}",
        parse_mode="Markdown"
    )
    
    await callback.message.answer(
        f"🤖 **Add another card to deck *{category}***\n\n"
        "What word, phrase, or topic do you want the AI to create next?\n\n"
        "*(Or tap **✍️ Manual Card** / **❌ Cancel** below)*",
        reply_markup=get_ai_topic_keyboard(has_saved_prompt=True),
        parse_mode="Markdown"
    )
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

@router.callback_query(CreateCardStates.waiting_for_ai_preview, F.data == "ai_edit_c")
async def start_edit_ai_comment(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CreateCardStates.waiting_for_edit_comment)
    await callback.message.answer(
        "✏️ **Edit Comment / Additional Info**\n\nPlease type the updated **Comment** text below (or type `/skip` to clear):",
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
    data = await state.get_data()
    category = data.get("category", "General")
    user_id = callback.from_user.id
    deck_setting = database.get_deck_setting(user_id, category)
    has_saved_prompt = deck_setting is not None or data.get("has_saved_prompt", False)

    await state.set_state(CreateCardStates.waiting_for_ai_topic)
    await state.update_data(
        category=category,
        topic=None,
        question=None,
        answer=None,
        comment=None
    )

    await callback.message.edit_text("❌ AI card creation cancelled.")
    await callback.message.answer(
        f"🤖 **Add another card to deck *{category}***\n\n"
        "What word, phrase, or topic do you want the AI to create next?\n\n"
        "*(Or tap **✍️ Manual Card** / **❌ Cancel** below)*",
        reply_markup=get_ai_topic_keyboard(has_saved_prompt=has_saved_prompt),
        parse_mode="Markdown"
    )
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
    comment = data.get("comment", "")
    comment_formatted = format_comment(comment, fmt="markdown") if comment else ""
    comment_str = f"📌 **Additional Info:**\n{comment_formatted}\n\n" if comment else ""
    
    preview_text = (
        "🤖 **AI Flashcard Preview (Updated Question)**\n\n"
        f"📁 **Category:** {category}\n"
        f"🎯 **Preset:** {preset_text}\n\n"
        f"❓ **Question:**\n{new_q}\n\n"
        f"💡 **Answer:**\n{answer}\n\n"
        f"{comment_str}"
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
    comment = data.get("comment", "")
    comment_formatted = format_comment(comment, fmt="markdown") if comment else ""
    comment_str = f"📌 **Additional Info:**\n{comment_formatted}\n\n" if comment else ""
    
    preview_text = (
        "🤖 **AI Flashcard Preview (Updated Answer)**\n\n"
        f"📁 **Category:** {category}\n"
        f"🎯 **Preset:** {preset_text}\n\n"
        f"❓ **Question:**\n{question}\n\n"
        f"💡 **Answer:**\n{new_a}\n\n"
        f"{comment_str}"
        "✨ *Would you like to save this card, edit it further, or regenerate?*"
    )
    await message.answer(preview_text, reply_markup=get_ai_preview_keyboard(), parse_mode="Markdown")

@router.message(CreateCardStates.waiting_for_edit_comment)
async def process_edited_comment(message: Message, state: FSMContext):
    new_c = message.text.strip()
    if new_c.lower() in ["/skip", "skip"]:
        new_c = ""
        
    await state.update_data(comment=new_c)
    await state.set_state(CreateCardStates.waiting_for_ai_preview)
    
    data = await state.get_data()
    category = data.get("category", "General")
    preset_text = data.get("preset_text", "AI Card")
    question = data.get("question", "")
    answer = data.get("answer", "")
    comment_formatted = format_comment(new_c, fmt="markdown") if new_c else ""
    comment_str = f"📌 **Additional Info:**\n{comment_formatted}\n\n" if new_c else ""
    
    preview_text = (
        "🤖 **AI Flashcard Preview (Updated Comment)**\n\n"
        f"📁 **Category:** {category}\n"
        f"🎯 **Preset:** {preset_text}\n\n"
        f"❓ **Question:**\n{question}\n\n"
        f"💡 **Answer:**\n{answer}\n\n"
        f"{comment_str}"
        "✨ *Would you like to save this card, edit it further, or regenerate?*"
    )
    await message.answer(preview_text, reply_markup=get_ai_preview_keyboard(), parse_mode="Markdown")

CARDS_PER_PAGE = 5

def format_card_page_text(cards: list, category_name: str, page: int, total_pages: int) -> str:
    start_idx = (page - 1) * CARDS_PER_PAGE
    end_idx = start_idx + CARDS_PER_PAGE
    page_cards = cards[start_idx:end_idx]
    
    if category_name != "all":
        cat_escaped = escape(category_name)
        text = f"📚 <b>Deck: {cat_escaped}</b> ({len(cards)} cards - Page {page}/{total_pages})\n"
    else:
        text = f"📚 <b>All Learning Cards</b> ({len(cards)} cards - Page {page}/{total_pages})\n"
        
    text += "🔍 <i>Type any word or phrase to search cards in this deck!</i>\n\n"
        
    for card in page_cards:
        q_escaped = escape(card['question'])
        stats = f"🎯 Stats: {card['correct_count']}✅ / {card['incorrect_count']}❌"
        if category_name == "all":
            cat_escaped = escape(card['category'])
            text += f"📁 <b>{cat_escaped}</b>\n"
        text += f"• <b>Q:</b> {q_escaped}\n"
        text += f"  {stats}\n"
        text += f"  🗑️ Delete: /delete_{card['id']}\n\n"
        
    return text

# --- LIST & DELETE CARDS HANDLERS ---
@router.message(F.text == "📚 My Cards")
@router.message(Command("list"))
async def list_cards(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    categories = database.get_user_categories(user_id)
    
    if not categories:
        await message.answer(
            "📭 You don't have any learning cards yet!\n\n"
            "Tap <b>➕ Create Card</b> to start creating your first flashcard.",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
        return
        
    await message.answer(
        "📚 <b>My Cards</b>\n\n"
        "Please select a deck to view your flashcards:",
        reply_markup=get_list_categories_keyboard(categories),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("list_cat_"))
async def process_list_category_selection(callback: CallbackQuery, state: FSMContext):
    category_data = callback.data.split("list_cat_")[1]
    user_id = callback.from_user.id
    
    selected_cat = None if category_data == "all" else category_data
    cards = database.get_user_cards(user_id, category=selected_cat)
    
    if not cards:
        await callback.message.answer(
            "📭 No cards found in this deck!",
            reply_markup=get_main_keyboard()
        )
        await callback.answer()
        return

    cat_key = category_data
    await state.set_state(ListCardsStates.browsing_deck)
    await state.update_data(active_category=cat_key)
    
    total_pages = math.ceil(len(cards) / CARDS_PER_PAGE)
    current_page = 1
    
    page_text = format_card_page_text(cards, cat_key, current_page, total_pages)
    kb = get_pagination_keyboard(cat_key, current_page, total_pages)
    
    try:
        await callback.message.edit_text(page_text, reply_markup=kb, parse_mode="HTML")
    except Exception as err:
        logger.warning(f"Failed to edit message with HTML formatting: {err}. Falling back to plain text.")
        await callback.message.edit_text(page_text, reply_markup=kb)
        
    await callback.answer()

@router.callback_query(F.data.startswith("list_page|"))
async def process_list_page(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("|")
    cat_key = parts[1]
    page = int(parts[2])
    user_id = callback.from_user.id
    
    selected_cat = None if cat_key == "all" else cat_key
    cards = database.get_user_cards(user_id, category=selected_cat)
    
    if not cards:
        await callback.message.edit_text("📭 No cards found.")
        await callback.answer()
        return
        
    await state.set_state(ListCardsStates.browsing_deck)
    await state.update_data(active_category=cat_key)
    
    total_pages = math.ceil(len(cards) / CARDS_PER_PAGE)
    if page < 1:
        page = 1
    elif page > total_pages:
        page = total_pages
        
    page_text = format_card_page_text(cards, cat_key, page, total_pages)
    kb = get_pagination_keyboard(cat_key, page, total_pages)
    
    try:
        await callback.message.edit_text(page_text, reply_markup=kb, parse_mode="HTML")
    except Exception as err:
        logger.warning(f"Failed to edit message with HTML formatting: {err}. Falling back to plain text.")
        await callback.message.edit_text(page_text, reply_markup=kb)
        
    await callback.answer()

@router.callback_query(F.data == "list_back_decks")
async def process_list_back_decks(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    categories = database.get_user_categories(user_id)
    
    if not categories:
        await callback.message.edit_text("📭 You don't have any learning cards yet!")
        await callback.answer()
        return
        
    await callback.message.edit_text(
        "📚 <b>My Cards</b>\n\n"
        "Please select a deck to view your flashcards:",
        reply_markup=get_list_categories_keyboard(categories),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "noop")
async def process_noop_callback(callback: CallbackQuery):
    await callback.answer()

@router.message(ListCardsStates.browsing_deck, ~F.text.startswith("/"))
async def process_deck_search(message: Message, state: FSMContext):
    search_query = message.text.strip()
    
    if search_query in ["➕ Create Card", "🎯 Study/Quiz", "📚 My Cards", "ℹ️ Help", "❌ Cancel"]:
        await state.clear()
        return
        
    data = await state.get_data()
    cat_key = data.get("active_category", "all")
    user_id = message.from_user.id
    
    matches = database.search_user_cards(user_id, search_query, category=cat_key)
    
    if not matches:
        deck_name = escape(cat_key) if cat_key != "all" else "all decks"
        await message.answer(
            f"🔍 <b>No matching cards found for:</b> <i>{escape(search_query)}</i> in <b>{deck_name}</b>.\n\n"
            "Try typing another word or phrase!",
            parse_mode="HTML"
        )
        return
        
    deck_title = f"in deck <b>{escape(cat_key)}</b>" if cat_key != "all" else "in <b>all decks</b>"
    result_text = f"🔎 <b>Closest matches for '{escape(search_query)}'</b> {deck_title}:\n\n"
    
    for card in matches[:5]:
        q_escaped = escape(card['question'])
        cat_escaped = escape(card['category'])
        stats = f"🎯 Stats: {card['correct_count']}✅ / {card['incorrect_count']}❌"
        result_text += f"📁 <b>{cat_escaped}</b>\n"
        result_text += f"• <b>Q:</b> {q_escaped}\n"
        result_text += f"  {stats}\n"
        result_text += f"  🗑️ Delete: /delete_{card['id']}\n\n"
        
    await message.answer(result_text, parse_mode="HTML")



@router.message(F.text.regexp(r"^/delete_(\d+)$"))
async def process_delete_command(message: Message):
    match = re.match(r"^/delete_(\d+)$", message.text)
    if not match:
        return
        
    card_id = int(match.group(1))
    user_id = message.from_user.id
    
    success = database.delete_card(card_id, user_id)
    if success:
        await message.answer(f"🗑️ Card ID **{card_id}** (both sides) has been deleted.", reply_markup=get_main_keyboard(), parse_mode="Markdown")
    else:
        await message.answer(f"❌ Could not delete card. Card ID **{card_id}** was not found or is not owned by you.", reply_markup=get_main_keyboard(), parse_mode="Markdown")
