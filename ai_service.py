import json
import re
import os
import logging
import aiohttp
from typing import Dict, Optional

import config

logger = logging.getLogger(__name__)

# Preset Prompt Descriptions
PRESET_PROMPTS = {
    "language": {
        "title": "🌐 Language Learning",
        "system_instruction": (
            "You are an expert language tutor. Create a high-quality flashcard for learning vocabulary, phrases, or grammar.\n"
            "Source / Learning Language (Translate FROM): {source_language}\n"
            "Target Translation Language (Translate TO): {target_language}\n"
            "User Input / Topic / Word / Phrase: {topic}\n\n"
            "Instructions & Typo Handling:\n"
            "1. Check if '{topic}' has any typos, misspellings, or non-standard forms in {source_language}.\n"
            "2. If there IS a typo or misspelling, normalize and fix it for the card's 'question', 'answer', and 'comment', and specify what was corrected in 'correction_note' (e.g. 'Auto-corrected typo \"comidaa\" ➔ \"comida\"'). If there is no typo, set 'correction_note' to null.\n"
            "3. STRICT RULE: Do NOT include meta-notes, disclaimers, or typo warnings inside 'question', 'answer', or 'comment' (e.g., NO '⚠️ Correction:' or 'Note: did you mean...'). They must contain ONLY pure study content.\n\n"
            "Format requirements:\n"
            "Return ONLY a JSON object with 3 primary keys: 'question', 'answer', 'comment', and optional 'correction_note':\n"
            "- 'question': The clean word, phrase, or sentence in {source_language} (e.g. 'el gato').\n"
            "- 'answer': The direct, clean translation in {target_language} ONLY (e.g. 'the cat'). Keep this concise and free of examples or extra info.\n"
            "- 'comment': All additional linguistic details & context, formatted clearly:\n"
            "  • Pronunciation / Phonetics (IPA or phonetic spelling)\n"
            "  • Part of Speech (e.g., Noun, Transitive Verb, Adjective, Idiom)\n"
            "  • Usage Frequency & Register (e.g., Common / Everyday, Formal, Colloquial, Slang)\n"
            "  • Dialect / Regional Variation (e.g., Universal, Spain, Latin America)\n"
            "  • Example Sentence (in {source_language} with translation in {target_language})\n"
            "- 'correction_note': Short explanation of typo correction if any, otherwise null."
        )
    },
    "definitions": {
        "title": "📚 Definitions & Concepts",
        "system_instruction": (
            "You are an educational assistant specializing in study cards.\n"
            "Topic / Prompt: {topic}\n"
            "Format requirements:\n"
            "Return ONLY a JSON object with keys 'question', 'answer', and optional 'comment'.\n"
            "'question': A clear, direct question asking for the definition, formula, or core concept.\n"
            "'answer': A concise, accurate definition.\n"
            "'comment': Additional explanation or context."
        )
    },
    "programming": {
        "title": "💻 Programming & Syntax",
        "system_instruction": (
            "You are a computer science tutor.\n"
            "Topic / Prompt: {topic}\n"
            "Format requirements:\n"
            "Return ONLY a JSON object with keys 'question', 'answer', and optional 'comment'.\n"
            "'question': A coding question, syntax problem, or code output prediction.\n"
            "'answer': The concise solution code block.\n"
            "'comment': Explanation of the solution."
        )
    },
    "trivia": {
        "title": "🧠 General Knowledge & Trivia",
        "system_instruction": (
            "You are a trivia and facts expert.\n"
            "Topic / Prompt: {topic}\n"
            "Format requirements:\n"
            "Return ONLY a JSON object with keys 'question', 'answer', and optional 'comment'.\n"
            "'question': An engaging trivia or historical fact question.\n"
            "'answer': The correct concise answer.\n"
            "'comment': A fascinating context detail or history background."
        )
    },
    "custom": {
        "title": "✏️ Custom Prompt",
        "system_instruction": (
            "User Custom Instructions: {custom_prompt}\n"
            "Topic / Context: {topic}\n"
            "Format requirements:\n"
            "Return ONLY a JSON object with keys 'question', 'answer', and optional 'comment'.\n"
            "'question': Front side of the flashcard based on instructions.\n"
            "'answer': Back side of the flashcard based on instructions.\n"
            "'comment': Additional notes or comments if applicable."
        )
    }
}

def get_full_prompt_text(preset_key: str, source_language: Optional[str] = None, target_language: Optional[str] = None, custom_prompt: Optional[str] = None) -> str:
    """Returns the full AI system instruction prompt template string."""
    preset_info = PRESET_PROMPTS.get(preset_key, PRESET_PROMPTS["custom"])
    source_lang = source_language or "Spanish"
    target_lang = target_language or "English"
    
    if preset_key == "custom" and custom_prompt:
        return preset_info["system_instruction"].format(
            custom_prompt=custom_prompt,
            topic="[Your Word/Topic]"
        )
    elif preset_key == "language":
        return preset_info["system_instruction"].format(
            topic="[Your Word/Topic]",
            source_language=source_lang,
            target_language=target_lang
        )
    else:
        return preset_info["system_instruction"].format(
            topic="[Your Word/Topic]"
        )

