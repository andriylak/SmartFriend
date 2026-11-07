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
    reveal_answer,
    process_study_edit,
    process_edit_field_a,
    save_edited_a,
    process_study_delete,
    process_confirm_study_delete,
    process_cancel_study_delete,
    process_cfg_deck,
    process_cfg_preset,
    process_cfg_select_preset,
    process_cfg_lang_src_btn,
    process_cfg_lang_src_msg,
    process_cfg_lang_tgt_btn,
    process_cfg_lang_tgt_msg,
    process_cfg_custom_prompt_msg,
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

    @patch("database.get_user_cards")
    def test_process_edit_field_shows_copyable_code_block(self, mock_get_user_cards):
        mock_get_user_cards.return_value = [{
            "id": 55,
            "question": "What is 2+2?",
            "answer": "Four",
            "comment": "Math",
            "category": "General"
        }]

        mock_callback = AsyncMock()
        mock_callback.data = "edit_field_a_55"
        mock_callback.from_user.id = 1000
        mock_callback.message.edit_text = AsyncMock()
        mock_callback.answer = AsyncMock()

        async def run_test():
            await process_edit_field_a(mock_callback, self.state)
            state_data = await self.state.get_data()
            self.assertEqual(state_data.get("editing_card_id"), 55)
            self.assertEqual(await self.state.get_state(), QuizStates.editing_a)

            mock_callback.message.edit_text.assert_called_once()
            call_text = mock_callback.message.edit_text.call_args[0][0]
            # Check copyable HTML code tag
            self.assertIn("<code>Four</code>", call_text)
            self.assertIn("tap to copy", call_text)

            # Check back button exists
            markup = mock_callback.message.edit_text.call_args[1].get("reply_markup")
            buttons = [btn.callback_data for row in markup.inline_keyboard for btn in row]
            self.assertIn("study_edit_55", buttons)

        asyncio.run(run_test())

    @patch("database.get_user_cards")
    @patch("database.update_card")
    def test_save_edited_field_remains_in_editing_menu(self, mock_update_card, mock_get_user_cards):
        mock_get_user_cards.return_value = [{
            "id": 55,
            "question": "What is 2+2?",
            "answer": "4 (four)",
            "comment": "Math",
            "category": "General"
        }]

        mock_message = AsyncMock()
        mock_message.text = "4 (four)"
        mock_message.from_user.id = 1000
        mock_message.answer = AsyncMock()

        async def run_test():
            await self.state.set_state(QuizStates.editing_a)
            await self.state.update_data(editing_card_id=55, active_category="General")

            await save_edited_a(mock_message, self.state)

            # Verify update_card was called with the new text
            mock_update_card.assert_called_once_with(55, 1000, answer="4 (four)")

            # Verify message.answer was called with the edit menu containing success message
            mock_message.answer.assert_called_once()
            call_text = mock_message.answer.call_args[0][0]
            self.assertIn("Answer updated", call_text)
            self.assertIn("Edit Card #55", call_text)
            self.assertIn("4 (four)", call_text)

            # Check markup contains edit menu buttons
            markup = mock_message.answer.call_args[1].get("reply_markup")
            buttons = [btn.callback_data for row in markup.inline_keyboard for btn in row]
            self.assertIn("edit_field_q_55", buttons)
            self.assertIn("edit_field_a_55", buttons)
            self.assertIn("study_resume", buttons)

        asyncio.run(run_test())

    @patch("database.delete_card")
    @patch("database.get_user_cards")
    def test_process_study_delete_prompts_confirmation(self, mock_get_user_cards, mock_delete_card):
        mock_get_user_cards.return_value = [{
            "id": 55,
            "question": "What is 2+2?",
            "answer": "Four",
            "comment": "Math",
            "category": "General"
        }]

        mock_callback = AsyncMock()
        mock_callback.data = "study_delete_unrev_55"
        mock_callback.from_user.id = 1000
        mock_callback.message.edit_text = AsyncMock()
        mock_callback.answer = AsyncMock()

        async def run_test():
            await self.state.set_state(QuizStates.studying)
            await process_study_delete(mock_callback, self.state)

            # Deletion must NOT occur on initial click
            mock_delete_card.assert_not_called()

            # Message must prompt user with confirmation text
            mock_callback.message.edit_text.assert_called_once()
            call_text = mock_callback.message.edit_text.call_args[0][0]
            self.assertIn("Are you sure you want to delete this card?", call_text)
            self.assertIn("What is 2+2?", call_text)
            self.assertIn("Four", call_text)

            # Markup must have confirm and cancel buttons
            markup = mock_callback.message.edit_text.call_args[1].get("reply_markup")
            buttons = [btn.callback_data for row in markup.inline_keyboard for btn in row]
            self.assertIn("confirm_study_del_55", buttons)
            self.assertIn("cancel_study_del_unrev_55", buttons)

        asyncio.run(run_test())

    @patch("handlers.quiz.send_next_card")
    @patch("database.delete_card")
    def test_process_confirm_study_delete(self, mock_delete_card, mock_send_next_card):
        mock_callback = AsyncMock()
        mock_callback.data = "confirm_study_del_55"
        mock_callback.from_user.id = 1000
        mock_callback.answer = AsyncMock()

        async def run_test():
            await self.state.set_state(QuizStates.studying)
            await self.state.update_data(active_category="General")

            await process_confirm_study_delete(mock_callback, self.state)

            mock_delete_card.assert_called_once_with(55, 1000)
            mock_callback.answer.assert_called_once()
            mock_send_next_card.assert_called_once()

        asyncio.run(run_test())

    @patch("database.delete_card")
    @patch("database.get_user_cards")
    def test_process_cancel_study_delete_unrev(self, mock_get_user_cards, mock_delete_card):
        mock_get_user_cards.return_value = [{
            "id": 55,
            "question": "What is 2+2?",
            "answer": "Four",
            "comment": "Math",
            "category": "General",
            "correct_count": 0,
            "incorrect_count": 0,
            "direction": "standard"
        }]

        mock_callback = AsyncMock()
        mock_callback.data = "cancel_study_del_unrev_55"
        mock_callback.from_user.id = 1000
        mock_callback.message.edit_text = AsyncMock()
        mock_callback.answer = AsyncMock()

        async def run_test():
            await self.state.set_state(QuizStates.studying)
            await process_cancel_study_delete(mock_callback, self.state)

            mock_delete_card.assert_not_called()
            mock_callback.message.edit_text.assert_called_once()
            call_text = mock_callback.message.edit_text.call_args[0][0]
            self.assertIn("What is 2+2?", call_text)

            # Restores reveal keyboard with Show Answer button
            markup = mock_callback.message.edit_text.call_args[1].get("reply_markup")
            buttons = [btn.callback_data for row in markup.inline_keyboard for btn in row]
            self.assertIn("reveal_std_55", buttons)

        asyncio.run(run_test())

    @patch("database.delete_card")
    @patch("database.get_user_cards")
    def test_process_cancel_study_delete_rev(self, mock_get_user_cards, mock_delete_card):
        mock_get_user_cards.return_value = [{
            "id": 55,
            "question": "What is 2+2?",
            "answer": "Four",
            "comment": "Math",
            "category": "General",
            "correct_count": 0,
            "incorrect_count": 0,
            "direction": "standard"
        }]

        mock_callback = AsyncMock()
        mock_callback.data = "cancel_study_del_rev_55"
        mock_callback.from_user.id = 1000
        mock_callback.message.edit_text = AsyncMock()
        mock_callback.answer = AsyncMock()

        async def run_test():
            await self.state.set_state(QuizStates.studying)
            await process_cancel_study_delete(mock_callback, self.state)

            mock_delete_card.assert_not_called()
            mock_callback.message.edit_text.assert_called_once()
            call_text = mock_callback.message.edit_text.call_args[0][0]
            self.assertIn("Rate your recall difficulty", call_text)

            # Restores evaluation keyboard with SRS grading buttons
            markup = mock_callback.message.edit_text.call_args[1].get("reply_markup")
            buttons = [btn.callback_data for row in markup.inline_keyboard for btn in row]
            self.assertIn("srs_again_55", buttons)
            self.assertIn("srs_good_55", buttons)

        asyncio.run(run_test())

    @patch("database.get_due_cards")
    def test_send_next_card_avoids_immediate_repeat(self, mock_get_due_cards):
        mock_get_due_cards.return_value = [
            {
                "id": 10,
                "question": "Q10",
                "answer": "A10",
                "category": "Spanish",
                "correct_count": 1,
                "incorrect_count": 1,
                "direction": "standard"
            },
            {
                "id": 20,
                "question": "Q20",
                "answer": "A20",
                "category": "Spanish",
                "correct_count": 1,
                "incorrect_count": 1,
                "direction": "standard"
            }
        ]

        mock_message = AsyncMock()
        mock_message.message_id = 999
        mock_message.edit_text = AsyncMock()

        async def run_test():
            await self.state.set_state(QuizStates.studying)
            await self.state.update_data(last_card_id=10)
            await send_next_card(mock_message, user_id=1000, category="Spanish", state=self.state, edit_existing=True)

            call_text = mock_message.edit_text.call_args[0][0]
            self.assertIn("Q20", call_text)
            state_data = await self.state.get_data()
            self.assertEqual(state_data.get("last_card_id"), 20)

        asyncio.run(run_test())

