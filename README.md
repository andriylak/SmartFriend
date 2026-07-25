# 🎓 Learning Companion Telegram Bot

An interactive and lightweight Telegram Bot written in Python using **aiogram v3** and **SQLite** to help you study and retain knowledge using digital flashcards (learning cards).

---

## 🚀 Features

- ➕ **Create Card**: Step-by-step flashcard creation (Category ➡️ Question ➡️ Answer) using Finite State Machine (FSM).
- 📚 **My Cards**: View all your created cards grouped by category, showing correct/incorrect stats, with quick dynamic deletion commands (e.g. `/delete_5`).
- 🎯 **Study/Quiz**: Starts an interactive quiz session where you can:
  - Choose a specific category or study all cards.
  - View the question first.
  - Reveal the answer with an inline button.
  - Grade yourself with "Got it Right" or "Got it Wrong" inline buttons, which update your card statistics.
  - Load the next card seamlessly for rapid learning.
- ❌ **Cancel Command**: Tap **❌ Cancel** or type `/cancel` at any point to cancel active card creation or study session.

---

## 🛠️ Project Structure

```text
/
├── .env                  # Environment file (stores Bot Token securely)
├── .env.example          # Template environment file
├── config.py             # Config loader for environmental variables
├── database.py           # SQLite Database setup and CRUD operations
├── keyboards.py          # Reply and Inline keyboards builders
├── main.py               # Main bot entry point (polls updates)
├── requirements.txt      # Python dependencies
├── test_database.py      # Automated database unit tests
└── handlers/
    ├── common.py         # Start, Help, and Cancel handlers
    ├── cards.py          # Card creation and management handlers
    └── quiz.py           # Active quiz/study loop handlers
```

---

## 📦 Setup and Running

### 1. Requirements
Make sure you have Python 3.10+ installed.

### 2. Install Dependencies
If you aren't using the pre-configured virtual environment, install the requirements with:
```bash
pip install -r requirements.txt
```

### 3. Run Tests
Ensure everything works perfectly:
```bash
python test_database.py
```

### 4. Start the Bot
Run the following command to start the bot:
```bash
python main.py
```

