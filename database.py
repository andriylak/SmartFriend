import sqlite3
import os
import re
import difflib
import random
import secrets

DB_PATH = "learning_bot.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            comment TEXT,
            category TEXT DEFAULT 'General',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            correct_count INTEGER DEFAULT 0,
            incorrect_count INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deck_settings (
            user_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            preset_key TEXT NOT NULL,
            source_language TEXT,
            target_language TEXT,
            custom_prompt TEXT,
            daily_new_limit INTEGER DEFAULT 20,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, category)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_new_cards_log (
            user_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            card_id INTEGER NOT NULL,
            studied_date TEXT NOT NULL,
            PRIMARY KEY (user_id, category, card_id, studied_date)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS collaborative_decks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            owner_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS collaborative_deck_members (
            deck_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT DEFAULT 'member',
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (deck_id, user_id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deck_shares (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            share_token TEXT UNIQUE NOT NULL,
            share_type TEXT NOT NULL,
            sender_id INTEGER NOT NULL,
            deck_name TEXT NOT NULL,
            deck_id INTEGER DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_card_progress (
            user_id INTEGER NOT NULL,
            card_id INTEGER NOT NULL,
            is_hidden INTEGER DEFAULT 0,
            correct_count INTEGER DEFAULT 0,
            incorrect_count INTEGER DEFAULT 0,
            next_review_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            interval_days REAL DEFAULT 0,
            ease_factor REAL DEFAULT 2.5,
            repetition_count INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, card_id)
        )
    """)
    # Migration check for existing databases
    cursor.execute("PRAGMA table_info(deck_settings)")
    columns = [col[1] for col in cursor.fetchall()]
    if "source_language" not in columns:
        cursor.execute("ALTER TABLE deck_settings ADD COLUMN source_language TEXT")
    if "daily_new_limit" not in columns:
        cursor.execute("ALTER TABLE deck_settings ADD COLUMN daily_new_limit INTEGER DEFAULT 20")
        
    cursor.execute("PRAGMA table_info(cards)")
    card_columns = [col[1] for col in cursor.fetchall()]
    if "comment" not in card_columns:
        cursor.execute("ALTER TABLE cards ADD COLUMN comment TEXT")
    if "next_review_at" not in card_columns:
        cursor.execute("ALTER TABLE cards ADD COLUMN next_review_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    if "interval_days" not in card_columns:
        cursor.execute("ALTER TABLE cards ADD COLUMN interval_days REAL DEFAULT 0")
    if "ease_factor" not in card_columns:
        cursor.execute("ALTER TABLE cards ADD COLUMN ease_factor REAL DEFAULT 2.5")
    if "repetition_count" not in card_columns:
        cursor.execute("ALTER TABLE cards ADD COLUMN repetition_count INTEGER DEFAULT 0")
    if "direction" not in card_columns:
        cursor.execute("ALTER TABLE cards ADD COLUMN direction TEXT DEFAULT 'standard'")
    if "collab_deck_id" not in card_columns:
        cursor.execute("ALTER TABLE cards ADD COLUMN collab_deck_id INTEGER DEFAULT NULL")

    # Migration: Auto-generate missing reverse cards for existing cards
    cursor.execute("SELECT id, user_id, question, answer, comment, category, collab_deck_id FROM cards WHERE direction IS NULL OR direction = 'standard'")
    std_cards = cursor.fetchall()
    for std_card in std_cards:
        c_id, u_id, q, a, comm, cat, c_deck_id = std_card
        if c_deck_id is not None:
            cursor.execute(
                "SELECT id FROM cards WHERE collab_deck_id = ? AND direction = 'reverse' AND question = ? AND answer = ?",
                (c_deck_id, a, q)
            )
        else:
            cursor.execute(
                "SELECT id FROM cards WHERE user_id = ? AND category = ? AND direction = 'reverse' AND question = ? AND answer = ? AND collab_deck_id IS NULL",
                (u_id, cat, a, q)
            )
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO cards (user_id, question, answer, comment, category, direction, next_review_at, interval_days, ease_factor, repetition_count, collab_deck_id) VALUES (?, ?, ?, ?, ?, 'reverse', CURRENT_TIMESTAMP, 0, 2.5, 0, ?)",
                (u_id, a, q, comm, cat, c_deck_id)
            )
        
    conn.commit()
    conn.close()

def add_card(user_id: int, question: str, answer: str, category: str = "General", comment: str = None, create_pair: bool = True) -> int:
    collab_deck = get_collaborative_deck_for_user(user_id, category)
    collab_deck_id = collab_deck["id"] if collab_deck else None

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # 1. Standard Card (Q -> A)
    cursor.execute(
        "INSERT INTO cards (user_id, question, answer, comment, category, direction, next_review_at, interval_days, ease_factor, repetition_count, collab_deck_id) VALUES (?, ?, ?, ?, ?, 'standard', CURRENT_TIMESTAMP, 0, 2.5, 0, ?)",
        (user_id, question, answer, comment, category, collab_deck_id)
    )
    std_card_id = cursor.lastrowid

    if collab_deck_id is not None:
        cursor.execute(
            "INSERT OR REPLACE INTO user_card_progress (user_id, card_id, is_hidden, correct_count, incorrect_count, next_review_at, interval_days, ease_factor, repetition_count) VALUES (?, ?, 0, 0, 0, CURRENT_TIMESTAMP, 0, 2.5, 0)",
            (user_id, std_card_id)
        )

    # 2. Reverse Card (A -> Q)
    if create_pair:
        cursor.execute(
            "INSERT INTO cards (user_id, question, answer, comment, category, direction, next_review_at, interval_days, ease_factor, repetition_count, collab_deck_id) VALUES (?, ?, ?, ?, ?, 'reverse', CURRENT_TIMESTAMP, 0, 2.5, 0, ?)",
            (user_id, answer, question, comment, category, collab_deck_id)
        )
        rev_card_id = cursor.lastrowid
        if collab_deck_id is not None:
            cursor.execute(
                "INSERT OR REPLACE INTO user_card_progress (user_id, card_id, is_hidden, correct_count, incorrect_count, next_review_at, interval_days, ease_factor, repetition_count) VALUES (?, ?, 0, 0, 0, CURRENT_TIMESTAMP, 0, 2.5, 0)",
                (user_id, rev_card_id)
            )

    conn.commit()
    conn.close()
    return std_card_id

def get_user_cards(user_id: int, category: str = None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    collab_deck = get_collaborative_deck_for_user(user_id, category) if category else None

    if collab_deck:
        cursor.execute(
            """
            SELECT 
                c.id, c.question, c.answer, c.comment, c.category,
                COALESCE(ucp.correct_count, 0),
                COALESCE(ucp.incorrect_count, 0),
                COALESCE(ucp.next_review_at, c.created_at),
                COALESCE(ucp.interval_days, 0),
                COALESCE(ucp.ease_factor, 2.5),
                COALESCE(ucp.repetition_count, 0),
                c.direction
            FROM cards c
            LEFT JOIN user_card_progress ucp ON c.id = ucp.card_id AND ucp.user_id = ?
            WHERE c.collab_deck_id = ?
              AND COALESCE(ucp.is_hidden, 0) = 0
            ORDER BY c.created_at DESC
            """,
            (user_id, collab_deck["id"])
        )
        rows = cursor.fetchall()
    elif category:
        cursor.execute(
            """
            SELECT id, question, answer, comment, category, correct_count, incorrect_count, next_review_at, interval_days, ease_factor, repetition_count, direction 
            FROM cards 
            WHERE user_id = ? AND category = ? AND collab_deck_id IS NULL 
            ORDER BY created_at DESC
            """,
            (user_id, category)
        )
        rows = cursor.fetchall()
    else:
        cursor.execute(
            """
            SELECT 
                c.id, c.question, c.answer, c.comment, c.category,
                c.correct_count, c.incorrect_count, c.next_review_at, c.interval_days, c.ease_factor, c.repetition_count,
                c.direction
            FROM cards c
            WHERE c.user_id = ? AND c.collab_deck_id IS NULL
            UNION ALL
            SELECT 
                c.id, c.question, c.answer, c.comment, c.category,
                COALESCE(ucp.correct_count, 0),
                COALESCE(ucp.incorrect_count, 0),
                COALESCE(ucp.next_review_at, c.created_at),
                COALESCE(ucp.interval_days, 0),
                COALESCE(ucp.ease_factor, 2.5),
                COALESCE(ucp.repetition_count, 0),
                c.direction
            FROM cards c
            JOIN collaborative_deck_members cdm ON c.collab_deck_id = cdm.deck_id
            LEFT JOIN user_card_progress ucp ON c.id = ucp.card_id AND ucp.user_id = ?
            WHERE cdm.user_id = ? AND COALESCE(ucp.is_hidden, 0) = 0
            ORDER BY 1 DESC
            """,
            (user_id, user_id, user_id)
        )
        rows = cursor.fetchall()

    conn.close()
    return [
        {
            "id": row[0],
            "question": row[1],
            "answer": row[2],
            "comment": row[3] or "",
            "category": row[4],
            "correct_count": row[5],
            "incorrect_count": row[6],
            "next_review_at": row[7],
            "interval_days": row[8] or 0,
            "ease_factor": row[9] or 2.5,
            "repetition_count": row[10] or 0,
            "direction": row[11] or "standard"
        }
        for row in rows
    ]

def get_new_cards_studied_today(user_id: int, category: str = None) -> int:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if category:
        cursor.execute(
            "SELECT COUNT(DISTINCT card_id) FROM daily_new_cards_log WHERE user_id = ? AND category = ? AND studied_date = date('now', 'localtime')",
            (user_id, category)
        )
    else:
        cursor.execute(
            "SELECT COUNT(DISTINCT card_id) FROM daily_new_cards_log WHERE user_id = ? AND studied_date = date('now', 'localtime')",
            (user_id,)
        )
    row = cursor.fetchone()
    count = row[0] if row else 0
    conn.close()
    return count

def get_due_cards(user_id: int, category: str = None, study_all: bool = False):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if study_all:
        if category:
            collab_deck = get_collaborative_deck_for_user(user_id, category)
            if collab_deck:
                cursor.execute(
                    """
                    SELECT c.id, c.question, c.answer, c.comment, c.category,
                           COALESCE(ucp.correct_count, 0), COALESCE(ucp.incorrect_count, 0),
                           COALESCE(ucp.next_review_at, c.created_at), COALESCE(ucp.interval_days, 0),
                           COALESCE(ucp.ease_factor, 2.5), COALESCE(ucp.repetition_count, 0), c.direction
                    FROM cards c
                    LEFT JOIN user_card_progress ucp ON c.id = ucp.card_id AND ucp.user_id = ?
                    WHERE c.collab_deck_id = ? AND COALESCE(ucp.is_hidden, 0) = 0
                    ORDER BY RANDOM()
                    """,
                    (user_id, collab_deck["id"])
                )
            else:
                cursor.execute(
                    "SELECT id, question, answer, comment, category, correct_count, incorrect_count, next_review_at, interval_days, ease_factor, repetition_count, direction FROM cards WHERE user_id = ? AND category = ? AND collab_deck_id IS NULL ORDER BY RANDOM()",
                    (user_id, category)
                )
        else:
            cursor.execute(
                """
                SELECT c.id, c.question, c.answer, c.comment, c.category,
                       c.correct_count, c.incorrect_count, c.next_review_at, c.interval_days, c.ease_factor, c.repetition_count, c.direction
                FROM cards c
                WHERE c.user_id = ? AND c.collab_deck_id IS NULL
                UNION ALL
                SELECT c.id, c.question, c.answer, c.comment, c.category,
                       COALESCE(ucp.correct_count, 0), COALESCE(ucp.incorrect_count, 0),
                       COALESCE(ucp.next_review_at, c.created_at), COALESCE(ucp.interval_days, 0),
                       COALESCE(ucp.ease_factor, 2.5), COALESCE(ucp.repetition_count, 0), c.direction
                FROM cards c
                JOIN collaborative_deck_members cdm ON c.collab_deck_id = cdm.deck_id
                LEFT JOIN user_card_progress ucp ON c.id = ucp.card_id AND ucp.user_id = ?
                WHERE cdm.user_id = ? AND COALESCE(ucp.is_hidden, 0) = 0
                ORDER BY RANDOM()
                """,
                (user_id, user_id, user_id)
            )
        rows = cursor.fetchall()
        conn.close()
    else:
        categories_to_check = [category] if category else get_user_categories(user_id)

        due_learning_rows = []
        due_review_rows = []
        new_rows = []
        learning_ahead_rows = []

        for cat in categories_to_check:
            collab_deck = get_collaborative_deck_for_user(user_id, cat)
            if collab_deck:
                deck_id = collab_deck["id"]
                # 1. Fetch review and learning cards that are currently due (or overdue)
                cursor.execute(
                    """
                    SELECT c.id, c.question, c.answer, c.comment, c.category,
                           COALESCE(ucp.correct_count, 0), COALESCE(ucp.incorrect_count, 0),
                           COALESCE(ucp.next_review_at, c.created_at), COALESCE(ucp.interval_days, 0),
                           COALESCE(ucp.ease_factor, 2.5), COALESCE(ucp.repetition_count, 0), c.direction 
                    FROM cards c
                    LEFT JOIN user_card_progress ucp ON c.id = ucp.card_id AND ucp.user_id = ?
                    WHERE c.collab_deck_id = ?
                      AND COALESCE(ucp.is_hidden, 0) = 0
                      AND (COALESCE(ucp.correct_count, 0) > 0 OR COALESCE(ucp.incorrect_count, 0) > 0 OR COALESCE(ucp.repetition_count, 0) > 0)
                      AND (ucp.next_review_at IS NULL OR ucp.next_review_at <= CURRENT_TIMESTAMP)
                    ORDER BY RANDOM()
                    """,
                    (user_id, deck_id)
                )
                for row in cursor.fetchall():
                    if (row[8] or 0) < 1.0:
                        due_learning_rows.append(row)
                    else:
                        due_review_rows.append(row)

                # 2. Check per-deck daily new cards limit (sorted by c.id ASC so today's batch selects pairs together)
                setting = get_deck_setting(user_id, cat)
                limit = setting.get("daily_new_limit", 20) if setting else 20
                studied_today = get_new_cards_studied_today(user_id, cat)

                if limit <= 0:
                    fetch_limit = -1
                else:
                    fetch_limit = max(0, limit - studied_today)

                if fetch_limit != 0:
                    limit_clause = f" LIMIT {fetch_limit}" if fetch_limit > 0 else ""
                    cursor.execute(
                        f"""
                        SELECT c.id, c.question, c.answer, c.comment, c.category,
                               COALESCE(ucp.correct_count, 0), COALESCE(ucp.incorrect_count, 0),
                               COALESCE(ucp.next_review_at, c.created_at), COALESCE(ucp.interval_days, 0),
                               COALESCE(ucp.ease_factor, 2.5), COALESCE(ucp.repetition_count, 0), c.direction 
                        FROM cards c
                        LEFT JOIN user_card_progress ucp ON c.id = ucp.card_id AND ucp.user_id = ?
                        WHERE c.collab_deck_id = ?
                          AND COALESCE(ucp.is_hidden, 0) = 0
                          AND COALESCE(ucp.correct_count, 0) = 0 AND COALESCE(ucp.incorrect_count, 0) = 0 AND COALESCE(ucp.repetition_count, 0) = 0 
                          AND (ucp.next_review_at IS NULL OR ucp.next_review_at <= CURRENT_TIMESTAMP)
                        ORDER BY c.id ASC
                        {limit_clause}
                        """,
                        (user_id, deck_id)
                    )
                    new_rows.extend(cursor.fetchall())

                # 3. Fetch intraday learning cards scheduled for later today (< 1 day interval)
                cursor.execute(
                    """
                    SELECT c.id, c.question, c.answer, c.comment, c.category,
                           COALESCE(ucp.correct_count, 0), COALESCE(ucp.incorrect_count, 0),
                           COALESCE(ucp.next_review_at, c.created_at), COALESCE(ucp.interval_days, 0),
                           COALESCE(ucp.ease_factor, 2.5), COALESCE(ucp.repetition_count, 0), c.direction 
                    FROM cards c
                    LEFT JOIN user_card_progress ucp ON c.id = ucp.card_id AND ucp.user_id = ?
                    WHERE c.collab_deck_id = ?
                      AND COALESCE(ucp.is_hidden, 0) = 0
                      AND (COALESCE(ucp.correct_count, 0) > 0 OR COALESCE(ucp.incorrect_count, 0) > 0 OR COALESCE(ucp.repetition_count, 0) > 0)
                      AND COALESCE(ucp.interval_days, 0) < 1.0
                      AND ucp.next_review_at > CURRENT_TIMESTAMP
                    ORDER BY RANDOM()
                    """,
                    (user_id, deck_id)
                )
                learning_ahead_rows.extend(cursor.fetchall())
            else:
                # 1. Fetch review and learning cards that are currently due (or overdue)
                cursor.execute(
                    """
                    SELECT id, question, answer, comment, category, correct_count, incorrect_count, next_review_at, interval_days, ease_factor, repetition_count, direction 
                    FROM cards 
                    WHERE user_id = ? AND category = ? AND collab_deck_id IS NULL
                      AND (correct_count > 0 OR incorrect_count > 0 OR repetition_count > 0)
                      AND (next_review_at IS NULL OR next_review_at <= CURRENT_TIMESTAMP)
                    ORDER BY RANDOM()
                    """,
                    (user_id, cat)
                )
                for row in cursor.fetchall():
                    if (row[8] or 0) < 1.0:
                        due_learning_rows.append(row)
                    else:
                        due_review_rows.append(row)

                # 2. Check per-deck daily new cards limit (sorted by id ASC so today's batch selects pairs together)
                setting = get_deck_setting(user_id, cat)
                limit = setting.get("daily_new_limit", 20) if setting else 20
                studied_today = get_new_cards_studied_today(user_id, cat)

                if limit <= 0:
                    fetch_limit = -1
                else:
                    fetch_limit = max(0, limit - studied_today)

                if fetch_limit != 0:
                    limit_clause = f" LIMIT {fetch_limit}" if fetch_limit > 0 else ""
                    cursor.execute(
                        f"""
                        SELECT id, question, answer, comment, category, correct_count, incorrect_count, next_review_at, interval_days, ease_factor, repetition_count, direction 
                        FROM cards 
                        WHERE user_id = ? AND category = ? AND collab_deck_id IS NULL
                          AND correct_count = 0 AND incorrect_count = 0 AND repetition_count = 0 
                          AND (next_review_at IS NULL OR next_review_at <= CURRENT_TIMESTAMP)
                        ORDER BY id ASC
                        {limit_clause}
                        """,
                        (user_id, cat)
                    )
                    new_rows.extend(cursor.fetchall())

                # 3. Fetch intraday learning cards scheduled for later today (< 1 day interval)
                cursor.execute(
                    """
                    SELECT id, question, answer, comment, category, correct_count, incorrect_count, next_review_at, interval_days, ease_factor, repetition_count, direction 
                    FROM cards 
                    WHERE user_id = ? AND category = ? AND collab_deck_id IS NULL
                      AND (correct_count > 0 OR incorrect_count > 0 OR repetition_count > 0)
                      AND interval_days < 1.0
                      AND next_review_at > CURRENT_TIMESTAMP
                    ORDER BY RANDOM()
                    """,
                    (user_id, cat)
                )
                learning_ahead_rows.extend(cursor.fetchall())

        random.shuffle(due_learning_rows)
        random.shuffle(learning_ahead_rows)

        mixed_due_and_new = due_review_rows + new_rows
        random.shuffle(mixed_due_and_new)

        rows = due_learning_rows + mixed_due_and_new + learning_ahead_rows
        conn.close()

    return [
        {
            "id": row[0],
            "question": row[1],
            "answer": row[2],
            "comment": row[3] or "",
            "category": row[4],
            "correct_count": row[5],
            "incorrect_count": row[6],
            "next_review_at": row[7],
            "interval_days": row[8] or 0,
            "ease_factor": row[9] or 2.5,
            "repetition_count": row[10] or 0,
            "direction": row[11] or "standard"
        }
        for row in rows
    ]

def get_due_card_counts(user_id: int):
    categories = get_user_categories(user_id)
    counts = {}
    total_due = 0
    for cat in categories:
        due_cards = get_due_cards(user_id, category=cat, study_all=False)
        cat_count = len(due_cards)
        counts[cat] = cat_count
        total_due += cat_count

    counts["_all_"] = total_due
    return counts

def get_random_card(user_id: int, category: str = None):
    cards = get_user_cards(user_id, category=category)
    if not cards:
        return None
    import random
    return random.choice(cards)

def delete_card(card_id: int, user_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, user_id, category, question, answer, collab_deck_id FROM cards WHERE id = ?",
        (card_id,)
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False

    c_id, owner_id, cat, q, a, collab_deck_id = row

    if collab_deck_id is None:
        if owner_id != user_id:
            conn.close()
            return False

        # Find reverse counterpart if it exists (swapped question and answer in same category)
        cursor.execute(
            "SELECT id FROM cards WHERE user_id = ? AND category = ? AND question = ? AND answer = ? AND collab_deck_id IS NULL",
            (user_id, cat, a, q)
        )
        counterpart_rows = cursor.fetchall()
        counterpart_ids = [r[0] for r in counterpart_rows if r[0] != card_id]

        # Delete primary card
        cursor.execute("DELETE FROM cards WHERE id = ? AND user_id = ?", (card_id, user_id))
        cursor.execute("DELETE FROM daily_new_cards_log WHERE user_id = ? AND card_id = ?", (user_id, card_id))

        # Delete counterpart cards
        for cp_id in counterpart_ids:
            cursor.execute("DELETE FROM cards WHERE id = ? AND user_id = ?", (cp_id, user_id))
            cursor.execute("DELETE FROM daily_new_cards_log WHERE user_id = ? AND card_id = ?", (user_id, cp_id))

        conn.commit()
        conn.close()
        return True
    else:
        # Collaborative card!
        # Check if user is a member of this collaborative deck
        cursor.execute(
            "SELECT user_id FROM collaborative_deck_members WHERE deck_id = ? AND user_id = ?",
            (collab_deck_id, user_id)
        )
        if not cursor.fetchone():
            conn.close()
            return False

        # Find reverse counterpart in same collab deck
        cursor.execute(
            "SELECT id FROM cards WHERE collab_deck_id = ? AND question = ? AND answer = ?",
            (collab_deck_id, a, q)
        )
        target_ids = [card_id] + [r[0] for r in cursor.fetchall() if r[0] != card_id]

        # Get all current members of this deck
        cursor.execute(
            "SELECT user_id FROM collaborative_deck_members WHERE deck_id = ?",
            (collab_deck_id,)
        )
        all_members = [r[0] for r in cursor.fetchall()]

        for tid in target_ids:
            # 1. Hide card for this user
            cursor.execute(
                """
                INSERT INTO user_card_progress (user_id, card_id, is_hidden)
                VALUES (?, ?, 1)
                ON CONFLICT(user_id, card_id) DO UPDATE SET is_hidden = 1
                """,
                (user_id, tid)
            )
            cursor.execute("DELETE FROM daily_new_cards_log WHERE user_id = ? AND card_id = ?", (user_id, tid))

            # 2. Check if ALL active members of the deck have hidden/deleted this card
            cursor.execute(
                """
                SELECT COUNT(DISTINCT user_id) 
                FROM user_card_progress 
                WHERE card_id = ? AND is_hidden = 1 AND user_id IN (
                    SELECT user_id FROM collaborative_deck_members WHERE deck_id = ?
                )
                """,
                (tid, collab_deck_id)
            )
            hidden_member_count = cursor.fetchone()[0]

            if hidden_member_count >= len(all_members) and len(all_members) > 0:
                # All members have deleted it! Permanently delete the card from database!
                cursor.execute("DELETE FROM cards WHERE id = ?", (tid,))
                cursor.execute("DELETE FROM user_card_progress WHERE card_id = ?", (tid,))
                cursor.execute("DELETE FROM daily_new_cards_log WHERE card_id = ?", (tid,))

        conn.commit()
        conn.close()
        return True

def delete_deck(user_id: int, category: str) -> int:
    collab_deck = get_collaborative_deck_for_user(user_id, category)
    if collab_deck:
        deck_id = collab_deck["id"]
        if collab_deck["owner_id"] == user_id:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM cards WHERE collab_deck_id = ?", (deck_id,))
            count = cursor.fetchone()[0]
            cursor.execute("DELETE FROM user_card_progress WHERE card_id IN (SELECT id FROM cards WHERE collab_deck_id = ?)", (deck_id,))
            cursor.execute("DELETE FROM cards WHERE collab_deck_id = ?", (deck_id,))
            cursor.execute("DELETE FROM collaborative_deck_members WHERE deck_id = ?", (deck_id,))
            cursor.execute("DELETE FROM collaborative_decks WHERE id = ?", (deck_id,))
            cursor.execute("DELETE FROM deck_shares WHERE deck_id = ?", (deck_id,))
            cursor.execute("DELETE FROM deck_settings WHERE user_id = ? AND category = ?", (user_id, category))
            cursor.execute("DELETE FROM daily_new_cards_log WHERE user_id = ? AND category = ?", (user_id, category))
            conn.commit()
            conn.close()
            return count
        else:
            leave_collaborative_deck(user_id, deck_id)
            return 0
    else:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM cards WHERE user_id = ? AND category = ? AND collab_deck_id IS NULL",
            (user_id, category)
        )
        count = cursor.fetchone()[0]
        cursor.execute(
            "DELETE FROM cards WHERE user_id = ? AND category = ? AND collab_deck_id IS NULL",
            (user_id, category)
        )
        cursor.execute(
            "DELETE FROM deck_settings WHERE user_id = ? AND category = ?",
            (user_id, category)
        )
        cursor.execute(
            "DELETE FROM daily_new_cards_log WHERE user_id = ? AND category = ?",
            (user_id, category)
        )
        conn.commit()
        conn.close()
        return count

def update_card_stats(card_id: int, user_id: int, correct: bool):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT collab_deck_id FROM cards WHERE id = ?", (card_id,))
    row = cursor.fetchone()
    if row and row[0] is not None:
        if correct:
            cursor.execute(
                """
                INSERT INTO user_card_progress (user_id, card_id, correct_count)
                VALUES (?, ?, 1)
                ON CONFLICT(user_id, card_id) DO UPDATE SET correct_count = correct_count + 1
                """,
                (user_id, card_id)
            )
        else:
            cursor.execute(
                """
                INSERT INTO user_card_progress (user_id, card_id, incorrect_count)
                VALUES (?, ?, 1)
                ON CONFLICT(user_id, card_id) DO UPDATE SET incorrect_count = incorrect_count + 1
                """,
                (user_id, card_id)
            )
    else:
        if correct:
            cursor.execute(
                "UPDATE cards SET correct_count = correct_count + 1 WHERE id = ? AND user_id = ?",
                (card_id, user_id)
            )
        else:
            cursor.execute(
                "UPDATE cards SET incorrect_count = incorrect_count + 1 WHERE id = ? AND user_id = ?",
                (card_id, user_id)
            )
    conn.commit()
    conn.close()

def update_card_srs(card_id: int, user_id: int, rating: str) -> dict:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT collab_deck_id, category, interval_days, ease_factor, repetition_count, correct_count, incorrect_count FROM cards WHERE id = ?",
        (card_id,)
    )
    card_row = cursor.fetchone()
    if not card_row:
        conn.close()
        return {}

    collab_deck_id, category, p_interval, p_ease, p_reps, p_corr, p_incorr = card_row
    category = category or "General"

    if collab_deck_id is not None:
        cursor.execute(
            "SELECT interval_days, ease_factor, repetition_count, correct_count, incorrect_count FROM user_card_progress WHERE user_id = ? AND card_id = ?",
            (user_id, card_id)
        )
        prog_row = cursor.fetchone()
        if prog_row:
            interval, ease, reps, correct_count, incorrect_count = prog_row
            interval = interval or 0.0
            ease = ease or 2.5
            reps = reps or 0
            correct_count = correct_count or 0
            incorrect_count = incorrect_count or 0
        else:
            interval, ease, reps, correct_count, incorrect_count = 0.0, 2.5, 0, 0, 0
    else:
        interval = p_interval or 0.0
        ease = p_ease or 2.5
        reps = p_reps or 0
        correct_count = p_corr or 0
        incorrect_count = p_incorr or 0

    # Track brand-new cards introduced today
    if reps == 0 and correct_count == 0 and incorrect_count == 0 and interval == 0.0:
        cursor.execute(
            "INSERT OR IGNORE INTO daily_new_cards_log (user_id, category, card_id, studied_date) VALUES (?, ?, ?, date('now', 'localtime'))",
            (user_id, category, card_id)
        )

    if rating == "again":
        reps = 0
        interval = 0.007  # ~10 minutes
        ease = max(1.3, round(ease - 0.2, 2))
        incorrect_count += 1
    elif rating == "hard":
        if interval < 1.0:
            interval = 0.007
            reps = 0
        else:
            reps += 1
            interval = float(max(int(round(interval * 1.2)), int(round(interval)) + 1))
            ease = max(1.3, round(ease - 0.15, 2))
        correct_count += 1
    elif rating == "good":
        if interval < 1.0:
            reps = 1
            interval = 1.0
        elif reps == 1:
            reps = 2
            interval = 6.0
        else:
            reps += 1
            interval = float(int(round(interval * ease)))
        correct_count += 1
    elif rating == "easy":
        if interval < 1.0:
            reps = 1
            interval = 4.0
        elif reps == 1:
            reps = 2
            interval = 10.0
        else:
            reps += 1
            interval = float(int(round(interval * ease * 1.3)))
            ease = round(ease + 0.15, 2)
        correct_count += 1

    if collab_deck_id is not None:
        cursor.execute(
            """
            INSERT INTO user_card_progress (user_id, card_id, interval_days, ease_factor, repetition_count, next_review_at, correct_count, incorrect_count, is_hidden)
            VALUES (?, ?, ?, ?, ?, datetime('now', '+' || ? || ' days'), ?, ?, 0)
            ON CONFLICT(user_id, card_id) DO UPDATE SET
                interval_days = excluded.interval_days,
                ease_factor = excluded.ease_factor,
                repetition_count = excluded.repetition_count,
                next_review_at = excluded.next_review_at,
                correct_count = excluded.correct_count,
                incorrect_count = excluded.incorrect_count,
                is_hidden = 0
            """,
            (user_id, card_id, interval, ease, reps, interval, correct_count, incorrect_count)
        )
    else:
        cursor.execute(
            """
            UPDATE cards SET 
                interval_days = ?,
                ease_factor = ?,
                repetition_count = ?,
                next_review_at = datetime('now', '+' || ? || ' days'),
                correct_count = ?,
                incorrect_count = ?
            WHERE id = ? AND user_id = ?
            """,
            (interval, ease, reps, interval, correct_count, incorrect_count, card_id, user_id)
        )

    conn.commit()
    conn.close()

    return {
        "interval_days": interval,
        "ease_factor": ease,
        "repetition_count": reps,
        "rating": rating
    }

def get_user_categories(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT DISTINCT category FROM cards WHERE user_id = ? AND collab_deck_id IS NULL",
        (user_id,)
    )
    personal_cats = [row[0] for row in cursor.fetchall()]
    cursor.execute(
        """
        SELECT cd.name 
        FROM collaborative_decks cd
        JOIN collaborative_deck_members cdm ON cd.id = cdm.deck_id
        WHERE cdm.user_id = ?
        """,
        (user_id,)
    )
    collab_cats = [row[0] for row in cursor.fetchall()]
    conn.close()
    return sorted(list(set(personal_cats + collab_cats)))

def save_deck_setting(user_id: int, category: str, preset_key: str = None, source_language: str = None, target_language: str = None, custom_prompt: str = None, daily_new_limit: int = None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    existing = get_deck_setting(user_id, category)
    
    if preset_key is None:
        preset_key = existing.get("preset_key", "general") if existing else "general"
    if source_language is None and existing:
        source_language = existing.get("source_language")
    if target_language is None and existing:
        target_language = existing.get("target_language")
    if custom_prompt is None and existing:
        custom_prompt = existing.get("custom_prompt")
    if daily_new_limit is None:
        daily_new_limit = existing.get("daily_new_limit", 20) if existing else 20

    cursor.execute(
        """
        INSERT INTO deck_settings (user_id, category, preset_key, source_language, target_language, custom_prompt, daily_new_limit, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id, category) DO UPDATE SET
            preset_key=excluded.preset_key,
            source_language=excluded.source_language,
            target_language=excluded.target_language,
            custom_prompt=excluded.custom_prompt,
            daily_new_limit=excluded.daily_new_limit,
            updated_at=CURRENT_TIMESTAMP
        """,
        (user_id, category, preset_key, source_language, target_language, custom_prompt, daily_new_limit)
    )
    conn.commit()
    conn.close()

def get_deck_setting(user_id: int, category: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT preset_key, source_language, target_language, custom_prompt, daily_new_limit FROM deck_settings WHERE user_id = ? AND category = ? COLLATE NOCASE",
        (user_id, category)
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "preset_key": row[0],
            "source_language": row[1],
            "target_language": row[2],
            "custom_prompt": row[3],
            "daily_new_limit": row[4] if row[4] is not None else 20
        }
    return None

COMMON_ARTICLES = {
    # English
    "the", "a", "an", "to",
    # Spanish
    "el", "la", "los", "las", "un", "una", "unos", "unas",
    # French
    "le", "la", "les", "un", "une", "des", "l", "d",
    # German
    "der", "die", "das", "ein", "eine", "einen", "einem", "einer", "eines",
    # Italian
    "il", "lo", "la", "i", "gli", "le", "un", "uno", "una",
}

def _normalize_word(text: str) -> str:
    if not text:
        return ""
    t = text.strip().lower()
    t = re.sub(r'^[¿¡\s.,;:!?"\'\(\)\[\]\{\}*`~]+|[¿¡\s.,;:!?"\'\(\)\[\]\{\}*`~]+$', '', t)
    return t

def _strip_leading_article(text: str) -> str:
    norm = _normalize_word(text)
    words = norm.split()
    if len(words) > 1 and words[0] in COMMON_ARTICLES:
        return " ".join(words[1:])
    return norm

def find_existing_cards_in_deck(user_id: int, category: str, query: str) -> list:
    """
    Check if a word, phrase, or topic already exists on either side (Question or Answer)
    of a flashcard in the specified deck. Returns a deduplicated list of matching standard cards.
    """
    cards = get_user_cards(user_id, category=category)
    if not cards or not query or not query.strip():
        return []

    # Filter out reverse cards so each dual card pair is only inspected once
    standard_cards = [c for c in cards if c.get("direction") != "reverse"]
    if not standard_cards:
        standard_cards = cards

    q_norm = _normalize_word(query)
    q_no_art = _strip_leading_article(query)
    if not q_norm:
        return []

    exact_matches = []
    close_matches = []

    for card in standard_cards:
        card_q_norm = _normalize_word(card.get("question", ""))
        card_a_norm = _normalize_word(card.get("answer", ""))
        card_q_no_art = _strip_leading_article(card.get("question", ""))
        card_a_no_art = _strip_leading_article(card.get("answer", ""))

        # 1. Exact match (with or without article) on Question or Answer
        if (
            q_norm == card_q_norm
            or q_norm == card_a_norm
            or q_no_art == card_q_no_art
            or q_no_art == card_a_no_art
        ):
            exact_matches.append(card)
            continue

        # 2. Check comma/slash/semicolon/parentheses separated phrases in Question or Answer
        # e.g. answer = "dog, hound" or question = "perro / can"
        q_segments = [_strip_leading_article(p) for p in re.split(r'[,;/|()]', card.get("question", "")) if p.strip()]
        a_segments = [_strip_leading_article(p) for p in re.split(r'[,;/|()]', card.get("answer", "")) if p.strip()]
        if q_no_art in q_segments or q_no_art in a_segments or q_norm in q_segments or q_norm in a_segments:
            exact_matches.append(card)
            continue

        # 3. Whole-word boundary match (if query is at least 2 chars and not just an article)
        if len(q_no_art) >= 2 and q_no_art not in COMMON_ARTICLES:
            pattern = r'(?u)\b' + re.escape(q_no_art) + r'\b'
            if re.search(pattern, card_q_norm) or re.search(pattern, card_a_norm):
                close_matches.append(card)
                continue

    # Deduplicate by card id and question/answer content
    seen_ids = set()
    seen_pairs = set()
    unique_results = []
    for c in exact_matches + close_matches:
        c_id = c.get("id")
        pair_key = (_normalize_word(c.get("question", "")), _normalize_word(c.get("answer", "")))
        if c_id not in seen_ids and pair_key not in seen_pairs:
            seen_ids.add(c_id)
            seen_pairs.add(pair_key)
            unique_results.append(c)

    return unique_results

def search_user_cards(user_id: int, query: str, category: str = None):
    cards = get_user_cards(user_id, category if category != "all" else None)
    if not cards or not query.strip():
        return []

    q_clean = query.strip().lower()
    
    # 1. First, check for exact/substring matches
    substring_matches = []
    for card in cards:
        q_text = card['question'].lower()
        a_text = card['answer'].lower()
        c_text = card.get('comment', '').lower()
        if q_clean in q_text or q_clean in a_text or q_clean in c_text:
            substring_matches.append(card)
            
    if substring_matches:
        return substring_matches

    # 2. If no substring matches, perform fuzzy matching using difflib
    scored_cards = []
    for card in cards:
        q_score = difflib.SequenceMatcher(None, q_clean, card['question'].lower()).ratio()
        a_score = difflib.SequenceMatcher(None, q_clean, card['answer'].lower()).ratio()
        c_score = difflib.SequenceMatcher(None, q_clean, card.get('comment', '').lower()).ratio() if card.get('comment') else 0
        max_score = max(q_score, a_score, c_score)
        
        words = card['question'].lower().split() + card['answer'].lower().split() + card.get('comment', '').lower().split()
        for word in words:
            clean_word = word.strip("?,.!;:()[]{}")
            if clean_word:
                word_score = difflib.SequenceMatcher(None, q_clean, clean_word).ratio()
                if word_score > max_score:
                    max_score = word_score

        if max_score >= 0.4:
            scored_cards.append((max_score, card))

    scored_cards.sort(key=lambda item: item[0], reverse=True)
    return [card for score, card in scored_cards[:5]]

def update_card(card_id: int, user_id: int, question: str = None, answer: str = None, comment: str = None, category: str = None) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Fetch current card info to check for reverse counterpart
    cursor.execute(
        "SELECT id, user_id, question, answer, comment, category, collab_deck_id FROM cards WHERE id = ?",
        (card_id,)
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False

    _, owner_id, old_q, old_a, old_comm, old_cat, collab_deck_id = row

    if collab_deck_id is not None:
        cursor.execute(
            "SELECT user_id FROM collaborative_deck_members WHERE deck_id = ? AND user_id = ?",
            (collab_deck_id, user_id)
        )
        if not cursor.fetchone():
            conn.close()
            return False
        cursor.execute(
            "SELECT id FROM cards WHERE collab_deck_id = ? AND question = ? AND answer = ?",
            (collab_deck_id, old_a, old_q)
        )
        counterpart_ids = [r[0] for r in cursor.fetchall() if r[0] != card_id]
    else:
        if owner_id != user_id:
            conn.close()
            return False
        cursor.execute(
            "SELECT id FROM cards WHERE user_id = ? AND category = ? AND question = ? AND answer = ? AND collab_deck_id IS NULL",
            (user_id, old_cat, old_a, old_q)
        )
        counterpart_ids = [r[0] for r in cursor.fetchall() if r[0] != card_id]

    # 3. Update primary card
    fields = []
    values = []
    if question is not None:
        fields.append("question = ?")
        values.append(question)
    if answer is not None:
        fields.append("answer = ?")
        values.append(answer)
    if comment is not None:
        fields.append("comment = ?")
        values.append(comment)
    if category is not None:
        fields.append("category = ?")
        values.append(category)
        
    if not fields:
        conn.close()
        return False
        
    query = f"UPDATE cards SET {', '.join(fields)} WHERE id = ?"
    values.append(card_id)
    cursor.execute(query, tuple(values))

    # 4. Also keep reverse counterpart card in sync if it exists
    if counterpart_ids:
        cp_fields = []
        cp_values = []
        if question is not None:
            cp_fields.append("answer = ?")
            cp_values.append(question)
        if answer is not None:
            cp_fields.append("question = ?")
            cp_values.append(answer)
        if comment is not None:
            cp_fields.append("comment = ?")
            cp_values.append(comment)
        if category is not None:
            cp_fields.append("category = ?")
            cp_values.append(category)

        if cp_fields:
            for c_id in counterpart_ids:
                cp_query = f"UPDATE cards SET {', '.join(cp_fields)} WHERE id = ?"
                cursor.execute(cp_query, tuple(cp_values + [c_id]))

    conn.commit()
    conn.close()
    return True

# --- COLLABORATIVE & SHARED DECK FUNCTIONS ---

def get_collaborative_deck_for_user(user_id: int, category: str):
    if not category:
        return None
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT cd.id, cd.name, cd.owner_id, cd.created_at, cdm.role
        FROM collaborative_decks cd
        JOIN collaborative_deck_members cdm ON cd.id = cdm.deck_id
        WHERE cdm.user_id = ? AND cd.name = ?
        """,
        (user_id, category)
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "id": row[0],
            "name": row[1],
            "owner_id": row[2],
            "created_at": row[3],
            "role": row[4]
        }
    return None

def get_collaborative_deck_by_id(deck_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, owner_id, created_at FROM collaborative_decks WHERE id = ?",
        (deck_id,)
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "id": row[0],
            "name": row[1],
            "owner_id": row[2],
            "created_at": row[3]
        }
    return None

def get_collaborative_deck_members(deck_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT user_id, role, joined_at FROM collaborative_deck_members WHERE deck_id = ? ORDER BY joined_at ASC",
        (deck_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [{"user_id": r[0], "role": r[1], "joined_at": r[2]} for r in rows]

def get_user_collaborative_decks(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT cd.id, cd.name, cd.owner_id, cd.created_at, cdm.role
        FROM collaborative_decks cd
        JOIN collaborative_deck_members cdm ON cd.id = cdm.deck_id
        WHERE cdm.user_id = ?
        ORDER BY cd.name ASC
        """,
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "name": r[1],
            "owner_id": r[2],
            "created_at": r[3],
            "role": r[4]
        }
        for r in rows
    ]

def make_deck_collaborative(owner_id: int, category: str) -> int:
    existing = get_collaborative_deck_for_user(owner_id, category)
    if existing:
        return existing["id"]

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO collaborative_decks (name, owner_id) VALUES (?, ?)",
        (category, owner_id)
    )
    deck_id = cursor.lastrowid
    cursor.execute(
        "INSERT INTO collaborative_deck_members (deck_id, user_id, role) VALUES (?, ?, 'owner')",
        (deck_id, owner_id)
    )

    # Migrate owner's existing personal cards in this category to the collaborative deck
    cursor.execute(
        "SELECT id, correct_count, incorrect_count, next_review_at, interval_days, ease_factor, repetition_count FROM cards WHERE user_id = ? AND category = ? AND collab_deck_id IS NULL",
        (owner_id, category)
    )
    cards_to_migrate = cursor.fetchall()

    cursor.execute(
        "UPDATE cards SET collab_deck_id = ? WHERE user_id = ? AND category = ? AND collab_deck_id IS NULL",
        (deck_id, owner_id, category)
    )

    for c in cards_to_migrate:
        c_id, corr, incorr, next_rev, interv, ease, reps = c
        cursor.execute(
            """
            INSERT OR REPLACE INTO user_card_progress 
            (user_id, card_id, is_hidden, correct_count, incorrect_count, next_review_at, interval_days, ease_factor, repetition_count)
            VALUES (?, ?, 0, ?, ?, ?, ?, ?, ?)
            """,
            (owner_id, c_id, corr or 0, incorr or 0, next_rev, interv or 0, ease or 2.5, reps or 0)
        )

    conn.commit()
    conn.close()
    return deck_id

def create_deck_share(sender_id: int, category: str, share_type: str) -> str:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    token = secrets.token_urlsafe(12)
    deck_id = None
    if share_type == "collab":
        deck_id = make_deck_collaborative(sender_id, category)

    cursor.execute(
        "INSERT INTO deck_shares (share_token, share_type, sender_id, deck_name, deck_id) VALUES (?, ?, ?, ?, ?)",
        (token, share_type, sender_id, category, deck_id)
    )
    conn.commit()
    conn.close()
    return token

def get_deck_share_info(share_token: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT share_token, share_type, sender_id, deck_name, deck_id, created_at FROM deck_shares WHERE share_token = ?",
        (share_token,)
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None

    token, share_type, sender_id, deck_name, deck_id, created_at = row

    if share_type == "collab" and deck_id is not None:
        cursor.execute(
            "SELECT COUNT(DISTINCT id) FROM cards WHERE collab_deck_id = ? AND direction = 'standard'",
            (deck_id,)
        )
        c_row = cursor.fetchone()
        card_count = c_row[0] if c_row else 0
        if card_count == 0:
            cursor.execute(
                "SELECT COUNT(*) FROM cards WHERE collab_deck_id = ?",
                (deck_id,)
            )
            card_count = cursor.fetchone()[0]
    else:
        cursor.execute(
            "SELECT COUNT(DISTINCT id) FROM cards WHERE user_id = ? AND category = ? AND direction = 'standard'",
            (sender_id, deck_name)
        )
        c_row = cursor.fetchone()
        card_count = c_row[0] if c_row else 0
        if card_count == 0:
            cursor.execute(
                "SELECT COUNT(*) FROM cards WHERE user_id = ? AND category = ?",
                (sender_id, deck_name)
            )
            card_count = cursor.fetchone()[0]

    conn.close()
    return {
        "share_token": token,
        "share_type": share_type,
        "sender_id": sender_id,
        "deck_name": deck_name,
        "deck_id": deck_id,
        "card_count": card_count,
        "created_at": created_at
    }

def import_deck_copy(recipient_id: int, share_token: str, target_category: str = None) -> tuple[int, str]:
    share_info = get_deck_share_info(share_token)
    if not share_info:
        return 0, ""

    sender_id = share_info["sender_id"]
    source_cat = share_info["deck_name"]
    deck_id = share_info["deck_id"]

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if deck_id is not None:
        cursor.execute(
            "SELECT question, answer, comment, direction FROM cards WHERE collab_deck_id = ?",
            (deck_id,)
        )
    else:
        cursor.execute(
            "SELECT question, answer, comment, direction FROM cards WHERE user_id = ? AND category = ? AND collab_deck_id IS NULL",
            (sender_id, source_cat)
        )
    source_cards = cursor.fetchall()

    if not source_cards:
        conn.close()
        return 0, source_cat

    if target_category:
        dest_cat = target_category
    else:
        dest_cat = source_cat
        cursor.execute("SELECT DISTINCT category FROM cards WHERE user_id = ? AND collab_deck_id IS NULL", (recipient_id,))
        existing_cats = [r[0] for r in cursor.fetchall()]
        if dest_cat in existing_cats:
            idx = 2
            cand = f"{dest_cat} (Copy)"
            while cand in existing_cats:
                cand = f"{dest_cat} (Copy {idx})"
                idx += 1
            dest_cat = cand

    # Copy deck settings if exists
    sender_settings = get_deck_setting(sender_id, source_cat)
    if sender_settings:
        save_deck_setting(
            user_id=recipient_id,
            category=dest_cat,
            preset_key=sender_settings.get("preset_key", "general"),
            source_language=sender_settings.get("source_language"),
            target_language=sender_settings.get("target_language"),
            custom_prompt=sender_settings.get("custom_prompt"),
            daily_new_limit=sender_settings.get("daily_new_limit", 20)
        )

    for sc in source_cards:
        q, a, comm, direct = sc
        cursor.execute(
            """
            INSERT INTO cards (user_id, question, answer, comment, category, direction, next_review_at, interval_days, ease_factor, repetition_count, collab_deck_id)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 0, 2.5, 0, NULL)
            """,
            (recipient_id, q, a, comm, dest_cat, direct or "standard")
        )

    conn.commit()
    conn.close()

    std_count = len([c for c in source_cards if c[3] == "standard" or c[3] is None])
    imported_count = std_count if std_count > 0 else len(source_cards)

    return imported_count, dest_cat

def join_collaborative_deck(user_id: int, share_token: str) -> tuple[bool, str, dict]:
    share_info = get_deck_share_info(share_token)
    if not share_info:
        return False, "not_found", {}

    if share_info["share_type"] != "collab":
        return False, "invalid_type", share_info

    deck_id = share_info["deck_id"]
    if deck_id is None:
        return False, "invalid_deck", share_info

    deck = get_collaborative_deck_by_id(deck_id)
    if not deck:
        return False, "deck_not_found", share_info

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check if already a member
    cursor.execute(
        "SELECT role FROM collaborative_deck_members WHERE deck_id = ? AND user_id = ?",
        (deck_id, user_id)
    )
    if cursor.fetchone():
        conn.close()
        return False, "already_member", {**share_info, "deck": deck}

    # If user has a personal deck with the same name, rename personal deck to avoid collision
    deck_name = deck["name"]
    cursor.execute(
        "SELECT COUNT(*) FROM cards WHERE user_id = ? AND category = ? AND collab_deck_id IS NULL",
        (user_id, deck_name)
    )
    if cursor.fetchone()[0] > 0:
        renamed_personal = f"{deck_name} (Personal)"
        cursor.execute(
            "UPDATE cards SET category = ? WHERE user_id = ? AND category = ? AND collab_deck_id IS NULL",
            (renamed_personal, user_id, deck_name)
        )
        cursor.execute(
            "UPDATE deck_settings SET category = ? WHERE user_id = ? AND category = ?",
            (renamed_personal, user_id, deck_name)
        )

    cursor.execute(
        "INSERT INTO collaborative_deck_members (deck_id, user_id, role) VALUES (?, ?, 'member')",
        (deck_id, user_id)
    )

    owner_settings = get_deck_setting(deck["owner_id"], deck_name)
    if owner_settings:
        user_settings = get_deck_setting(user_id, deck_name)
        if not user_settings:
            save_deck_setting(
                user_id=user_id,
                category=deck_name,
                preset_key=owner_settings.get("preset_key", "general"),
                source_language=owner_settings.get("source_language"),
                target_language=owner_settings.get("target_language"),
                custom_prompt=owner_settings.get("custom_prompt"),
                daily_new_limit=owner_settings.get("daily_new_limit", 20)
            )

    conn.commit()
    conn.close()
    return True, "success", {**share_info, "deck": deck}

def leave_collaborative_deck(user_id: int, deck_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role FROM collaborative_deck_members WHERE deck_id = ? AND user_id = ?",
        (deck_id, user_id)
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False

    cursor.execute(
        "DELETE FROM collaborative_deck_members WHERE deck_id = ? AND user_id = ?",
        (deck_id, user_id)
    )

    cursor.execute(
        """
        DELETE FROM user_card_progress 
        WHERE user_id = ? AND card_id IN (
            SELECT id FROM cards WHERE collab_deck_id = ?
        )
        """,
        (user_id, deck_id)
    )

    cursor.execute("SELECT COUNT(*) FROM collaborative_deck_members WHERE deck_id = ?", (deck_id,))
    remaining_count = cursor.fetchone()[0]

    if remaining_count == 0:
        cursor.execute("DELETE FROM cards WHERE collab_deck_id = ?", (deck_id,))
        cursor.execute("DELETE FROM collaborative_decks WHERE id = ?", (deck_id,))
        cursor.execute("DELETE FROM deck_shares WHERE deck_id = ?", (deck_id,))

    conn.commit()
    conn.close()
    return True

