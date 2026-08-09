import re
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database
from keyboards import get_main_keyboard, get_cancel_keyboard

router = Router()

class CreateCardStates(StatesGroup):
    waiting_for_category = State()
    waiting_for_question = State()
    waiting_for_answer = State()

@router.message(F.text == "➕ Create Card")
@router.message(Command("create"))
async def start_create_card(message: Message, state: FSMContext):
    await state.set_state(CreateCardStates.waiting_for_category)
    
    # Simple keyboard with 'General' option and 'Cancel'
    category_kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="General")],
            [KeyboardButton(text="❌ Cancel")]
        ],
        resize_keyboard=True,
        placeholder="Enter category name or tap 'General'..."
    )
    
    await message.answer(
        "📁 **Step 1: Category**\n\n"
        "Please enter a category for your card (e.g., *Math*, *Python*, *History*), or tap **General** to use the default.",
        reply_markup=category_kb,
        parse_mode="Markdown"
    )

@router.message(CreateCardStates.waiting_for_category)
async def process_category(message: Message, state: FSMContext):
    category = message.text.strip()
    if not category:
        await message.answer("Please enter a valid non-empty category name.")
        return
        
    await state.update_data(category=category)
    await state.set_state(CreateCardStates.waiting_for_question)
    
    await message.answer(
        "❓ **Step 2: Question**\n\n"
        f"Category selected: *{category}*\n\n"
        "Now, type the **Question** or prompt for the front side of your learning card.",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )

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
    
    # Save to SQLite database
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

@router.message(F.text == "📚 My Cards")
@router.message(Command("list"))
async def list_cards(message: Message):
    user_id = message.from_user.id
    cards = database.get_user_cards(user_id)
    
    if not cards:
        await message.answer(
            "📭 You don't have any learning cards yet!\n\n"
            "Tap **➕ Create Card** to start creating your first flashcard.",
            reply_markup=get_main_keyboard()
        )
        return
        
    response = "📚 **Your Learning Cards:**\n\n"
    
    # Group cards by category for neat presentation
    by_category = {}
    for card in cards:
        cat = card["category"]
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(card)
        
    for cat, cat_cards in by_category.items():
        response += f"📁 **{cat}** ({len(cat_cards)} cards):\n"
        for card in cat_cards:
            stats = f"🎯 Stats: {card['correct_count']}✅ / {card['incorrect_count']}❌"
            response += f"• **Q:** {card['question']}\n"
            response += f"  **A:** {card['answer']}\n"
            response += f"  {stats}\n"
            response += f"  🗑️ Delete: /delete_{card['id']}\n\n"
            
    # Check if response fits inside a single message
    if len(response) > 4000:
        # If it's too long, send in chunks
        for i in range(0, len(response), 4000):
            await message.answer(response[i:i+4000], parse_mode="Markdown")
    else:
        await message.answer(response, parse_mode="Markdown")

# Handle dynamic delete commands like /delete_5
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
