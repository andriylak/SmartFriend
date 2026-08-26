from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Create Card"), KeyboardButton(text="🎯 Study/Quiz")],
            [KeyboardButton(text="📚 My Cards"), KeyboardButton(text="ℹ️ Help")]
        ],
        resize_keyboard=True,
        placeholder="Select an option..."
    )
    return keyboard

def get_cancel_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❌ Cancel")]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_skip_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⏩ Skip")],
            [KeyboardButton(text="❌ Cancel")]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_reveal_keyboard(card_id: int, is_reversed: bool = False):
    # Inline keyboard to show the answer or question for a card
    builder = InlineKeyboardBuilder()
    text = "👁️ Show Question" if is_reversed else "👁️ Show Answer"
    cb = f"reveal_rev_{card_id}" if is_reversed else f"reveal_std_{card_id}"
    builder.add(InlineKeyboardButton(text=text, callback_data=cb))
    return builder.as_markup()

def get_evaluation_keyboard(card_id: int):
    # Inline keyboard for Anki 4-tier SRS grading
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="🔴 Again", callback_data=f"srs_again_{card_id}"),
        InlineKeyboardButton(text="🟠 Hard", callback_data=f"srs_hard_{card_id}"),
        InlineKeyboardButton(text="🟢 Good", callback_data=f"srs_good_{card_id}"),
        InlineKeyboardButton(text="🔵 Easy", callback_data=f"srs_easy_{card_id}")
    )
    builder.adjust(2, 2)
    return builder.as_markup()

def get_study_ahead_keyboard(category: str):
    builder = InlineKeyboardBuilder()
    cat_param = category if category else "all"
    builder.add(
        InlineKeyboardButton(text="⚡ Study All Cards Anyway", callback_data=f"study_ahead_{cat_param}"),
        InlineKeyboardButton(text="🔙 Choose Another Deck", callback_data="study_back_decks")
    )
    builder.adjust(1)
    return builder.as_markup()

def get_delete_card_keyboard(card_id: int):
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="🗑️ Delete Card", callback_data=f"delete_{card_id}"))
    return builder.as_markup()

def get_card_creation_mode_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🤖 AI-Assisted Card"), KeyboardButton(text="✍️ Manual Card")],
            [KeyboardButton(text="❌ Cancel")]
        ],
        resize_keyboard=True,
        placeholder="Choose creation method..."
    )
    return keyboard

def get_ai_prompt_presets_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🌐 Language Learning"), KeyboardButton(text="📚 Definitions & Concepts")],
            [KeyboardButton(text="💻 Programming & Syntax"), KeyboardButton(text="🧠 General Knowledge")],
            [KeyboardButton(text="✏️ Custom Prompt")],
            [KeyboardButton(text="❌ Cancel")]
        ],
        resize_keyboard=True,
        placeholder="Select AI prompt preset..."
    )
    return keyboard

def get_source_languages_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🇪🇸 Spanish"), KeyboardButton(text="🇬🇧 English")],
            [KeyboardButton(text="🇺🇦 Ukrainian"), KeyboardButton(text="🇩🇪 German")],
            [KeyboardButton(text="🇫🇷 French"), KeyboardButton(text="🇮🇹 Italian")],
            [KeyboardButton(text="🇵🇱 Polish")],
            [KeyboardButton(text="❌ Cancel")]
        ],
        resize_keyboard=True,
        placeholder="Choose or type source (learning) language..."
    )
    return keyboard

def get_target_languages_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🇬🇧 English"), KeyboardButton(text="🇺🇦 Ukrainian")],
            [KeyboardButton(text="🇪🇸 Spanish"), KeyboardButton(text="🇩🇪 German")],
            [KeyboardButton(text="🇫🇷 French"), KeyboardButton(text="🇮🇹 Italian")],
            [KeyboardButton(text="🇵🇱 Polish")],
            [KeyboardButton(text="❌ Cancel")]
        ],
        resize_keyboard=True,
        placeholder="Choose or type target language..."
    )
    return keyboard

def get_ai_preview_keyboard():
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="✅ Save Card", callback_data="ai_save"),
        InlineKeyboardButton(text="✏️ Edit Question", callback_data="ai_edit_q"),
        InlineKeyboardButton(text="✏️ Edit Answer", callback_data="ai_edit_a"),
        InlineKeyboardButton(text="✏️ Edit Comment", callback_data="ai_edit_c"),
        InlineKeyboardButton(text="🔄 Regenerate", callback_data="ai_regen"),
        InlineKeyboardButton(text="❌ Cancel", callback_data="ai_cancel")
    )
    builder.adjust(1, 2, 2, 1)
    return builder.as_markup()

def get_categories_keyboard(categories: list, due_counts: dict = None):
    builder = InlineKeyboardBuilder()
    counts = due_counts or {}
    all_due = counts.get("_all_", 0)
    
    # Add an option to quiz from all categories
    builder.add(InlineKeyboardButton(text=f"🌐 All Decks ({all_due} due)", callback_data="quiz_cat_all"))
    
    # Add each category as a button
    for cat in categories:
        cat_due = counts.get(cat, 0)
        builder.add(InlineKeyboardButton(text=f"📁 {cat} ({cat_due} due)", callback_data=f"quiz_cat_{cat}"))
        
    builder.adjust(1) # one button per row
    return builder.as_markup()

def get_category_selection_reply_keyboard(categories: list):
    builder = ReplyKeyboardBuilder()
    
    cats_to_show = list(categories)
    if "General" not in cats_to_show:
        cats_to_show.insert(0, "General")
        
    for cat in cats_to_show:
        builder.add(KeyboardButton(text=cat))
        
    builder.adjust(2)
    builder.row(KeyboardButton(text="❌ Cancel"))
    
    return builder.as_markup(
        resize_keyboard=True,
        placeholder="Select existing deck or type new deck name..."
    )

def get_ai_topic_keyboard(has_saved_prompt: bool = False):
    buttons = []
    if has_saved_prompt:
        buttons.append([KeyboardButton(text="⚙️ Change Deck Prompt")])
    buttons.append([KeyboardButton(text="✍️ Manual Card")])
    buttons.append([KeyboardButton(text="❌ Cancel")])
    
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        placeholder="Enter topic, word, or phrase..."
    )

def get_list_categories_keyboard(categories: list):
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="🌐 All Decks", callback_data="list_cat_all"))
    for cat in categories:
        builder.add(InlineKeyboardButton(text=f"📁 {cat}", callback_data=f"list_cat_{cat}"))
    builder.adjust(1)
    return builder.as_markup()

def get_pagination_keyboard(category: str, current_page: int, total_pages: int):
    builder = InlineKeyboardBuilder()
    
    nav_buttons = []
    if current_page > 1:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"list_page|{category}|{current_page - 1}"))
    
    nav_buttons.append(InlineKeyboardButton(text=f"📄 {current_page}/{total_pages}", callback_data="noop"))
    
    if current_page < total_pages:
        nav_buttons.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"list_page|{category}|{current_page + 1}"))
        
    builder.row(*nav_buttons)
    builder.row(InlineKeyboardButton(text="🔙 Change Deck", callback_data="list_back_decks"))
    
    return builder.as_markup()



