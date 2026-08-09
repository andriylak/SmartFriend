import sqlite3
import os

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

def get_user_cards(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
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
