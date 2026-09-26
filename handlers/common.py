from aiogram import Router, F
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from html import escape
import logging

import database
from keyboards import get_main_keyboard, get_share_invite_confirm_keyboard

logger = logging.getLogger(__name__)

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, state: FSMContext):
    # Clear any active state
    await state.clear()
    
    payload = command.args
    if payload:
        if payload.startswith("copy_") or payload.startswith("collab_"):
            token = payload.split("_", 1)[1]
            share_info = database.get_deck_share_info(token)
            if not share_info:
                await message.answer(
                    "❌ <b>Invalid or Expired Link</b>\n\n"
                    "This shared deck invitation could not be found or has expired.",
                    reply_markup=get_main_keyboard(),
                    parse_mode="HTML"
                )
                return

            deck_name = escape(share_info["deck_name"])
            card_count = share_info["card_count"]
            share_type = share_info["share_type"]

            if share_type == "collab":
                invite_text = (
                    f"🤝 <b>Collaborative Deck Invitation!</b>\n\n"
                    f"You have been invited to collaborate on deck <b>'{deck_name}'</b> ({card_count} cards).\n\n"
                    "<b>In a Collaborative Deck:</b>\n"
                    "• Both of you can add new flashcards to this deck\n"
                    "• Each of you has your own independent study schedule & SRS stats\n"
                    "• If you delete a card, it hides it for you; it is only deleted from the deck if both members delete it!\n\n"
                    "Would you like to join this collaborative deck?"
                )
            else:
                invite_text = (
                    f"📋 <b>Shared Deck Copy!</b>\n\n"
                    f"You have received a copy of deck <b>'{deck_name}'</b> ({card_count} cards).\n\n"
                    "<b>Snapshot Copy:</b>\n"
                    "• All current flashcards will be copied into your personal decks\n"
                    "• Future changes by either of you will not affect each other\n\n"
                    "Would you like to import this deck into your collection?"
                )

            kb = get_share_invite_confirm_keyboard(token, share_type)
            await message.answer(invite_text, reply_markup=kb, parse_mode="HTML")
            return

    await show_welcome_help(message)

@router.message(F.text == "ℹ️ Help")
@router.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext):
    await state.clear()
    await show_welcome_help(message)

async def show_welcome_help(message: Message):
    welcome_text = (
        "👋 **Welcome to the Learning Companion Bot!**\n\n"
        "This bot is designed to help you study and retain knowledge using interactive flashcards.\n\n"
        "**Available Features:**\n"
        "➕ **Create Card**: Create flashcards either **manually** or **assisted by AI**!\n"
        "   • 🤖 **AI-Assisted**: Use pre-set prompts (e.g. *Language Learning*, *Definitions*, *Programming*, *Trivia*) or your own *Custom Prompt* to generate cards automatically!\n"
        "   • ✏️ **Card Editing**: Preview AI-generated cards and edit Question or Answer before saving.\n"
        "📚 **My Cards**: View, organize, delete, and 🔗 **share your decks** (via Snapshot Copy or Collaborative Shared Decks)!\n"
        "🎯 **Study/Quiz**: Quiz yourself on specific categories or all flashcards.\n"
        "❌ **Cancel**: Type `/cancel` or tap \"❌ Cancel\" at any time.\n\n"
        "🔑 *Note: AI card creation requires setting `GEMINI_API_KEY` in `.env` file.*\n\n"
        "Use the menu below to get started!"
    )
    await message.answer(welcome_text, reply_markup=get_main_keyboard(), parse_mode="Markdown")

@router.callback_query(F.data.startswith("confirm_join_"))
async def process_confirm_join_collab(callback: CallbackQuery):
    token = callback.data.split("confirm_join_")[1]
    user_id = callback.from_user.id
    
    success, reason, data = database.join_collaborative_deck(user_id, token)
    if success:
        deck_name = escape(data.get("deck_name", ""))
        card_count = data.get("card_count", 0)
        await callback.message.edit_text(
            f"🎉 <b>Joined Collaborative Deck!</b>\n\n"
            f"You are now a collaborator on deck <b>'{deck_name}'</b> ({card_count} cards).\n\n"
            "• You can study it right now from <b>🎯 Study/Quiz</b>\n"
            "• You can add cards to it using <b>➕ Create Card</b>\n"
            "• Cards deleted by you are hidden for you, and only removed when both members delete them.",
            parse_mode="HTML"
        )
        sender_id = data.get("sender_id")
        if sender_id and sender_id != user_id:
            try:
                user_name = callback.from_user.full_name or f"User #{user_id}"
                await callback.bot.send_message(
                    chat_id=sender_id,
                    text=f"👋 <b>{escape(user_name)}</b> has joined your collaborative deck <b>'{deck_name}'</b>!",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.warning(f"Failed to notify owner {sender_id}: {e}")
    elif reason == "already_member":
        deck_name = escape(data.get("deck_name", "this"))
        await callback.message.edit_text(
            f"ℹ️ You are already a member of collaborative deck <b>'{deck_name}'</b>.",
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            "❌ <b>Unable to join deck.</b>\nThe invite link may have expired or is invalid.",
            parse_mode="HTML"
        )
    await callback.answer()

@router.callback_query(F.data.startswith("confirm_import_"))
async def process_confirm_import_copy(callback: CallbackQuery):
    token = callback.data.split("confirm_import_")[1]
    user_id = callback.from_user.id
    
    imported_count, dest_cat = database.import_deck_copy(user_id, token)
    if imported_count > 0:
        await callback.message.edit_text(
            f"📥 <b>Deck Imported Successfully!</b>\n\n"
            f"Created deck <b>'{escape(dest_cat)}'</b> with <b>{imported_count} cards</b>.\n\n"
            "You can now study it anytime from <b>🎯 Study/Quiz</b>.",
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            "❌ <b>Failed to import deck.</b>\nThe deck might be empty or the link has expired.",
            parse_mode="HTML"
        )
    await callback.answer()

@router.callback_query(F.data == "decline_share_invite")
async def process_decline_share_invite(callback: CallbackQuery):
    await callback.message.edit_text("❌ Invitation declined.")
    await callback.answer()

@router.message(Command("cancel"))
@router.message(F.text == "❌ Cancel")
@router.message(F.text.casefold() == "cancel")
async def cmd_cancel(message: Message, state: FSMContext):
    current_state = await state.get_state()
    state_data = await state.get_data()
    study_msg_id = state_data.get("study_msg_id")
    
    if study_msg_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=study_msg_id,
                text="🏁 <b>Study session ended.</b>",
                parse_mode="HTML"
            )
        except Exception:
            pass

    if current_state is None:
        await message.answer("Nothing is currently active.", reply_markup=get_main_keyboard())
        return
        
    await state.clear()
    await message.answer("Action cancelled.", reply_markup=get_main_keyboard())
