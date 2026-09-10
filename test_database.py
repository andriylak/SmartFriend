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
        # Add card with comment (single direction for test)
        card_id = database.add_card(user_id, "What is Python?", "A programming language", "Programming", comment="Popular language", create_pair=False)
        self.assertIsNotNone(card_id)
        
        # Get cards
        cards = database.get_user_cards(user_id)
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["id"], card_id)
        self.assertEqual(cards[0]["question"], "What is Python?")
        self.assertEqual(cards[0]["answer"], "A programming language")
        self.assertEqual(cards[0]["comment"], "Popular language")
        self.assertEqual(cards[0]["category"], "Programming")
        self.assertEqual(cards[0]["correct_count"], 0)
        self.assertEqual(cards[0]["incorrect_count"], 0)

    def test_get_user_cards_by_category(self):
        user_id = 54321
        database.add_card(user_id, "Q_Math", "A_Math", "Math", create_pair=False)
        database.add_card(user_id, "Q_History", "A_History", "History", create_pair=False)

        cards_all = database.get_user_cards(user_id)
        self.assertEqual(len(cards_all), 2)

        cards_math = database.get_user_cards(user_id, category="Math")
        self.assertEqual(len(cards_math), 1)
        self.assertEqual(cards_math[0]["question"], "Q_Math")
        self.assertEqual(cards_math[0]["category"], "Math")

    def test_get_random_card(self):
        user_id = 98765
        # Add multiple cards
        database.add_card(user_id, "Q1", "A1", "Cat1", create_pair=False)
        database.add_card(user_id, "Q2", "A2", "Cat2", create_pair=False)
        
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
        card_id = database.add_card(user_id, "To be deleted", "Answer", create_pair=False)
        
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
        card_id = database.add_card(user_id, "Stats Q", "Stats A", create_pair=False)
        
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
        database.add_card(user_id, "Q1", "A1", "Math", create_pair=False)
        database.add_card(user_id, "Q2", "A2", "History", create_pair=False)
        database.add_card(user_id, "Q3", "A3", "Math", create_pair=False) # duplicate category
        
        categories = database.get_user_categories(user_id)
        self.assertEqual(categories, ["History", "Math"])

    def test_deck_settings(self):
        user_id = 44444
        category = "Spanish"
        
        # Initially None
        setting = database.get_deck_setting(user_id, category)
        self.assertIsNone(setting)
        
        # Save setting
        database.save_deck_setting(user_id, category, "language", source_language="Spanish", target_language="English")
        setting = database.get_deck_setting(user_id, category)
        self.assertIsNotNone(setting)
        self.assertEqual(setting["preset_key"], "language")
        self.assertEqual(setting["source_language"], "Spanish")
        self.assertEqual(setting["target_language"], "English")
        
        # Update setting (ON CONFLICT)
        database.save_deck_setting(user_id, category, "language", source_language="German", target_language="Ukrainian")
        updated = database.get_deck_setting(user_id, category)
        self.assertEqual(updated["source_language"], "German")
        self.assertEqual(updated["target_language"], "Ukrainian")

    def test_search_user_cards(self):
        user_id = 66666
        database.add_card(user_id, "el gato", "the cat", "Spanish", create_pair=False)
        database.add_card(user_id, "el perro", "the dog", "Spanish", create_pair=False)
        database.add_card(user_id, "la manzana", "the apple", "Spanish", create_pair=False)

        # Substring match
        matches = database.search_user_cards(user_id, "gato", "Spanish")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["question"], "el gato")

        # Fuzzy match with slight typo
        fuzzy = database.search_user_cards(user_id, "perro", "Spanish")
        self.assertEqual(len(fuzzy), 1)
        self.assertEqual(fuzzy[0]["question"], "el perro")

    def test_srs_scheduling(self):
        user_id = 77777
        card_id = database.add_card(user_id, "Hola", "Hello", "Spanish", create_pair=False)
        
        # Verify card is due immediately
        due_cards = database.get_due_cards(user_id, "Spanish")
        self.assertEqual(len(due_cards), 1)
        self.assertEqual(due_cards[0]["id"], card_id)
        
        counts = database.get_due_card_counts(user_id)
        self.assertEqual(counts.get("Spanish"), 1)
        
        # Grade card as 'good'
        res = database.update_card_srs(card_id, user_id, "good")
        self.assertEqual(res["rating"], "good")
        self.assertEqual(res["interval_days"], 1.0)
        
        # After grading 'good' for interval=1 day, card should no longer be due immediately
        due_cards_after = database.get_due_cards(user_id, "Spanish")
        self.assertEqual(len(due_cards_after), 0)

    def test_dual_direction_card_creation(self):
        user_id = 88888
        std_id = database.add_card(user_id, "el perro", "the dog", "Spanish", create_pair=True)
        cards = database.get_user_cards(user_id, "Spanish")
        self.assertEqual(len(cards), 2)
        
        directions = [c["direction"] for c in cards]
        self.assertIn("standard", directions)
        self.assertIn("reverse", directions)

    def test_get_due_cards_randomized_and_prioritized(self):
        user_id = 99999
        # Add 5 cards
        for i in range(5):
            database.add_card(user_id, f"Question {i}", f"Answer {i}", "DeckA", create_pair=False)
            
        due = database.get_due_cards(user_id, "DeckA")
        self.assertEqual(len(due), 5)
        
        # Test prioritization: fail card 3 so it becomes Tier 0 (Learning)
        failed_id = due[3]["id"]
        database.update_card_srs(failed_id, user_id, "again")
        
        # Manually reset next_review_at to past so it's due now as a learning card
        import sqlite3
        conn = sqlite3.connect(database.DB_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE cards SET next_review_at = CURRENT_TIMESTAMP WHERE id = ?", (failed_id,))
        conn.commit()
        conn.close()
        
        due_prioritized = database.get_due_cards(user_id, "DeckA")
        self.assertEqual(len(due_prioritized), 5)
        # The failed card must be first because it is in Tier 0 (Learning)
        self.assertEqual(due_prioritized[0]["id"], failed_id)

    def test_srs_again_hard_good_progression(self):
        user_id = 70001
        card_id = database.add_card(user_id, "Q_SRS", "A_SRS", "DeckSRS", create_pair=False)
        
        # 1. Answer 'again' -> learning step
        res1 = database.update_card_srs(card_id, user_id, "again")
        self.assertEqual(res1["interval_days"], 0.007)
        self.assertEqual(res1["repetition_count"], 0)

        # 2. Answer 'hard' while in learning step -> stays in learning step, reps=0
        res2 = database.update_card_srs(card_id, user_id, "hard")
        self.assertEqual(res2["interval_days"], 0.007)
        self.assertEqual(res2["repetition_count"], 0)

        # 3. Answer 'good' -> graduates out of learning step cleanly to 1.0 day
        res3 = database.update_card_srs(card_id, user_id, "good")
        self.assertEqual(res3["interval_days"], 1.0)
        self.assertEqual(res3["repetition_count"], 1)

        # 4. Next 'good' -> 6.0 days (whole integer days)
        res4 = database.update_card_srs(card_id, user_id, "good")
        self.assertEqual(res4["interval_days"], 6.0)
        self.assertEqual(res4["repetition_count"], 2)

    def test_daily_new_cards_limit(self):
        user_id = 70002
        cat = "DeckLimit"
        # Add 5 cards
        c_ids = []
        for i in range(5):
            c_id = database.add_card(user_id, f"Q_Lim_{i}", f"A_Lim_{i}", cat, create_pair=False)
            c_ids.append(c_id)

        # Set daily new limit to 2
        database.save_deck_setting(user_id, cat, daily_new_limit=2)
        
        due = database.get_due_cards(user_id, cat)
        self.assertEqual(len(due), 2)  # Capped at 2 new cards

        # Study 1 card
        database.update_card_srs(c_ids[0], user_id, "good")

        # Now 1 new card studied today, limit is 2, so 1 remaining new card + 0 review cards due
        due_after = database.get_due_cards(user_id, cat)
        self.assertEqual(len(due_after), 1)

    def test_intraday_learning_card_due_immediately(self):
        user_id = 70003
        cat = "DeckIntraday"
        card_id = database.add_card(user_id, "Q_Intraday", "A_Intraday", cat, create_pair=False)
        
        # Grade as 'again' -> interval 0.007 days (~10 min in the future)
        res = database.update_card_srs(card_id, user_id, "again")
        self.assertEqual(res["interval_days"], 0.007)
        
        # Verify card is returned in due cards immediately without waiting 10 minutes
        due_cards = database.get_due_cards(user_id, cat)
        self.assertEqual(len(due_cards), 1)
        self.assertEqual(due_cards[0]["id"], card_id)
        
        # Verify get_due_card_counts also counts it
        counts = database.get_due_card_counts(user_id)
        self.assertEqual(counts.get(cat), 1)
        
        # Now grade it 'good' -> graduates to 1.0 day (due tomorrow)
        res_good = database.update_card_srs(card_id, user_id, "good")
        self.assertEqual(res_good["interval_days"], 1.0)
        
        # Now no cards should be due today
        due_cards_graduated = database.get_due_cards(user_id, cat)
        self.assertEqual(len(due_cards_graduated), 0)
        
        counts_graduated = database.get_due_card_counts(user_id)
        self.assertEqual(counts_graduated.get(cat), 0)

    def test_queue_ordering_learning_ahead_at_end(self):
        user_id = 70004
        cat = "DeckOrder"
        
        # 1. Existing review card that is due now
        card_due = database.add_card(user_id, "Q_DueNow", "A_DueNow", cat, create_pair=False)
        database.update_card_srs(card_due, user_id, "good") # interval 1.0 day
        conn = sqlite3.connect(database.DB_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE cards SET next_review_at = CURRENT_TIMESTAMP WHERE id = ?", (card_due,))
        conn.commit()
        conn.close()
        
        # 2. Brand new card (due now)
        card_new = database.add_card(user_id, "Q_New", "A_New", cat, create_pair=False)
        
        # 3. Learning card answered 'again' (scheduled 10 mins in future)
        card_learning = database.add_card(user_id, "Q_Learn", "A_Learn", cat, create_pair=False)
        database.update_card_srs(card_learning, user_id, "again")
        
        due_queue = database.get_due_cards(user_id, cat)
        self.assertEqual(len(due_queue), 3)
        # Order: 1. due review card, 2. new card, 3. future learning card
        self.assertEqual(due_queue[0]["id"], card_due)
        self.assertEqual(due_queue[1]["id"], card_new)
        self.assertEqual(due_queue[2]["id"], card_learning)

if __name__ == "__main__":
    unittest.main()

