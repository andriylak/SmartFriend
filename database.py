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
            target_language TEXT,
            custom_prompt TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, category)
        )
    """)
    conn.commit()
    conn.close()

def add_card(user_id: int, question: str, answer: str, category: str = "General") -> int:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO cards (user_id, question, answer, category) VALUES (?, ?, ?, ?)",
        (user_id, question, answer, category)
    )
    card_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return card_id

def get_user_cards(user_id: int, category: str = None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if category:
        cursor.execute(
            "SELECT id, question, answer, category, correct_count, incorrect_count FROM cards WHERE user_id = ? AND category = ? ORDER BY created_at DESC",
            (user_id, category)
        )
    else:
        cursor.execute(
            "SELECT id, question, answer, category, correct_count, incorrect_count FROM cards WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        )
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "id": row[0],
            "question": row[1],
            "answer": row[2],
            "category": row[3],
            "correct_count": row[4],
            "incorrect_count": row[5]
        }
        for row in rows
    ]

def get_random_card(user_id: int, category: str = None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if category:
        cursor.execute(
            "SELECT id, question, answer, category, correct_count, incorrect_count FROM cards WHERE user_id = ? AND category = ? ORDER BY RANDOM() LIMIT 1",
            (user_id, category)
        )
    else:
        cursor.execute(
            "SELECT id, question, answer, category, correct_count, incorrect_count FROM cards WHERE user_id = ? ORDER BY RANDOM() LIMIT 1",
            (user_id,)
        )
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "id": row[0],
            "question": row[1],
            "answer": row[2],
            "category": row[3],
            "correct_count": row[4],
            "incorrect_count": row[5]
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

def save_deck_setting(user_id: int, category: str, preset_key: str, target_language: str = None, custom_prompt: str = None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO deck_settings (user_id, category, preset_key, target_language, custom_prompt, updated_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id, category) DO UPDATE SET
            preset_key=excluded.preset_key,
            target_language=excluded.target_language,
            custom_prompt=excluded.custom_prompt,
            updated_at=CURRENT_TIMESTAMP
        """,
        (user_id, category, preset_key, target_language, custom_prompt)
    )
    conn.commit()
    conn.close()

def get_deck_setting(user_id: int, category: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT preset_key, target_language, custom_prompt FROM deck_settings WHERE user_id = ? AND category = ?",
        (user_id, category)
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "preset_key": row[0],
            "target_language": row[1],
            "custom_prompt": row[2]
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
        if q_clean in q_text or q_clean in a_text:
            substring_matches.append(card)
            
    if substring_matches:
        return substring_matches

    # 2. If no substring matches, perform fuzzy matching using difflib
    scored_cards = []
    for card in cards:
        q_score = difflib.SequenceMatcher(None, q_clean, card['question'].lower()).ratio()
        a_score = difflib.SequenceMatcher(None, q_clean, card['answer'].lower()).ratio()
        max_score = max(q_score, a_score)
        
        for word in card['question'].lower().split() + card['answer'].lower().split():
            clean_word = word.strip("?,.!;:()[]{}")
            if clean_word:
                word_score = difflib.SequenceMatcher(None, q_clean, clean_word).ratio()
                if word_score > max_score:
                    max_score = word_score

        if max_score >= 0.4:
            scored_cards.append((max_score, card))

    scored_cards.sort(key=lambda item: item[0], reverse=True)
    return [card for score, card in scored_cards[:5]]

