import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey

import database
import keyboards
from handlers.quiz import (
    QuizStates,
    start_quiz,
    select_category,
    process_study_ahead,
    process_study_back_decks,
    process_stop_study,
    send_next_card,
    process_grading,
    reveal_answer
)

class TestQuizStudyMode(unittest.TestCase):
    def setUp(self):
        self.storage = MemoryStorage()
        self.key = StorageKey(bot_id=1, chat_id=100, user_id=1000)
        self.state = FSMContext(storage=self.storage, key=self.key)
        
    def test_study_keyboards_contain_stop_button(self):
        reveal_kb = keyboards.get_reveal_keyboard(card_id=42)
        eval_kb = keyboards.get_evaluation_keyboard(card_id=42)
        ahead_kb = keyboards.get_study_ahead_keyboard(category="Spanish")
        
        # Verify study_stop callback data exists in all study keyboards
        reveal_buttons = [btn.callback_data for row in reveal_kb.inline_keyboard for btn in row]
        eval_buttons = [btn.callback_data for row in eval_kb.inline_keyboard for btn in row]
        ahead_buttons = [btn.callback_data for row in ahead_kb.inline_keyboard for btn in row]
        
        self.assertIn("study_stop", reveal_buttons)
        self.assertIn("study_stop", eval_buttons)
        self.assertIn("study_stop", ahead_buttons)

    @patch("database.get_due_cards")
    def test_send_next_card_edits_existing_message(self, mock_get_due_cards):
        mock_get_due_cards.return_value = [{
            "id": 1,
            "question": "Hola",
            "answer": "Hello",
            "category": "Spanish",
            "correct_count": 5,
            "incorrect_count": 1,
            "direction": "standard"
        }]
        
        mock_message = AsyncMock()
        mock_message.message_id = 999
        mock_message.edit_text = AsyncMock()
        
        async def run_test():
            await self.state.set_state(QuizStates.studying)
            await send_next_card(mock_message, user_id=1000, category="Spanish", state=self.state, edit_existing=True)
            
            # Should call edit_text in-place on existing message
            mock_message.edit_text.assert_called_once()
            state_data = await self.state.get_data()
            self.assertEqual(state_data.get("study_msg_id"), 999)

        asyncio.run(run_test())

    @patch("database.get_due_cards")
    def test_send_next_card_fallback_on_edit_failure(self, mock_get_due_cards):
        mock_get_due_cards.return_value = [{
            "id": 1,
            "question": "Hola",
            "answer": "Hello",
            "category": "Spanish",
            "correct_count": 0,
            "incorrect_count": 0,
            "direction": "standard"
        }]
        
        mock_message = AsyncMock()
        mock_message.edit_text = AsyncMock(side_effect=Exception("Telegram edit error"))
        mock_message.delete = AsyncMock()
        new_msg = AsyncMock()
        new_msg.message_id = 1001
        mock_message.answer = AsyncMock(return_value=new_msg)
        
        async def run_test():
            await self.state.set_state(QuizStates.studying)
            await send_next_card(mock_message, user_id=1000, category="Spanish", state=self.state, edit_existing=True)
            
            # Edit attempted, failed, delete called, answer called for new message
            mock_message.edit_text.assert_called_once()
            mock_message.delete.assert_called_once()
            mock_message.answer.assert_called_once()
            
            state_data = await self.state.get_data()
            self.assertEqual(state_data.get("study_msg_id"), 1001)

        asyncio.run(run_test())

    @patch("database.get_due_cards")
    def test_send_next_card_all_caught_up_edits_in_place(self, mock_get_due_cards):
        mock_get_due_cards.return_value = [] # No due cards
        
        mock_message = AsyncMock()
        mock_message.message_id = 888
        mock_message.edit_text = AsyncMock()
        
        async def run_test():
            await send_next_card(mock_message, user_id=1000, category="Spanish", state=self.state, edit_existing=True)
            mock_message.edit_text.assert_called_once()
            call_args = mock_message.edit_text.call_args[0][0]
            self.assertIn("All Caught Up", call_args)

        asyncio.run(run_test())

    def test_process_stop_study_clears_state_and_edits_msg(self):
        mock_callback = AsyncMock()
        mock_callback.message.edit_text = AsyncMock()
        mock_callback.answer = AsyncMock()
        
        async def run_test():
            await self.state.set_state(QuizStates.studying)
            await process_stop_study(mock_callback, self.state)
            
            current_state = await self.state.get_state()
            self.assertIsNone(current_state)
            mock_callback.message.edit_text.assert_called_once()
            self.assertIn("Study session ended", mock_callback.message.edit_text.call_args[0][0])

        asyncio.run(run_test())

if __name__ == "__main__":
    unittest.main()
