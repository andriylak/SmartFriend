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

    def test_delete_card_deletes_both_sides(self):
        user_id = 11112
        # Create paired card (standard + reverse)
        std_id = database.add_card(user_id, "gato", "cat", "Spanish", create_pair=True)
        cards = database.get_user_cards(user_id)
        self.assertEqual(len(cards), 2)

        # Deleting the standard card should delete both sides
        success = database.delete_card(std_id, user_id)
        self.assertTrue(success)
        self.assertEqual(len(database.get_user_cards(user_id)), 0)

        # Create another pair and test deleting via reverse card id
        database.add_card(user_id, "perro", "dog", "Spanish", create_pair=True)
        cards2 = database.get_user_cards(user_id)
        self.assertEqual(len(cards2), 2)
        rev_card = next(c for c in cards2 if c["direction"] == "reverse")

        success_rev = database.delete_card(rev_card["id"], user_id)
        self.assertTrue(success_rev)
        self.assertEqual(len(database.get_user_cards(user_id)), 0)

        # Deleting non-existent card returns False
        self.assertFalse(database.delete_card(999999, user_id))

    def test_update_card_and_paired_sync(self):
        user_id = 11113
        # Create paired card
        std_id = database.add_card(user_id, "gato", "cat", "Spanish", comment="animal", create_pair=True)
        cards = database.get_user_cards(user_id)
        self.assertEqual(len(cards), 2)

        # Update standard card's question, answer, comment, category
        success = database.update_card(std_id, user_id, question="el gato", answer="the cat", comment="feline", category="Espanol")
        self.assertTrue(success)

        updated_cards = database.get_user_cards(user_id)
        std_card = next(c for c in updated_cards if c["id"] == std_id)
        rev_card = next(c for c in updated_cards if c["id"] != std_id)

        # Standard card check
        self.assertEqual(std_card["question"], "el gato")
        self.assertEqual(std_card["answer"], "the cat")
        self.assertEqual(std_card["comment"], "feline")
        self.assertEqual(std_card["category"], "Espanol")

        # Reverse counterpart must be kept in sync (swapped Q and A)
        self.assertEqual(rev_card["question"], "the cat")
        self.assertEqual(rev_card["answer"], "el gato")
        self.assertEqual(rev_card["comment"], "feline")
        self.assertEqual(rev_card["category"], "Espanol")

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

        # Updating daily limit preserves existing language and preset settings
        database.save_deck_setting(user_id, category, daily_new_limit=50)
        with_limit = database.get_deck_setting(user_id, category)
        self.assertEqual(with_limit["preset_key"], "language")
        self.assertEqual(with_limit["source_language"], "German")
        self.assertEqual(with_limit["target_language"], "Ukrainian")
        self.assertEqual(with_limit["daily_new_limit"], 50)

        # Case-insensitive category lookup works
        case_match = database.get_deck_setting(user_id, "spanish")
        self.assertIsNotNone(case_match)
        self.assertEqual(case_match["source_language"], "German")

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

    def test_find_existing_cards_in_deck(self):
        user_id = 66667
        # Create dual SRS cards in Spanish
        database.add_card(user_id, "el perro", "the dog", "Spanish", create_pair=True)
        database.add_card(user_id, "to run", "бігати", "Spanish", create_pair=True)
        database.add_card(user_id, "gato", "cat, feline", "Spanish", create_pair=True)
        # Create card in another deck
        database.add_card(user_id, "la maison", "the house", "French", create_pair=True)

        # 1. Exact match with article stripped (query "perro" matches "el perro")
        res1 = database.find_existing_cards_in_deck(user_id, "Spanish", "perro")
        self.assertEqual(len(res1), 1)
        self.assertEqual(res1[0]["question"], "el perro")

        # 2. Reverse pair deduplication: only 1 card returned despite dual SRS cards
        self.assertEqual(len(res1), 1)

        # 3. Match from answer side (query "dog" matches answer "the dog")
        res2 = database.find_existing_cards_in_deck(user_id, "Spanish", "dog")
        self.assertEqual(len(res2), 1)
        self.assertEqual(res2[0]["question"], "el perro")

        # 4. Particle stripping ("run" matches "to run")
        res3 = database.find_existing_cards_in_deck(user_id, "Spanish", "run")
        self.assertEqual(len(res3), 1)
        self.assertEqual(res3[0]["question"], "to run")

        # 5. Segment matching ("feline" matches "cat, feline")
        res4 = database.find_existing_cards_in_deck(user_id, "Spanish", "feline")
        self.assertEqual(len(res4), 1)
        self.assertEqual(res4[0]["question"], "gato")

        # 6. Avoiding false positives ("catch" must NOT match "cat", "in" must NOT match "dinner")
        res_no_match = database.find_existing_cards_in_deck(user_id, "Spanish", "catch")
        self.assertEqual(len(res_no_match), 0)

        # 7. Deck isolation (French card "la maison" should not match in Spanish)
        res_diff_deck = database.find_existing_cards_in_deck(user_id, "Spanish", "maison")
        self.assertEqual(len(res_diff_deck), 0)
        res_french = database.find_existing_cards_in_deck(user_id, "French", "maison")
        self.assertEqual(len(res_french), 1)


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
        # Due review cards and new cards are shuffled together ahead of future learning-ahead cards
        self.assertEqual({due_queue[0]["id"], due_queue[1]["id"]}, {card_due, card_new})
        self.assertEqual(due_queue[2]["id"], card_learning)

    def test_new_cards_sorted_selection_and_shuffled_into_old_cards(self):
        user_id = 70006
        cat = "DeckMixed"
        database.save_deck_setting(user_id, cat, daily_new_limit=4)

        # Create 4 old due review cards
        old_ids = []
        for i in range(4):
            cid = database.add_card(user_id, f"Old_Q_{i}", f"Old_A_{i}", cat, create_pair=False)
            database.update_card_srs(cid, user_id, "good")
            old_ids.append(cid)

        # Clear daily_new_cards_log so our 4 new cards limit applies to the next unstudied cards
        conn = sqlite3.connect(database.DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM daily_new_cards_log WHERE user_id = ?", (user_id,))
        for cid in old_ids:
            cursor.execute("UPDATE cards SET next_review_at = CURRENT_TIMESTAMP WHERE id = ?", (cid,))
        conn.commit()
        conn.close()

        # Create 5 new paired cards (10 cards total); daily limit=4 should select the first 4 by id ASC (pair 1 + pair 2)
        p1_std = database.add_card(user_id, "New_Q_1", "New_A_1", cat, create_pair=True)
        p2_std = database.add_card(user_id, "New_Q_2", "New_A_2", cat, create_pair=True)
        for i in range(3, 6):
            database.add_card(user_id, f"New_Q_{i}", f"New_A_{i}", cat, create_pair=True)

        all_cards = database.get_user_cards(user_id, cat)
        p1_rev = next(c["id"] for c in all_cards if c["question"] == "New_A_1" and c["answer"] == "New_Q_1")
        p2_rev = next(c["id"] for c in all_cards if c["question"] == "New_A_2" and c["answer"] == "New_Q_2")
        expected_new_ids = {p1_std, p1_rev, p2_std, p2_rev}

        orders = set()
        for _ in range(15):
            due_queue = database.get_due_cards(user_id, cat)
            ids = [c["id"] for c in due_queue]
            self.assertEqual(set(ids), set(old_ids) | expected_new_ids)
            orders.add(tuple(ids))

        self.assertGreater(len(orders), 1)

    def test_due_cards_tiers_are_shuffled(self):
        user_id = 70005
        cat = "DeckShuffle"
        card_ids = []
        for i in range(10):
            cid = database.add_card(user_id, f"Q_Shuf_{i}", f"A_Shuf_{i}", cat, create_pair=False)
            card_ids.append(cid)

        # New cards should be randomized across calls
        orders_new = {tuple(c["id"] for c in database.get_due_cards(user_id, cat)) for _ in range(10)}
        self.assertGreater(len(orders_new), 1)

        # Mark all as learning ahead ('again') in sequential order and verify they are shuffled
        for cid in card_ids:
            database.update_card_srs(cid, user_id, "again")
        orders_learning = {tuple(c["id"] for c in database.get_due_cards(user_id, cat)) for _ in range(10)}
        self.assertGreater(len(orders_learning), 1)

        # Set varying intervals for due review cards and verify they are shuffled (not sorted by interval_days)
        conn = sqlite3.connect(database.DB_PATH)
        cursor = conn.cursor()
        for idx, cid in enumerate(card_ids):
            cursor.execute(
                "UPDATE cards SET interval_days = ?, repetition_count = 2, correct_count = 2, next_review_at = CURRENT_TIMESTAMP WHERE id = ?",
                (float(idx + 1), cid)
            )
        conn.commit()
        conn.close()
        orders_review = {tuple(c["id"] for c in database.get_due_cards(user_id, cat)) for _ in range(10)}
        self.assertGreater(len(orders_review), 1)

    def test_delete_deck(self):
        user_id = 99999
        cat_to_delete = "DeckToDelete"
        cat_to_keep = "DeckToKeep"
        
        database.add_card(user_id, "Q1", "A1", cat_to_delete, create_pair=False)
        database.add_card(user_id, "Q2", "A2", cat_to_delete, create_pair=False)
        database.add_card(user_id, "QK", "AK", cat_to_keep, create_pair=False)
        database.save_deck_setting(user_id, cat_to_delete, daily_new_limit=10)
        
        deleted_count = database.delete_deck(user_id, cat_to_delete)
        self.assertEqual(deleted_count, 2)
        
        cards_deleted = database.get_user_cards(user_id, category=cat_to_delete)
        self.assertEqual(len(cards_deleted), 0)
        
        cards_kept = database.get_user_cards(user_id, category=cat_to_keep)
        self.assertEqual(len(cards_kept), 1)
        
        setting = database.get_deck_setting(user_id, cat_to_delete)
        self.assertIsNone(setting)

if __name__ == "__main__":
    unittest.main()


