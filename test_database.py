import os
import unittest
import sqlite3

import database

# Use a test database path so we don't affect production data
TEST_DB_PATH = "test_learning_bot.db"

class TestDatabase(unittest.TestCase):
    def setUp(self):
        # Override DB_PATH in database module
        database.DB_PATH = TEST_DB_PATH
        database.init_db()

    def tearDown(self):
        # Remove the test database file if it exists
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)

    def test_init_db(self):
        # Verify the database has the 'cards' table
        conn = sqlite3.connect(TEST_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cards'")
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "cards")
        conn.close()

    def test_add_and_get_cards(self):
        user_id = 12345
        # Add card
        card_id = database.add_card(user_id, "What is Python?", "A programming language", "Programming")
        self.assertIsNotNone(card_id)
        
        # Get cards
        cards = database.get_user_cards(user_id)
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["id"], card_id)
        self.assertEqual(cards[0]["question"], "What is Python?")
        self.assertEqual(cards[0]["answer"], "A programming language")
        self.assertEqual(cards[0]["category"], "Programming")
        self.assertEqual(cards[0]["correct_count"], 0)
        self.assertEqual(cards[0]["incorrect_count"], 0)

    def test_get_random_card(self):
        user_id = 98765
        # Add multiple cards
        database.add_card(user_id, "Q1", "A1", "Cat1")
        database.add_card(user_id, "Q2", "A2", "Cat2")
        
        # Get random card overall
        card = database.get_random_card(user_id)
        self.assertIsNotNone(card)
        self.assertIn(card["question"], ["Q1", "Q2"])
        
        # Get random card by specific category
        card_cat1 = database.get_random_card(user_id, "Cat1")
        self.assertIsNotNone(card_cat1)
        self.assertEqual(card_cat1["question"], "Q1")

    def test_delete_card(self):
        user_id = 11111
        card_id = database.add_card(user_id, "To be deleted", "Answer")
        
        # Verify card exists
        cards_before = database.get_user_cards(user_id)
        self.assertEqual(len(cards_before), 1)
        
        # Delete card
        success = database.delete_card(card_id, user_id)
        self.assertTrue(success)
        
        # Verify card deleted
        cards_after = database.get_user_cards(user_id)
        self.assertEqual(len(cards_after), 0)

    def test_update_card_stats(self):
        user_id = 22222
        card_id = database.add_card(user_id, "Stats Q", "Stats A")
        
        # Initial stats
        cards = database.get_user_cards(user_id)
        self.assertEqual(cards[0]["correct_count"], 0)
        self.assertEqual(cards[0]["incorrect_count"], 0)
        
        # Correct guess
        database.update_card_stats(card_id, user_id, correct=True)
        cards = database.get_user_cards(user_id)
        self.assertEqual(cards[0]["correct_count"], 1)
        self.assertEqual(cards[0]["incorrect_count"], 0)
        
        # Incorrect guess
        database.update_card_stats(card_id, user_id, correct=False)
        cards = database.get_user_cards(user_id)
        self.assertEqual(cards[0]["correct_count"], 1)
        self.assertEqual(cards[0]["incorrect_count"], 1)

    def test_get_user_categories(self):
        user_id = 33333
        database.add_card(user_id, "Q1", "A1", "Math")
        database.add_card(user_id, "Q2", "A2", "History")
        database.add_card(user_id, "Q3", "A3", "Math") # duplicate category
        
        categories = database.get_user_categories(user_id)
        self.assertEqual(categories, ["History", "Math"])

    def test_deck_settings(self):
        user_id = 44444
        category = "Spanish"
        
        # Initially None
        setting = database.get_deck_setting(user_id, category)
        self.assertIsNone(setting)
        
        # Save setting
        database.save_deck_setting(user_id, category, "language", target_language="English")
        setting = database.get_deck_setting(user_id, category)
        self.assertIsNotNone(setting)
        self.assertEqual(setting["preset_key"], "language")
        self.assertEqual(setting["target_language"], "English")
        
        # Update setting (ON CONFLICT)
        database.save_deck_setting(user_id, category, "language", target_language="Ukrainian")
        updated = database.get_deck_setting(user_id, category)
        self.assertEqual(updated["target_language"], "Ukrainian")

if __name__ == "__main__":
    unittest.main()
