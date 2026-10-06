#!/usr/bin/env python3
"""
Diagnostic and Repair Script for Learning Bot Deck Prompts.

Usage:
    python fix_deck_prompts.py [path_to_db]

Examples:
    python fix_deck_prompts.py
    python fix_deck_prompts.py /var/bot/learning_bot.db
    python fix_deck_prompts.py "C:\\path\\to\\other.db"
"""

import sys
import os
import sqlite3

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def run_repair(db_path: str):
    if not os.path.exists(db_path):
        print(f"[!] Database file not found at: {db_path}")
        sys.exit(1)

    print(f"[*] Inspecting and repairing database: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Ensure required tables exist
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

    # Check for missing columns in cards and deck_settings
    cursor.execute("PRAGMA table_info(cards)")
    card_cols = [c[1] for c in cursor.fetchall()]
    if "collab_deck_id" not in card_cols:
        cursor.execute("ALTER TABLE cards ADD COLUMN collab_deck_id INTEGER DEFAULT NULL")
        print("  ➕ Added missing column 'collab_deck_id' to cards table.")
    if "direction" not in card_cols:
        cursor.execute("ALTER TABLE cards ADD COLUMN direction TEXT DEFAULT 'standard'")
        print("  ➕ Added missing column 'direction' to cards table.")

    cursor.execute("PRAGMA table_info(deck_settings)")
    deck_cols = [c[1] for c in cursor.fetchall()]
    if "daily_new_limit" not in deck_cols:
        cursor.execute("ALTER TABLE deck_settings ADD COLUMN daily_new_limit INTEGER DEFAULT 20")
        print("  ➕ Added missing column 'daily_new_limit' to deck_settings table.")

    # 2. Inspect existing deck settings
    cursor.execute("SELECT user_id, category, preset_key, source_language, target_language, custom_prompt, daily_new_limit FROM deck_settings")
    current_settings = cursor.fetchall()
    print(f"\n📋 Found {len(current_settings)} current deck setting(s):")
    for row in current_settings:
        u_id, cat, p_key, s_lang, t_lang, c_prompt, d_limit = row
        print(f"  • User {u_id} | Deck '{cat}' | Preset: '{p_key}' | FROM: '{s_lang}' ➔ TO: '{t_lang}' | Custom: '{c_prompt}'")

    # 3. Find all distinct user_id and category combinations in cards table
    cursor.execute("SELECT DISTINCT user_id, category FROM cards")
    deck_combos = cursor.fetchall()

    repaired_count = 0

    for user_id, category in deck_combos:
        cursor.execute(
            "SELECT preset_key, source_language, target_language, custom_prompt, daily_new_limit FROM deck_settings WHERE user_id = ? AND category = ? COLLATE NOCASE",
            (user_id, category)
        )
        row = cursor.fetchone()

        needs_repair = False
        new_preset = "general"
        new_s_lang = None
        new_t_lang = None
        new_c_prompt = None
        new_limit = 20

        is_cz_deck = category.strip().lower() in ["cz", "czech", "česky", "cesky"]

        if row is None:
            # No setting exists yet
            needs_repair = True
            if is_cz_deck:
                new_preset = "language"
                new_s_lang = "Czech"
                new_t_lang = "English"
            else:
                new_preset = "general"
        else:
            p_key, s_lang, t_lang, c_prompt, d_limit = row
            new_preset = p_key
            new_s_lang = s_lang
            new_t_lang = t_lang
            new_c_prompt = c_prompt
            new_limit = d_limit if d_limit is not None else 20

            # Broken state 1: custom preset without a custom prompt
            if p_key == "custom" and (not c_prompt or not c_prompt.strip()):
                needs_repair = True
                if is_cz_deck:
                    new_preset = "language"
                    new_s_lang = "Czech"
                    new_t_lang = "English"
                    new_c_prompt = None
                else:
                    new_preset = "general"
                    new_c_prompt = None

            # Broken state 2: Language deck without source or target language
            if p_key == "language" and is_cz_deck and (not s_lang or not t_lang):
                needs_repair = True
                new_s_lang = s_lang or "Czech"
                new_t_lang = t_lang or "English"

        if needs_repair:
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
                (user_id, category, new_preset, new_s_lang, new_t_lang, new_c_prompt, new_limit)
            )
            repaired_count += 1
            print(f"  ✨ Repaired deck '{category}' for user {user_id} ➔ Preset: {new_preset} (FROM: {new_s_lang} ➔ TO: {new_t_lang})")

    conn.commit()
    conn.close()

    if repaired_count > 0:
        print(f"\n✅ Successfully repaired {repaired_count} deck prompt(s)!")
    else:
        print("\n✅ All deck prompts are already valid and in good health!")

if __name__ == "__main__":
    target_db = sys.argv[1] if len(sys.argv) > 1 else os.getenv("DB_PATH", "learning_bot.db")
    run_repair(target_db)
