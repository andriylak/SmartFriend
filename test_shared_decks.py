import os
import unittest
import sqlite3

import database

TEST_DB_PATH = "test_shared_decks.db"

class TestSharedDecks(unittest.TestCase):
    def setUp(self):
        database.DB_PATH = TEST_DB_PATH
        database.init_db()

    def tearDown(self):
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)

    def test_snapshot_copy_sharing(self):
        user_a = 1001
        user_b = 2002

        # User A creates cards and deck settings
        database.add_card(user_a, "gato", "cat", "Spanish", create_pair=True)
        database.add_card(user_a, "perro", "dog", "Spanish", create_pair=True)
        database.save_deck_setting(user_a, "Spanish", preset_key="language", source_language="Spanish", target_language="English")

        # User A creates a copy share token
        token = database.create_deck_share(user_a, "Spanish", share_type="copy")
        self.assertIsNotNone(token)

        info = database.get_deck_share_info(token)
        self.assertEqual(info["share_type"], "copy")
        self.assertEqual(info["deck_name"], "Spanish")
        self.assertEqual(info["card_count"], 2)

        # User B imports the copy
        imported_count, dest_cat = database.import_deck_copy(user_b, token)
        self.assertEqual(imported_count, 2)
        self.assertEqual(dest_cat, "Spanish")

        # Verify User B has cards
        b_cards = database.get_user_cards(user_b, category="Spanish")
        self.assertEqual(len(b_cards), 4) # 2 standard + 2 reverse

        # Verify User B gets settings copied
        b_setting = database.get_deck_setting(user_b, "Spanish")
        self.assertIsNotNone(b_setting)
        self.assertEqual(b_setting["preset_key"], "language")
        self.assertEqual(b_setting["source_language"], "Spanish")

        # User A adds a new card -> User B's copy should NOT have it
        database.add_card(user_a, "casa", "house", "Spanish", create_pair=True)
        a_cards = database.get_user_cards(user_a, category="Spanish")
        self.assertEqual(len(a_cards), 6)
        b_cards_after = database.get_user_cards(user_b, category="Spanish")
        self.assertEqual(len(b_cards_after), 4)

    def test_collaborative_deck_creation_and_joining(self):
        user_a = 3001
        user_b = 3002

        # User A creates a deck with 1 card pair
        database.add_card(user_a, "bonjour", "hello", "French", create_pair=True)
        token = database.create_deck_share(user_a, "French", share_type="collab")

        info = database.get_deck_share_info(token)
        self.assertEqual(info["share_type"], "collab")
        self.assertEqual(info["card_count"], 1)

        # User B joins collaborative deck
        success, reason, data = database.join_collaborative_deck(user_b, token)
        self.assertTrue(success)
        self.assertEqual(reason, "success")

        # Joining again returns already_member
        success_again, reason_again, _ = database.join_collaborative_deck(user_b, token)
        self.assertFalse(success_again)
        self.assertEqual(reason_again, "already_member")

        # Both users see "French" in categories
        self.assertIn("French", database.get_user_categories(user_a))
        self.assertIn("French", database.get_user_categories(user_b))

        # Both users see the cards in "French"
        cards_a = database.get_user_cards(user_a, "French")
        cards_b = database.get_user_cards(user_b, "French")
        self.assertEqual(len(cards_a), 2)
        self.assertEqual(len(cards_b), 2)

        # User B adds a card to "French"
        database.add_card(user_b, "merci", "thank you", "French", create_pair=True)

        # Both users should now see 4 cards (2 pairs)
        cards_a_updated = database.get_user_cards(user_a, "French")
        cards_b_updated = database.get_user_cards(user_b, "French")
        self.assertEqual(len(cards_a_updated), 4)
        self.assertEqual(len(cards_b_updated), 4)

    def test_collaborative_deck_independent_srs(self):
        user_a = 4001
        user_b = 4002

        # User A creates collab deck with single card
        card_id = database.add_card(user_a, "sol", "sun", "Astronomy", create_pair=False)
        token = database.create_deck_share(user_a, "Astronomy", share_type="collab")
        database.join_collaborative_deck(user_b, token)

        # User A rates the card as "easy"
        res_a = database.update_card_srs(card_id, user_a, "easy")
        self.assertEqual(res_a["interval_days"], 4.0)
        self.assertEqual(res_a["repetition_count"], 1)

        # Verify User B's progress on this card is still unreviewed / new
        cards_b = database.get_user_cards(user_b, "Astronomy")
        card_b = next(c for c in cards_b if c["id"] == card_id)
        self.assertEqual(card_b["interval_days"], 0)
        self.assertEqual(card_b["repetition_count"], 0)

        # User B rates the card as "again"
        res_b = database.update_card_srs(card_id, user_b, "again")
        self.assertEqual(res_b["repetition_count"], 0)
        self.assertAlmostEqual(res_b["interval_days"], 0.007, places=3)

        # User A's progress should remain interval 4.0
        cards_a = database.get_user_cards(user_a, "Astronomy")
        card_a = next(c for c in cards_a if c["id"] == card_id)
        self.assertEqual(card_a["interval_days"], 4.0)
        self.assertEqual(card_a["repetition_count"], 1)

    def test_collaborative_deck_individual_deletion_and_joint_deletion(self):
        user_a = 5001
        user_b = 5002

        # User A creates collab deck with 1 pair (card1 and reverse card2)
        std_id = database.add_card(user_a, "luna", "moon", "Space", create_pair=True)
        token = database.create_deck_share(user_a, "Space", share_type="collab")
        database.join_collaborative_deck(user_b, token)

        self.assertEqual(len(database.get_user_cards(user_a, "Space")), 2)
        self.assertEqual(len(database.get_user_cards(user_b, "Space")), 2)

        # User A deletes the card (both sides)
        success = database.delete_card(std_id, user_a)
        self.assertTrue(success)

        # User A should no longer see the cards
        self.assertEqual(len(database.get_user_cards(user_a, "Space")), 0)
        self.assertEqual(len(database.get_due_cards(user_a, "Space")), 0)

        # User B should STILL see the cards!
        b_cards = database.get_user_cards(user_b, "Space")
        self.assertEqual(len(b_cards), 2)
        self.assertEqual(len(database.get_due_cards(user_b, "Space")), 2)

        # Now User B also deletes the card
        success_b = database.delete_card(std_id, user_b)
        self.assertTrue(success_b)

        # Now BOTH have deleted it -> completely gone from database
        self.assertEqual(len(database.get_user_cards(user_b, "Space")), 0)
        conn = sqlite3.connect(TEST_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM cards WHERE category = 'Space'")
        count = cursor.fetchone()[0]
        conn.close()
        self.assertEqual(count, 0)

    def test_leave_collaborative_deck(self):
        user_a = 6001
        user_b = 6002

        database.add_card(user_a, "wasser", "water", "German", create_pair=False)
        token = database.create_deck_share(user_a, "German", share_type="collab")
        database.join_collaborative_deck(user_b, token)

        collab_deck = database.get_collaborative_deck_for_user(user_b, "German")
        self.assertIsNotNone(collab_deck)

        # User B leaves
        left = database.leave_collaborative_deck(user_b, collab_deck["id"])
        self.assertTrue(left)

        # User B no longer has German in categories
        self.assertNotIn("German", database.get_user_categories(user_b))

        # User A still has German with the card
        self.assertIn("German", database.get_user_categories(user_a))
        self.assertEqual(len(database.get_user_cards(user_a, "German")), 1)

if __name__ == "__main__":
    unittest.main()
