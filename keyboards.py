import urllib.parse
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Create Card"), KeyboardButton(text="🎯 Study/Quiz")],
            [KeyboardButton(text="📚 My Cards"), KeyboardButton(text="ℹ️ Help")]
        ],
        resize_keyboard=True,
        placeholder="Select an option..."
    )
    return keyboard

def get_cancel_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❌ Cancel")]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_cancel_or_back_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔙 Back"), KeyboardButton(text="❌ Cancel")]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_skip_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⏩ Skip")],
            [KeyboardButton(text="❌ Cancel")]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_reveal_keyboard(card_id: int, is_reversed: bool = False):
    # Inline keyboard to show the answer or question for a card
    builder = InlineKeyboardBuilder()
    text = "👁️ Show Question" if is_reversed else "👁️ Show Answer"
    cb = f"reveal_rev_{card_id}" if is_reversed else f"reveal_std_{card_id}"
    builder.add(InlineKeyboardButton(text=text, callback_data=cb))
    builder.add(
        InlineKeyboardButton(text="✏️ Edit", callback_data=f"study_edit_{card_id}"),
        InlineKeyboardButton(text="🗑️ Delete", callback_data=f"study_delete_unrev_{card_id}")
    )
    builder.add(InlineKeyboardButton(text="❌ End Session", callback_data="study_stop"))
    builder.adjust(1, 2, 1)
    return builder.as_markup()

def get_evaluation_keyboard(card_id: int):
    # Inline keyboard for Anki 4-tier SRS grading
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="🔴 Again", callback_data=f"srs_again_{card_id}"),
        InlineKeyboardButton(text="🟠 Hard", callback_data=f"srs_hard_{card_id}"),
        InlineKeyboardButton(text="🟢 Good", callback_data=f"srs_good_{card_id}"),
        InlineKeyboardButton(text="🔵 Easy", callback_data=f"srs_easy_{card_id}"),
        InlineKeyboardButton(text="✏️ Edit", callback_data=f"study_edit_{card_id}"),
        InlineKeyboardButton(text="🗑️ Delete", callback_data=f"study_delete_rev_{card_id}"),
        InlineKeyboardButton(text="❌ End Session", callback_data="study_stop")
    )
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup()

def get_study_delete_confirm_keyboard(card_id: int, from_view: str = "unrev"):
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="⚠️ Yes, Delete Card", callback_data=f"confirm_study_del_{card_id}"),
        InlineKeyboardButton(text="❌ Cancel", callback_data=f"cancel_study_del_{from_view}_{card_id}")
    )
    builder.adjust(1)
    return builder.as_markup()

def get_card_edit_menu_keyboard(card_id: int):
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="✏️ Edit Question", callback_data=f"edit_field_q_{card_id}"),
        InlineKeyboardButton(text="✏️ Edit Answer", callback_data=f"edit_field_a_{card_id}"),
        InlineKeyboardButton(text="✏️ Edit Comment", callback_data=f"edit_field_c_{card_id}"),
        InlineKeyboardButton(text="📁 Change Deck / Category", callback_data=f"edit_field_cat_{card_id}"),
        InlineKeyboardButton(text="🔙 Back to Study", callback_data="study_resume")
    )
    builder.adjust(1)
    return builder.as_markup()


def get_study_ahead_keyboard(category: str):
    builder = InlineKeyboardBuilder()
    cat_param = category if category else "all"
    builder.add(
        InlineKeyboardButton(text="⚡ Study All Cards Anyway", callback_data=f"study_ahead_{cat_param}"),
        InlineKeyboardButton(text="🔙 Choose Another Deck", callback_data="study_back_decks"),
        InlineKeyboardButton(text="❌ End Session", callback_data="study_stop")
    )
    builder.adjust(1)
    return builder.as_markup()

def get_delete_card_keyboard(card_id: int):
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="🗑️ Delete Card", callback_data=f"delete_{card_id}"))
    return builder.as_markup()

def get_card_creation_mode_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🤖 AI-Assisted Card"), KeyboardButton(text="✍️ Manual Card")],
            [KeyboardButton(text="❌ Cancel")]
        ],
        resize_keyboard=True,
        placeholder="Choose creation method..."
    )
    return keyboard

