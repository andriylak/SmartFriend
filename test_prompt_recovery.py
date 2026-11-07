import unittest
from unittest.mock import AsyncMock, patch, MagicMock
import asyncio

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey
from aiogram.types import Message, CallbackQuery, User, Chat

import database
import ai_service
from handlers.cards import (
    CreateCardStates,
    process_ai_preset,
    process_ai_custom_prompt,
    generate_and_show_ai_preview,
    start_edit_ai_answer,
    process_edited_answer,
    PRESET_NAME_MAP
)

class TestPromptRecovery(unittest.TestCase):
    def setUp(self):
        self.storage = MemoryStorage()
        self.user_id = 12345
        self.chat_id = 54321
        self.key = StorageKey(bot_id=1, chat_id=self.chat_id, user_id=self.user_id)
        self.state = FSMContext(storage=self.storage, key=self.key)

    @patch("database.get_deck_setting")
    def test_keep_current_preset_restores_state(self, mock_get_setting):
        mock_get_setting.return_value = {
            "preset_key": "language",
            "source_language": "Czech",
            "target_language": "English",
            "custom_prompt": None,
            "daily_new_limit": 20
        }

        mock_msg = AsyncMock(spec=Message)
        mock_msg.text = "🔙 Keep Current Preset"
        mock_msg.from_user = User(id=self.user_id, is_bot=False, first_name="User")
        mock_msg.chat = Chat(id=self.chat_id, type="private")
        mock_msg.answer = AsyncMock()

        async def run_test():
            await self.state.set_state(CreateCardStates.waiting_for_ai_prompt_preset)
            await self.state.update_data(category="cz")
            
            await process_ai_preset(mock_msg, self.state)
            
            curr_state = await self.state.get_state()
            self.assertEqual(curr_state, CreateCardStates.waiting_for_ai_topic)
            
            data = await self.state.get_data()
            self.assertEqual(data.get("preset_key"), "language")
            self.assertEqual(data.get("source_language"), "Czech")
            self.assertEqual(data.get("target_language"), "English")
            self.assertTrue(data.get("has_saved_prompt"))

        asyncio.run(run_test())

    @patch("database.get_deck_setting")
    @patch("handlers.cards.generate_and_show_ai_preview")
    def test_topic_entered_in_preset_selection_uses_saved_deck_setting(self, mock_preview, mock_get_setting):
        mock_get_setting.return_value = {
            "preset_key": "language",
            "source_language": "Czech",
            "target_language": "English",
            "custom_prompt": None,
            "daily_new_limit": 20
        }

        mock_msg = AsyncMock(spec=Message)
        mock_msg.text = "knihovna"
        mock_msg.from_user = User(id=self.user_id, is_bot=False, first_name="User")
        mock_msg.chat = Chat(id=self.chat_id, type="private")
        mock_msg.answer = AsyncMock()

        async def run_test():
            await self.state.set_state(CreateCardStates.waiting_for_ai_prompt_preset)
            await self.state.update_data(category="cz")

            await process_ai_preset(mock_msg, self.state)

            mock_preview.assert_called_once()
            data = await self.state.get_data()
            self.assertEqual(data.get("topic"), "knihovna")
            self.assertEqual(data.get("preset_key"), "language")
            self.assertEqual(data.get("source_language"), "Czech")

        asyncio.run(run_test())

    @patch("database.get_deck_setting")
    def test_custom_prompt_back_restores_state(self, mock_get_setting):
        mock_get_setting.return_value = {
            "preset_key": "language",
            "source_language": "Czech",
            "target_language": "English",
            "custom_prompt": None,
            "daily_new_limit": 20
        }

        mock_msg = AsyncMock(spec=Message)
        mock_msg.text = "🔙 Back"
        mock_msg.from_user = User(id=self.user_id, is_bot=False, first_name="User")
        mock_msg.chat = Chat(id=self.chat_id, type="private")
        mock_msg.answer = AsyncMock()

        async def run_test():
            await self.state.set_state(CreateCardStates.waiting_for_ai_custom_prompt)
            await self.state.update_data(category="cz")

            await process_ai_custom_prompt(mock_msg, self.state)

            curr_state = await self.state.get_state()
            self.assertEqual(curr_state, CreateCardStates.waiting_for_ai_topic)

            data = await self.state.get_data()
            self.assertEqual(data.get("preset_key"), "language")

        asyncio.run(run_test())

    @patch("database.get_deck_setting")
    @patch("ai_service.generate_ai_card")
    def test_preview_generation_syncs_corrupted_state_with_database(self, mock_gen, mock_get_setting):
        mock_get_setting.return_value = {
            "preset_key": "language",
            "source_language": "Czech",
            "target_language": "English",
            "custom_prompt": None,
            "daily_new_limit": 20
        }
        mock_gen.return_value = {
            "question": "pes",
            "answer": "dog",
            "comment": "noun",
            "correction_note": None
        }

        mock_msg = AsyncMock(spec=Message)
        mock_msg.from_user = User(id=self.user_id, is_bot=False, first_name="User")
        mock_msg.chat = Chat(id=self.chat_id, type="private")
        wait_msg = AsyncMock()
        mock_msg.answer = AsyncMock(return_value=wait_msg)

        async def run_test():
            # State inadvertently corrupted with preset_key="custom" and custom_prompt=None
            await self.state.set_state(CreateCardStates.waiting_for_ai_topic)
            await self.state.update_data(
                category="cz",
                preset_key="custom",
                custom_prompt=None,
                topic="pes"
            )

            await generate_and_show_ai_preview(mock_msg, self.state)

            # It should have restored language preset from database
            mock_gen.assert_called_once()
            called_kwargs = mock_gen.call_args.kwargs
            self.assertEqual(called_kwargs["preset_key"], "language")
            self.assertEqual(called_kwargs["source_language"], "Czech")
            self.assertEqual(called_kwargs["target_language"], "English")

        asyncio.run(run_test())

    def test_edit_ai_answer_flow(self):
        mock_cb = AsyncMock(spec=CallbackQuery)
        mock_cb.data = "ai_edit_a"
        mock_cb.answer = AsyncMock()
        mock_cb.message = AsyncMock(spec=Message)
        mock_cb.message.answer = AsyncMock()

        mock_msg = AsyncMock(spec=Message)
        mock_msg.text = "updated answer"
        mock_msg.answer = AsyncMock()

        async def run_test():
            await self.state.set_state(CreateCardStates.waiting_for_ai_preview)
            await self.state.update_data(category="Spanish", question="el perro", answer="dog")

            await start_edit_ai_answer(mock_cb, self.state)
            self.assertEqual(await self.state.get_state(), CreateCardStates.waiting_for_edit_answer.state)
            mock_cb.message.answer.assert_called_once()

            await process_edited_answer(mock_msg, self.state)
            self.assertEqual(await self.state.get_state(), CreateCardStates.waiting_for_ai_preview.state)
            data = await self.state.get_data()
            self.assertEqual(data.get("answer"), "updated answer")
            mock_msg.answer.assert_called_once()
            self.assertIn("updated answer", mock_msg.answer.call_args[0][0])

        asyncio.run(run_test())

if __name__ == "__main__":
    unittest.main()
