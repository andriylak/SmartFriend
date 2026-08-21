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

def get_reveal_keyboard(card_id: int):
    # Inline keyboard to show the answer for a card
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="👁️ Show Answer", callback_data=f"reveal_{card_id}"))
    return builder.as_markup()

def get_evaluation_keyboard(card_id: int):
    # Inline keyboard for user to grade themselves
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="✅ Got it Right", callback_data=f"grade_correct_{card_id}"),
        InlineKeyboardButton(text="❌ Got it Wrong", callback_data=f"grade_incorrect_{card_id}")
    )
    builder.adjust(2)
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
        InlineKeyboardButton(text="🔄 Regenerate", callback_data="ai_regen"),
        InlineKeyboardButton(text="❌ Cancel", callback_data="ai_cancel")
    )
    builder.adjust(1, 2, 2)
    return builder.as_markup()

def get_categories_keyboard(categories: list):
    builder = InlineKeyboardBuilder()
    # Add an option to quiz from all categories
    builder.add(InlineKeyboardButton(text="🌐 All Categories", callback_data="quiz_cat_all"))
    
    # Add each category as a button
    for cat in categories:
        builder.add(InlineKeyboardButton(text=f"📁 {cat}", callback_data=f"quiz_cat_{cat}"))
        
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
    buttons.append([KeyboardButton(text="❌ Cancel")])
    
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        placeholder="Enter topic, word, or phrase..."
    )