def get_ai_prompt_presets_keyboard(allow_keep: bool = False):
    rows = [
        [KeyboardButton(text="🌐 Language Learning"), KeyboardButton(text="📚 Definitions & Concepts")],
        [KeyboardButton(text="💻 Programming & Syntax"), KeyboardButton(text="🧠 General Knowledge")],
        [KeyboardButton(text="✏️ Custom Prompt")]
    ]
    if allow_keep:
        rows.append([KeyboardButton(text="🔙 Keep Current Preset"), KeyboardButton(text="❌ Cancel")])
    else:
        rows.append([KeyboardButton(text="❌ Cancel")])
    keyboard = ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        placeholder="Select AI prompt preset..."
    )
    return keyboard

def get_source_languages_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🇪🇸 Spanish"), KeyboardButton(text="🇬🇧 English")],
            [KeyboardButton(text="🇺🇦 Ukrainian"), KeyboardButton(text="🇩🇪 German")],
            [KeyboardButton(text="🇫🇷 French"), KeyboardButton(text="🇮🇹 Italian")],
            [KeyboardButton(text="🇵🇱 Polish")],
            [KeyboardButton(text="❌ Cancel")]
        ],
        resize_keyboard=True,
        placeholder="Choose or type source (learning) language..."
    )
    return keyboard

def get_target_languages_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🇬🇧 English"), KeyboardButton(text="🇺🇦 Ukrainian")],
            [KeyboardButton(text="🇪🇸 Spanish"), KeyboardButton(text="🇩🇪 German")],
            [KeyboardButton(text="🇫🇷 French"), KeyboardButton(text="🇮🇹 Italian")],
            [KeyboardButton(text="🇵🇱 Polish")],
            [KeyboardButton(text="❌ Cancel")]
        ],
        resize_keyboard=True,
        placeholder="Choose or type target language..."
    )
    return keyboard

def get_ai_preview_keyboard():
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="✅ Save Card", callback_data="ai_save"),
        InlineKeyboardButton(text="✏️ Edit Question", callback_data="ai_edit_q"),
        InlineKeyboardButton(text="✏️ Edit Answer", callback_data="ai_edit_a"),
        InlineKeyboardButton(text="✏️ Edit Comment", callback_data="ai_edit_c"),
        InlineKeyboardButton(text="🔄 Regenerate", callback_data="ai_regen"),
        InlineKeyboardButton(text="❌ Cancel", callback_data="ai_cancel")
    )
    builder.adjust(1, 2, 2, 1)
    return builder.as_markup()

def get_categories_keyboard(categories: list, due_counts: dict = None):
    builder = InlineKeyboardBuilder()
    counts = due_counts or {}
    all_due = counts.get("_all_", 0)
    
    # Add an option to quiz from all categories
    builder.add(InlineKeyboardButton(text=f"🌐 All Decks ({all_due} due)", callback_data="quiz_cat_all"))
    
    # Add each category as a button
    for cat in categories:
        cat_due = counts.get(cat, 0)
        builder.add(InlineKeyboardButton(text=f"📁 {cat} ({cat_due} due)", callback_data=f"quiz_cat_{cat}"))
        
    builder.add(InlineKeyboardButton(text="⚙️ Configure Decks", callback_data="quiz_cfg_list"))
    builder.adjust(1) # one button per row
    return builder.as_markup()

def get_deck_config_list_keyboard(categories: list):
    builder = InlineKeyboardBuilder()
    for cat in categories:
        builder.add(InlineKeyboardButton(text=f"⚙️ {cat}", callback_data=f"cfg_deck_{cat}"))
    builder.add(InlineKeyboardButton(text="🔙 Back to Study", callback_data="study_back_decks"))
    builder.adjust(1)
    return builder.as_markup()

