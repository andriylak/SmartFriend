import unittest
from unittest.mock import AsyncMock, patch, MagicMock
import asyncio

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey
from aiogram.types import Message, CallbackQuery, User, Chat

import database
import keyboards
from handlers.cards import (
    CreateCardStates,
    process_ai_topic,
    process_dup_continue,
    process_dup_cancel,
    process_dup_override
)

class TestDuplicateFlow(unittest.TestCase):
    def setUp(self):
        self.storage = MemoryStorage()
        self.user_id = 99999
        self.chat_id = 88888
        self.key = StorageKey(bot_id=1, chat_id=self.chat_id, user_id=self.user_id)
        self.state = FSMContext(storage=self.storage, key=self.key)

    def test_duplicate_warning_keyboard_buttons(self):
        kb = keyboards.get_duplicate_warning_keyboard()
        buttons = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        self.assertIn("ai_dup_continue", buttons)
        self.assertIn("ai_dup_cancel", buttons)

    @patch("database.find_existing_cards_in_deck")
    @patch("handlers.cards.generate_and_show_ai_preview")
    def test_topic_without_duplicate_proceeds_immediately(self, mock_generate, mock_find):
        mock_find.return_value = []
        
        mock_msg = AsyncMock(spec=Message)
        mock_msg.text = "manzana"
        mock_msg.from_user = User(id=self.user_id, is_bot=False, first_name="Tester")
        mock_msg.chat = Chat(id=self.chat_id, type="private")

        async def run_test():
            await self.state.set_state(CreateCardStates.waiting_for_ai_topic)
            await self.state.update_data(category="Spanish")
            await process_ai_topic(mock_msg, self.state)

            # Since no duplicates found, generate_and_show_ai_preview should be called immediately
            mock_generate.assert_called_once()
            state_data = await self.state.get_data()
            self.assertEqual(state_data.get("topic"), "manzana")

        asyncio.run(run_test())

    @patch("database.find_existing_cards_in_deck")
    @patch("handlers.cards.generate_and_show_ai_preview")
    def test_topic_with_duplicate_shows_warning_and_sets_confirm_state(self, mock_generate, mock_find):
        mock_find.return_value = [{
            "id": 10,
            "question": "la manzana",
            "answer": "apple",
            "comment": "feminine noun",
            "category": "Spanish"
        }]

        mock_msg = AsyncMock(spec=Message)
        mock_msg.text = "manzana"
        mock_msg.from_user = User(id=self.user_id, is_bot=False, first_name="Tester")
        mock_msg.chat = Chat(id=self.chat_id, type="private")
        mock_msg.answer = AsyncMock()

        async def run_test():
            await self.state.set_state(CreateCardStates.waiting_for_ai_topic)
            await self.state.update_data(category="Spanish")
            await process_ai_topic(mock_msg, self.state)

            # AI should NOT be called yet!
            mock_generate.assert_not_called()

            # State must transition to waiting_for_duplicate_confirm
            curr_state = await self.state.get_state()
            self.assertEqual(curr_state, CreateCardStates.waiting_for_duplicate_confirm.state)

            # Warning message sent with duplicate info and warning keyboard
            mock_msg.answer.assert_called_once()
            args, kwargs = mock_msg.answer.call_args
            self.assertIn("already exist", args[0])
            self.assertIn("la manzana", args[0])
            self.assertIn("apple", args[0])
            self.assertIsNotNone(kwargs.get("reply_markup"))

        asyncio.run(run_test())

    @patch("handlers.cards.generate_and_show_ai_preview")
    def test_dup_continue_invokes_ai_preview(self, mock_generate):
        mock_callback = AsyncMock(spec=CallbackQuery)
        mock_callback.answer = AsyncMock()
        mock_callback.message = AsyncMock(spec=Message)
        mock_callback.message.delete = AsyncMock()

        async def run_test():
            await self.state.set_state(CreateCardStates.waiting_for_duplicate_confirm)
            await self.state.update_data(category="Spanish", topic="manzana")
            await process_dup_continue(mock_callback, self.state)

            mock_callback.answer.assert_called_once()
            mock_generate.assert_called_once_with(mock_callback.message, self.state)

        asyncio.run(run_test())

    @patch("database.get_deck_setting")
    def test_dup_cancel_resets_to_topic_prompt(self, mock_get_setting):
        mock_get_setting.return_value = {"preset_key": "language"}
        mock_callback = AsyncMock(spec=CallbackQuery)
        mock_callback.from_user = User(id=self.user_id, is_bot=False, first_name="Tester")
        mock_callback.answer = AsyncMock()
        mock_callback.message = AsyncMock(spec=Message)
        mock_callback.message.delete = AsyncMock()
        mock_callback.message.answer = AsyncMock()

        async def run_test():
            await self.state.set_state(CreateCardStates.waiting_for_duplicate_confirm)
            await self.state.update_data(category="Spanish", topic="manzana")
            await process_dup_cancel(mock_callback, self.state)

            curr_state = await self.state.get_state()
            self.assertEqual(curr_state, CreateCardStates.waiting_for_ai_topic.state)
            data = await self.state.get_data()
            self.assertIsNone(data.get("topic"))
            mock_callback.message.answer.assert_called_once()
            args, _ = mock_callback.message.answer.call_args
            self.assertIn("Cancelled", args[0])

        asyncio.run(run_test())