class TestDeckPresetManager(unittest.TestCase):
    def setUp(self):
        self.storage = MemoryStorage()
        self.key = StorageKey(bot_id=1, chat_id=100, user_id=1000)
        self.state = FSMContext(storage=self.storage, key=self.key)

    @patch("database.get_collaborative_deck_for_user", return_value=None)
    @patch("database.get_new_cards_studied_today", return_value=0)
    @patch("database.get_deck_setting")
    def test_deck_config_shows_language_preset_details(self, mock_get_setting, mock_studied, mock_collab):
        mock_get_setting.return_value = {
            "preset_key": "language",
            "source_language": "Czech",
            "target_language": "English",
            "daily_new_limit": 20
        }
        mock_callback = AsyncMock()
        mock_callback.data = "cfg_deck_Czech"
        mock_callback.from_user.id = 1000
        mock_callback.message.edit_text = AsyncMock()
        mock_callback.answer = AsyncMock()

        async def run_test():
            await process_cfg_deck(mock_callback, self.state)
            mock_callback.message.edit_text.assert_called_once()
            call_text = mock_callback.message.edit_text.call_args[0][0]
            self.assertIn("AI Preset:", call_text)
            self.assertIn("Language Learning (Czech ➔ English)", call_text)

        asyncio.run(run_test())

    @patch("database.get_deck_setting")
    def test_process_cfg_preset_opens_selection_menu(self, mock_get_setting):
        mock_get_setting.return_value = {
            "preset_key": "language",
            "source_language": "Czech",
            "target_language": "English"
        }
        mock_callback = AsyncMock()
        mock_callback.data = "cfg_preset_Czech"
        mock_callback.from_user.id = 1000
        mock_callback.message.edit_text = AsyncMock()
        mock_callback.answer = AsyncMock()

        async def run_test():
            await process_cfg_preset(mock_callback, self.state)
            mock_callback.message.edit_text.assert_called_once()
            call_text = mock_callback.message.edit_text.call_args[0][0]
            self.assertIn("AI Generator Preset for 'Czech'", call_text)
            self.assertIn("Language Learning", call_text)

            markup = mock_callback.message.edit_text.call_args[1].get("reply_markup")
            buttons = [btn.callback_data for row in markup.inline_keyboard for btn in row]
            self.assertIn("cfg_sel_preset:language", buttons)
            self.assertIn("cfg_sel_preset:definitions", buttons)
            self.assertIn("cfg_sel_preset:custom", buttons)
            self.assertIn("cfg_deck_Czech", buttons)

        asyncio.run(run_test())

    @patch("database.save_deck_setting")
    def test_process_cfg_select_preset_direct(self, mock_save_setting):
        mock_callback = AsyncMock()
        mock_callback.data = "cfg_sel_preset:definitions"
        mock_callback.from_user.id = 1000
        mock_callback.message.edit_text = AsyncMock()
        mock_callback.answer = AsyncMock()

        async def run_test():
            await self.state.update_data(active_config_deck="Science")
            await process_cfg_select_preset(mock_callback, self.state)

            mock_save_setting.assert_called_once_with(1000, "Science", preset_key="definitions")
            mock_callback.message.edit_text.assert_called_once()
            call_text = mock_callback.message.edit_text.call_args[0][0]
            self.assertIn("AI Preset Saved!", call_text)
            self.assertIn("Definitions", call_text)

        asyncio.run(run_test())

    def test_process_cfg_select_preset_language_flow(self):
        mock_callback = AsyncMock()
        mock_callback.data = "cfg_sel_preset:language"
        mock_callback.from_user.id = 1000
        mock_callback.message.edit_text = AsyncMock()
        mock_callback.answer = AsyncMock()

        async def run_test():
            await self.state.update_data(active_config_deck="Czech")
            await process_cfg_select_preset(mock_callback, self.state)

            current_state = await self.state.get_state()
            self.assertEqual(current_state, QuizStates.waiting_deck_source_lang.state)
            mock_callback.message.edit_text.assert_called_once()
            call_text = mock_callback.message.edit_text.call_args[0][0]
            self.assertIn("Language Learning: Step 1 of 2", call_text)

            markup = mock_callback.message.edit_text.call_args[1].get("reply_markup")
            buttons = [btn.callback_data for row in markup.inline_keyboard for btn in row]
            self.assertIn("cfg_lang_src:Czech", buttons)
            self.assertIn("cfg_lang_src:Spanish", buttons)

        asyncio.run(run_test())

    @patch("database.save_deck_setting")
    def test_language_source_and_target_callback_buttons(self, mock_save_setting):
        mock_src_cb = AsyncMock()
        mock_src_cb.data = "cfg_lang_src:Czech"
        mock_src_cb.from_user.id = 1000
        mock_src_cb.message.edit_text = AsyncMock()
        mock_src_cb.answer = AsyncMock()

        mock_tgt_cb = AsyncMock()
        mock_tgt_cb.data = "cfg_lang_tgt:English"
        mock_tgt_cb.from_user.id = 1000
        mock_tgt_cb.message.edit_text = AsyncMock()
        mock_tgt_cb.answer = AsyncMock()

        async def run_test():
            await self.state.update_data(active_config_deck="Czech")
            await self.state.set_state(QuizStates.waiting_deck_source_lang)

            # 1. Select source language via button
            await process_cfg_lang_src_btn(mock_src_cb, self.state)
            state_data = await self.state.get_data()
            self.assertEqual(state_data.get("deck_source_lang"), "Czech")
            current_state = await self.state.get_state()
            self.assertEqual(current_state, QuizStates.waiting_deck_target_lang.state)

            # 2. Select target language via button
            await process_cfg_lang_tgt_btn(mock_tgt_cb, self.state)
            mock_save_setting.assert_called_once_with(
                user_id=1000,
                category="Czech",
                preset_key="language",
                source_language="Czech",
                target_language="English"
            )
            mock_tgt_cb.message.edit_text.assert_called_once()
            call_text = mock_tgt_cb.message.edit_text.call_args[0][0]
            self.assertIn("Language Preset Saved!", call_text)
            self.assertIn("Czech", call_text)
            self.assertIn("English", call_text)

        asyncio.run(run_test())

    @patch("database.save_deck_setting")
    def test_language_source_and_target_text_messages(self, mock_save_setting):
        mock_src_msg = AsyncMock()
        mock_src_msg.text = "🇪🇸 Spanish"
        mock_src_msg.from_user.id = 1000
        mock_src_msg.answer = AsyncMock()

        mock_tgt_msg = AsyncMock()
        mock_tgt_msg.text = "Ukrainian"
        mock_tgt_msg.from_user.id = 1000
        mock_tgt_msg.answer = AsyncMock()

        async def run_test():
            await self.state.update_data(active_config_deck="Spanish Deck")
            await self.state.set_state(QuizStates.waiting_deck_source_lang)

            # 1. Send source language message
            await process_cfg_lang_src_msg(mock_src_msg, self.state)
            state_data = await self.state.get_data()
            self.assertEqual(state_data.get("deck_source_lang"), "Spanish")

            # 2. Send target language message
            await process_cfg_lang_tgt_msg(mock_tgt_msg, self.state)
            mock_save_setting.assert_called_once_with(
                user_id=1000,
                category="Spanish Deck",
                preset_key="language",
                source_language="Spanish",
                target_language="Ukrainian"
            )
            mock_tgt_msg.answer.assert_called_once()
            call_text = mock_tgt_msg.answer.call_args[0][0]
            self.assertIn("Language Preset Saved!", call_text)

        asyncio.run(run_test())

    @patch("database.save_deck_setting")
    def test_custom_prompt_input_flow(self, mock_save_setting):
        mock_msg = AsyncMock()
        mock_msg.text = "Create advanced C1 level flashcards with IPA pronunciation."
        mock_msg.from_user.id = 1000
        mock_msg.answer = AsyncMock()

        async def run_test():
            await self.state.update_data(active_config_deck="German")
            await self.state.set_state(QuizStates.waiting_deck_custom_prompt)

            await process_cfg_custom_prompt_msg(mock_msg, self.state)
            mock_save_setting.assert_called_once_with(
                user_id=1000,
                category="German",
                preset_key="custom",
                custom_prompt="Create advanced C1 level flashcards with IPA pronunciation."
            )
            mock_msg.answer.assert_called_once()
            call_text = mock_msg.answer.call_args[0][0]
            self.assertIn("Custom Prompt Saved!", call_text)

        asyncio.run(run_test())

if __name__ == "__main__":
    unittest.main()
