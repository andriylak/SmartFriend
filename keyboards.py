from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

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

def get_categories_keyboard(categories: list):
    builder = InlineKeyboardBuilder()
    # Add an option to quiz from all categories
    builder.add(InlineKeyboardButton(text="🌐 All Categories", callback_data="quiz_cat_all"))
    
    # Add each category as a button
    for cat in categories:
        builder.add(InlineKeyboardButton(text=f"📁 {cat}", callback_data=f"quiz_cat_{cat}"))
        
    builder.adjust(1) # one button per row
    return builder.as_markup()
