import sqlite3
import os
import difflib

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

    # Migration: Auto-generate missing reverse cards for existing cards
    cursor.execute("SELECT id, user_id, question, answer, comment, category FROM cards WHERE direction IS NULL OR direction = 'standard'")
    std_cards = cursor.fetchall()
    for std_card in std_cards:
        c_id, u_id, q, a, comm, cat = std_card
        cursor.execute(
            "SELECT id FROM cards WHERE user_id = ? AND category = ? AND direction = 'reverse' AND question = ? AND answer = ?",
            (u_id, cat, a, q)
        )
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO cards (user_id, question, answer, comment, category, direction, next_review_at, interval_days, ease_factor, repetition_count) VALUES (?, ?, ?, ?, ?, 'reverse', CURRENT_TIMESTAMP, 0, 2.5, 0)",
                (u_id, a, q, comm, cat)
            )
        
    conn.commit()
    conn.close()

def add_card(user_id: int, question: str, answer: str, category: str = "General", comment: str = None, create_pair: bool = True) -> int:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # 1. Standard Card (Q -> A)
    cursor.execute(
        "INSERT INTO cards (user_id, question, answer, comment, category, direction, next_review_at, interval_days, ease_factor, repetition_count) VALUES (?, ?, ?, ?, ?, 'standard', CURRENT_TIMESTAMP, 0, 2.5, 0)",
        (user_id, question, answer, comment, category)
    )
    std_card_id = cursor.lastrowid

    # 2. Reverse Card (A -> Q)
    if create_pair:
        cursor.execute(
            "INSERT INTO cards (user_id, question, answer, comment, category, direction, next_review_at, interval_days, ease_factor, repetition_count) VALUES (?, ?, ?, ?, ?, 'reverse', CURRENT_TIMESTAMP, 0, 2.5, 0)",
            (user_id, answer, question, comment, category)
        )

    conn.commit()
    conn.close()
    return std_card_id

def get_user_cards(user_id: int, category: str = None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if category:
        cursor.execute(
            "SELECT id, question, answer, comment, category, correct_count, incorrect_count, next_review_at, interval_days, ease_factor, repetition_count, direction FROM cards WHERE user_id = ? AND category = ? ORDER BY created_at DESC",
            (user_id, category)
        )
    else:
        cursor.execute(
            "SELECT id, question, answer, comment, category, correct_count, incorrect_count, next_review_at, interval_days, ease_factor, repetition_count, direction FROM cards WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
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
            cursor.execute(
                "SELECT id, question, answer, comment, category, correct_count, incorrect_count, next_review_at, interval_days, ease_factor, repetition_count, direction FROM cards WHERE user_id = ? AND category = ? ORDER BY RANDOM()",
                (user_id, category)
            )
        else:
            cursor.execute(
                "SELECT id, question, answer, comment, category, correct_count, incorrect_count, next_review_at, interval_days, ease_factor, repetition_count, direction FROM cards WHERE user_id = ? ORDER BY RANDOM()",
                (user_id,)
            )
        rows = cursor.fetchall()
        conn.close()
    else:
        if category:
            categories_to_check = [category]
        else:
            cursor.execute("SELECT DISTINCT category FROM cards WHERE user_id = ?", (user_id,))
            categories_to_check = [r[0] for r in cursor.fetchall()]

        rows = []
        for cat in categories_to_check:
            # 1. Fetch review and learning cards (cards that have already been answered at least once)
            cursor.execute(
                """
                SELECT id, question, answer, comment, category, correct_count, incorrect_count, next_review_at, interval_days, ease_factor, repetition_count, direction 
                FROM cards 
                WHERE user_id = ? AND category = ? 
                  AND (correct_count > 0 OR incorrect_count > 0 OR repetition_count > 0)
                  AND (next_review_at IS NULL OR next_review_at <= CURRENT_TIMESTAMP)
                ORDER BY 
                    CASE 
                        WHEN interval_days < 1.0 THEN 0
                        ELSE 1
                    END ASC,
                    interval_days ASC,
                    RANDOM()
                """,
                (user_id, cat)
            )
            rows.extend(cursor.fetchall())

            # 2. Check per-deck daily new cards limit
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
                    WHERE user_id = ? AND category = ? 
                      AND correct_count = 0 AND incorrect_count = 0 AND repetition_count = 0 
                      AND (next_review_at IS NULL OR next_review_at <= CURRENT_TIMESTAMP)
                    ORDER BY id ASC
                    {limit_clause}
                    """,
                    (user_id, cat)
                )
                rows.extend(cursor.fetchall())

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
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT category FROM cards WHERE user_id = ?", (user_id,))
    categories = [r[0] for r in cursor.fetchall()]
    conn.close()

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
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if category:
        cursor.execute(
            "SELECT id, question, answer, comment, category, correct_count, incorrect_count, next_review_at, interval_days, ease_factor, repetition_count FROM cards WHERE user_id = ? AND category = ? ORDER BY RANDOM() LIMIT 1",
            (user_id, category)
        )
    else:
        cursor.execute(
            "SELECT id, question, answer, comment, category, correct_count, incorrect_count, next_review_at, interval_days, ease_factor, repetition_count FROM cards WHERE user_id = ? ORDER BY RANDOM() LIMIT 1",
            (user_id,)
        )
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
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
            "repetition_count": row[10] or 0
        }
    return None

def delete_card(card_id: int, user_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM cards WHERE id = ? AND user_id = ?",
        (card_id, user_id)
    )
    changes = conn.total_changes
    conn.commit()
    conn.close()
    return changes > 0

def update_card_stats(card_id: int, user_id: int, correct: bool):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
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
        "SELECT interval_days, ease_factor, repetition_count, correct_count, incorrect_count, category FROM cards WHERE id = ? AND user_id = ?",
        (card_id, user_id)
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {}

    interval = row[0] or 0.0
    ease = row[1] or 2.5
    reps = row[2] or 0
    correct_count = row[3] or 0
    incorrect_count = row[4] or 0
    category = row[5] or "General"

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
        "SELECT DISTINCT category FROM cards WHERE user_id = ? ORDER BY category ASC",
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]

def save_deck_setting(user_id: int, category: str, preset_key: str = "general", source_language: str = None, target_language: str = None, custom_prompt: str = None, daily_new_limit: int = None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if daily_new_limit is None:
        existing = get_deck_setting(user_id, category)
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
        "SELECT preset_key, source_language, target_language, custom_prompt, daily_new_limit FROM deck_settings WHERE user_id = ? AND category = ?",
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