def clean_json_text(text: str) -> str:
    """Extract raw JSON text from markdown code blocks or surrounding text."""
    text = text.strip()
    # Match json code block ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    
    # Match JSON object starting with { and ending with }
    match_object = re.search(r"(\{.*\})", text, re.DOTALL)
    if match_object:
        return match_object.group(1).strip()
        
    return text

def parse_card_json(raw_text: str) -> Dict[str, Optional[str]]:
    """Parse raw text into a valid dict with question, answer, comment, and optional correction_note keys."""
    cleaned = clean_json_text(raw_text)
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict) and "question" in data and "answer" in data:
            return {
                "question": str(data["question"]).strip(),
                "answer": str(data["answer"]).strip(),
                "comment": str(data["comment"]).strip() if data.get("comment") else "",
                "correction_note": str(data["correction_note"]).strip() if data.get("correction_note") else None
            }
    except Exception as e:
        logger.warning(f"Failed to parse JSON directly: {e}, raw text: {raw_text}")

    # Regex extraction fallback for truncated or partially formatted JSON
    q_match = re.search(r'"question"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', raw_text)
    a_match = re.search(r'"answer"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', raw_text)
    c_match = re.search(r'"comment"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', raw_text)
    n_match = re.search(r'"correction_note"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', raw_text)

    if q_match and a_match:
        return {
            "question": q_match.group(1).strip(),
            "answer": a_match.group(1).strip(),
            "comment": c_match.group(1).strip() if c_match else "",
            "correction_note": n_match.group(1).strip() if n_match else None
        }

    # Fallback heuristic splitting if JSON parsing fails
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    question = "Generated Question"
    answer = raw_text

    for line in lines:
        if line.lower().startswith("question:") or line.lower().startswith("q:"):
            question = line.split(":", 1)[1].strip()
        elif line.lower().startswith("answer:") or line.lower().startswith("a:"):
            answer = line.split(":", 1)[1].strip()

    return {"question": question, "answer": answer, "comment": "", "correction_note": None}

async def generate_ai_card(
    preset_key: str,
    topic: str,
    custom_prompt: Optional[str] = None,
    source_language: Optional[str] = None,
    target_language: Optional[str] = None
) -> Dict[str, str]:
    """
    Calls Google Gemini API to generate a flashcard question and answer.
    Returns a dict with {"question": "...", "answer": "..."}.
    """
    api_key = config.GEMINI_API_KEY
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY is not configured in your environment or .env file.\n"
            "Please add `GEMINI_API_KEY=your_key_here` to your .env file to enable AI assistance."
        )

    preset_info = PRESET_PROMPTS.get(preset_key, PRESET_PROMPTS["custom"])
    source_lang = source_language or "Spanish"
    target_lang = target_language or "English"
    
    if preset_key == "custom" and custom_prompt:
        instruction = preset_info["system_instruction"].format(
            custom_prompt=custom_prompt,
            topic=topic
        )
    elif preset_key == "language":
        instruction = preset_info["system_instruction"].format(
            topic=topic,
            source_language=source_lang,
            target_language=target_lang
        )
    else:
        instruction = preset_info["system_instruction"].format(
            topic=topic
        )

    # Build ordered list of models to try starting with primary MODEL_NAME, followed by FALLBACK_MODELS
    fallback_list = getattr(config, "FALLBACK_MODELS", [getattr(config, "FALLBACK_MODEL_NAME", "gemini-3.1-flash-lite")])
    models_to_try = [config.MODEL_NAME]
    for model in fallback_list:
        if model not in models_to_try:
            models_to_try.append(model)

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": instruction}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "responseMimeType": "application/json"
        }
    }


    headers = {"Content-Type": "application/json"}
    last_error_msg = ""

    async with aiohttp.ClientSession() as session:
        for model in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            try:
                async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        try:
                            candidate_text = data["candidates"][0]["content"]["parts"][0]["text"]
                            logger.info(f"Successfully generated AI card using model '{model}'")
                            return parse_card_json(candidate_text)
                        except (KeyError, IndexError) as err:
                            logger.error(f"Invalid API response format from model '{model}': {data}")
                            last_error_msg = f"Model '{model}' returned invalid response format"
                    else:
                        error_text = await resp.text()
                        logger.warning(f"Model '{model}' request failed with status {resp.status}: {error_text[:200]}")
                        last_error_msg = f"Model '{model}' status {resp.status}: {error_text[:200]}"
            except Exception as e:
                logger.warning(f"Network/API error with model '{model}': {e}")
                last_error_msg = f"Model '{model}' error: {e}"

    raise RuntimeError(f"All Gemini API models failed. Last error: {last_error_msg}")

