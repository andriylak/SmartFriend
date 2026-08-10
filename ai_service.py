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
            "Topic / Prompt: {topic}\n"
            "Format requirements:\n"
            "Return ONLY a JSON object with keys 'question' and 'answer'.\n"
            "'question': The word, phrase, or sentence in the target language (or translation request).\n"
            "'answer': The translation, pronunciation/phonetics (if relevant), and a clear example sentence with translation."
        )
    },
    "definitions": {
        "title": "📚 Definitions & Concepts",
        "system_instruction": (
            "You are an educational assistant specializing in study cards.\n"
            "Topic / Prompt: {topic}\n"
            "Format requirements:\n"
            "Return ONLY a JSON object with keys 'question' and 'answer'.\n"
            "'question': A clear, direct question asking for the definition, formula, or core concept.\n"
            "'answer': A concise, accurate definition and brief explanation."
        )
    },
    "programming": {
        "title": "💻 Programming & Syntax",
        "system_instruction": (
            "You are a computer science tutor.\n"
            "Topic / Prompt: {topic}\n"
            "Format requirements:\n"
            "Return ONLY a JSON object with keys 'question' and 'answer'.\n"
            "'question': A coding question, syntax problem, or code output prediction.\n"
            "'answer': The concise solution code block and explanation."
        )
    },
    "trivia": {
        "title": "🧠 General Knowledge & Trivia",
        "system_instruction": (
            "You are a trivia and facts expert.\n"
            "Topic / Prompt: {topic}\n"
            "Format requirements:\n"
            "Return ONLY a JSON object with keys 'question' and 'answer'.\n"
            "'question': An engaging trivia or historical fact question.\n"
            "'answer': The correct answer along with a fascinating context detail."
        )
    },
    "custom": {
        "title": "✏️ Custom Prompt",
        "system_instruction": (
            "User Custom Instructions: {custom_prompt}\n"
            "Topic / Context: {topic}\n"
            "Format requirements:\n"
            "Return ONLY a JSON object with keys 'question' and 'answer'.\n"
            "'question': Front side of the flashcard based on instructions.\n"
            "'answer': Back side of the flashcard based on instructions."
        )
    }
}

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

def parse_card_json(raw_text: str) -> Dict[str, str]:
    """Parse raw text into a valid dict with question and answer keys."""
    cleaned = clean_json_text(raw_text)
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict) and "question" in data and "answer" in data:
            return {
                "question": str(data["question"]).strip(),
                "answer": str(data["answer"]).strip()
            }
    except Exception as e:
        logger.warning(f"Failed to parse JSON directly: {e}, raw text: {raw_text}")

    # Fallback heuristic splitting if JSON parsing fails
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    question = "Generated Question"
    answer = raw_text

    for line in lines:
        if line.lower().startswith("question:") or line.lower().startswith("q:"):
            question = line.split(":", 1)[1].strip()
        elif line.lower().startswith("answer:") or line.lower().startswith("a:"):
            answer = line.split(":", 1)[1].strip()

    return {"question": question, "answer": answer}

async def generate_ai_card(
    preset_key: str,
    topic: str,
    custom_prompt: Optional[str] = None
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
    
    if preset_key == "custom" and custom_prompt:
        instruction = preset_info["system_instruction"].format(
            custom_prompt=custom_prompt,
            topic=topic
        )
    else:
        instruction = preset_info["system_instruction"].format(
            topic=topic
        )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.MODEL_NAME}:generateContent?key={api_key}"
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

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            if resp.status != 200:
                fallback_url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.FALLBACK_MODEL_NAME}:generateContent?key={api_key}"
                async with session.post(fallback_url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as fallback_resp:
                    if fallback_resp.status != 200:
                        error_text = await fallback_resp.text()
                        raise RuntimeError(f"Gemini API returned status {fallback_resp.status}: {error_text}")
                    data = await fallback_resp.json()
            else:
                data = await resp.json()

    try:
        candidate_text = data["candidates"][0]["content"]["parts"][0]["text"]
        return parse_card_json(candidate_text)
    except (KeyError, IndexError) as err:
        logger.error(f"Invalid API response format: {data}")
        raise RuntimeError("AI model returned an empty or invalid response format.") from err