def get_deck_config_menu_keyboard(category: str, is_collab: bool = False, is_owner: bool = True):
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="🔢 Change Daily New Limit", callback_data=f"cfg_limit_{category}"),
        InlineKeyboardButton(text="🤖 Change AI Generator Preset", callback_data=f"cfg_preset_{category}"),
        InlineKeyboardButton(text="🔗 Share Deck", callback_data=f"share_deck_{category}")
    )
    if is_collab and not is_owner:
        builder.add(InlineKeyboardButton(text="🚪 Leave Collaborative Deck", callback_data=f"ask_leave_deck_{category}"))
    else:
        builder.add(InlineKeyboardButton(text="🗑️ Delete Deck", callback_data=f"ask_del_deck_{category}"))
    builder.add(InlineKeyboardButton(text="🔙 Back to Deck List", callback_data="quiz_cfg_list"))
    builder.adjust(1)
    return builder.as_markup()

def get_deck_preset_selection_keyboard(category: str):
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="🌐 Language Learning", callback_data="cfg_sel_preset:language"),
        InlineKeyboardButton(text="📚 Definitions & Concepts", callback_data="cfg_sel_preset:definitions"),
        InlineKeyboardButton(text="💻 Programming & Syntax", callback_data="cfg_sel_preset:programming"),
        InlineKeyboardButton(text="🧠 General Knowledge", callback_data="cfg_sel_preset:trivia"),
        InlineKeyboardButton(text="📚 General Flashcard", callback_data="cfg_sel_preset:general"),
        InlineKeyboardButton(text="✏️ Custom Prompt", callback_data="cfg_sel_preset:custom"),
        InlineKeyboardButton(text="🔙 Back to Deck Settings", callback_data=f"cfg_deck_{category}")
    )
    builder.adjust(1)
    return builder.as_markup()

def get_deck_source_language_keyboard(category: str):
    builder = InlineKeyboardBuilder()
    languages = [
        ("🇨🇿 Czech", "Czech"),
        ("🇪🇸 Spanish", "Spanish"),
        ("🇩🇪 German", "German"),
        ("🇬🇧 English", "English"),
        ("🇺🇦 Ukrainian", "Ukrainian"),
        ("🇫🇷 French", "French"),
        ("🇮🇹 Italian", "Italian"),
        ("🇵🇱 Polish", "Polish"),
    ]
    for text, code in languages:
        builder.add(InlineKeyboardButton(text=text, callback_data=f"cfg_lang_src:{code}"))
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="🔙 Back to Presets", callback_data=f"cfg_preset_{category}"))
    return builder.as_markup()

def get_deck_target_language_keyboard(category: str):
    builder = InlineKeyboardBuilder()
    languages = [
        ("🇬🇧 English", "English"),
        ("🇺🇦 Ukrainian", "Ukrainian"),
        ("🇨🇿 Czech", "Czech"),
        ("🇪🇸 Spanish", "Spanish"),
        ("🇩🇪 German", "German"),
        ("🇫🇷 French", "French"),
        ("🇵🇱 Polish", "Polish"),
        ("🇮🇹 Italian", "Italian"),
    ]
    for text, code in languages:
        builder.add(InlineKeyboardButton(text=text, callback_data=f"cfg_lang_tgt:{code}"))
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="🔙 Back to Source Language", callback_data="cfg_sel_preset:language"))
    return builder.as_markup()

def get_deck_custom_prompt_keyboard(category: str):
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="🔙 Cancel", callback_data=f"cfg_preset_{category}"))
    return builder.as_markup()

def get_deck_preset_saved_keyboard(category: str):
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="⚙️ Back to Deck Settings", callback_data=f"cfg_deck_{category}"),
        InlineKeyboardButton(text="🎯 Study Deck", callback_data=f"quiz_cat_{category}")
    )
    builder.adjust(1)
    return builder.as_markup()

def get_category_selection_reply_keyboard(categories: list):
    builder = ReplyKeyboardBuilder()
    
    cats_to_show = list(categories)
    if "General" not in cats_to_show:
        cats_to_show.insert(0, "General")
        
    for cat in cats_to_show:
        builder.add(KeyboardButton(text=cat))
        
    builder.adjust(2)
    builder.row(KeyboardButton(text="❌ Cancel"))
    
    return builder.as_markup(
        resize_keyboard=True,
        placeholder="Select existing deck or type new deck name..."
    )

def get_ai_topic_keyboard(has_saved_prompt: bool = False):
    buttons = []
    if has_saved_prompt:
        buttons.append([KeyboardButton(text="⚙️ Change Deck Prompt")])
    buttons.append([KeyboardButton(text="✍️ Manual Card")])
    buttons.append([KeyboardButton(text="❌ Cancel")])
    
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        placeholder="Enter topic, word, or phrase..."
    )

def get_list_categories_keyboard(categories: list):
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="🌐 All Decks", callback_data="list_cat_all"))
    for cat in categories:
        builder.add(InlineKeyboardButton(text=f"📁 {cat}", callback_data=f"list_cat_{cat}"))
    builder.adjust(1)
    return builder.as_markup()

def get_pagination_keyboard(category: str, current_page: int, total_pages: int):
    builder = InlineKeyboardBuilder()
    
    nav_buttons = []
    if current_page > 1:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"list_page|{category}|{current_page - 1}"))
    
    nav_buttons.append(InlineKeyboardButton(text=f"📄 {current_page}/{total_pages}", callback_data="noop"))
    
    if current_page < total_pages:
        nav_buttons.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"list_page|{category}|{current_page + 1}"))
        
    builder.row(*nav_buttons)
    if category != "all":
        builder.row(
            InlineKeyboardButton(text="🔗 Share Deck", callback_data=f"share_deck_{category}"),
            InlineKeyboardButton(text="🗑️ Delete Deck", callback_data=f"ask_del_deck_{category}")
        )
        builder.row(InlineKeyboardButton(text="🔙 Change Deck", callback_data="list_back_decks"))
    else:
        builder.row(InlineKeyboardButton(text="🔙 Change Deck", callback_data="list_back_decks"))
    
    return builder.as_markup()

def get_share_type_keyboard(category: str):
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="📋 Send a Copy (Snapshot)", callback_data=f"share_mode_copy_{category}"),
        InlineKeyboardButton(text="🤝 Collaborative Shared Deck", callback_data=f"share_mode_collab_{category}"),
        InlineKeyboardButton(text="🔙 Back", callback_data=f"list_cat_{category}")
    )
    builder.adjust(1)
    return builder.as_markup()

def get_share_link_keyboard(share_url: str, share_text: str, category: str):
    builder = InlineKeyboardBuilder()
    tg_share_url = f"https://t.me/share/url?url={urllib.parse.quote(share_url)}&text={urllib.parse.quote(share_text)}"
    builder.add(
        InlineKeyboardButton(text="↗️ Send to Friend on Telegram", url=tg_share_url),
        InlineKeyboardButton(text="🔙 Back to Deck", callback_data=f"list_cat_{category}")
    )
    builder.adjust(1)
    return builder.as_markup()

def get_share_invite_confirm_keyboard(share_token: str, share_type: str):
    builder = InlineKeyboardBuilder()
    if share_type == "collab":
        builder.add(InlineKeyboardButton(text="🤝 Join Collaborative Deck", callback_data=f"confirm_join_{share_token}"))
    else:
        builder.add(InlineKeyboardButton(text="📥 Import Deck Copy", callback_data=f"confirm_import_{share_token}"))
    builder.add(InlineKeyboardButton(text="❌ Decline", callback_data="decline_share_invite"))
    builder.adjust(1)
    return builder.as_markup()

def get_deck_leave_confirm_keyboard(category: str):
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="🚪 Yes, Leave Deck", callback_data=f"confirm_leave_deck_{category}"),
        InlineKeyboardButton(text="❌ Cancel", callback_data=f"cfg_deck_{category}")
    )
    builder.adjust(1)
    return builder.as_markup()

def get_deck_delete_confirm_keyboard(category: str):
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="⚠️ Yes, Delete Entire Deck", callback_data=f"confirm_del_deck_{category}"),
        InlineKeyboardButton(text="❌ Cancel", callback_data="list_back_decks")
    )
    builder.adjust(1)
    return builder.as_markup()

def get_duplicate_warning_keyboard():
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="▶️ Generate Anyway", callback_data="ai_dup_continue"),
        InlineKeyboardButton(text="❌ Cancel / Another Word", callback_data="ai_dup_cancel")
    )
    builder.adjust(1)
    return builder.as_markup()





