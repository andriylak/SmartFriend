import unittest
from ai_service import (
    clean_json_text,
    parse_card_json,
    format_comment,
    PRESET_PROMPTS
)

class TestAIService(unittest.TestCase):
    def test_clean_json_text_with_codeblock(self):
        raw = """Here is your card:
```json
{
  "question": "Hola",
  "answer": "Hello (Spanish)"
}
```
Hope that helps!"""
        cleaned = clean_json_text(raw)
        self.assertEqual(cleaned, '{\n  "question": "Hola",\n  "answer": "Hello (Spanish)"\n}')

    def test_format_comment(self):
        comment_raw = "Pronunciation: /koˈmiða/\nPart of Speech: Noun\nExample Sentence: La comida está rica."
        formatted_html = format_comment(comment_raw, fmt="html")
        self.assertIn("• <b>Pronunciation:</b> /koˈmiða/", formatted_html)
        self.assertIn("• <b>Part of Speech:</b> Noun", formatted_html)
        self.assertIn("• <b>Example Sentence:</b> La comida está rica.", formatted_html)
        
        formatted_md = format_comment(comment_raw, fmt="markdown")
        self.assertIn("• **Pronunciation:** /koˈmiða/", formatted_md)
        self.assertIn("• **Part of Speech:** Noun", formatted_md)

    def test_format_comment_with_subitems_and_blank_lines(self):
        comment_raw = (
            "Usage Frequency & Register: Formal\n\n"
            "1. First definition\n"
            "   Example: Sample sentence\n"
            "   Translation: Переклад речення"
        )
        formatted_html = format_comment(comment_raw, fmt="html")
        self.assertIn("• <b>Usage Frequency &amp; Register:</b> Formal\n\n1. First definition", formatted_html)
        self.assertIn("   • <b>Example:</b> Sample sentence", formatted_html)
        self.assertIn("   • <b>Translation:</b> Переклад речення", formatted_html)

    def test_parse_card_json_valid(self):
        raw = '{"question": "What is Python?", "answer": "A programming language."}'
        parsed = parse_card_json(raw)
        self.assertEqual(parsed["question"], "What is Python?")
        self.assertEqual(parsed["answer"], "A programming language.")

    def test_parse_card_json_with_markdown(self):
        raw = '```json\n{"question": "French for Apple", "answer": "la pomme"}\n```'
        parsed = parse_card_json(raw)
        self.assertEqual(parsed["question"], "French for Apple")
        self.assertEqual(parsed["answer"], "la pomme")

    def test_parse_card_json_fallback(self):
        raw = "Question: What is 2 + 2?\nAnswer: 4"
        parsed = parse_card_json(raw)
        self.assertEqual(parsed["question"], "What is 2 + 2?")
        self.assertEqual(parsed["answer"], "4")

    def test_parse_card_json_with_correction_note(self):
        raw = '{"question": "comida", "answer": "Food", "correction_note": "Auto-corrected typo comidaa ➔ comida"}'
        parsed = parse_card_json(raw)
        self.assertEqual(parsed["question"], "comida")
        self.assertEqual(parsed["answer"], "Food")
        self.assertEqual(parsed["correction_note"], "Auto-corrected typo comidaa ➔ comida")

    def test_preset_prompts_exist(self):
        self.assertIn("language", PRESET_PROMPTS)
        self.assertIn("definitions", PRESET_PROMPTS)
        self.assertIn("programming", PRESET_PROMPTS)
        self.assertIn("trivia", PRESET_PROMPTS)
        self.assertIn("custom", PRESET_PROMPTS)

    def test_language_preset_prompt_formatting(self):
        instruction = PRESET_PROMPTS["language"]["system_instruction"].format(
            topic="el gato",
            source_language="Spanish",
            target_language="Ukrainian"
        )
        self.assertIn("el gato", instruction)
        self.assertIn("Spanish", instruction)
        self.assertIn("Ukrainian", instruction)
        self.assertNotIn("Pronunciation", instruction)
        self.assertNotIn("Part of Speech", instruction)
        self.assertIn("Usage Frequency", instruction)
        self.assertIn("Dialect", instruction)
        self.assertIn("Explanation", instruction)
        self.assertIn("Meanings & Examples", instruction)

    def test_model_config(self):
        import config
        self.assertTrue(hasattr(config, "MODEL_NAME"))
        self.assertTrue(hasattr(config, "FALLBACK_MODEL_NAME"))
        self.assertTrue(hasattr(config, "FALLBACK_MODELS"))
        self.assertIn(config.FALLBACK_MODEL_NAME, config.FALLBACK_MODELS)

    def test_parse_card_json_truncated(self):
        raw = '{\n  "question": "tucet",\n  "answer": "a dozen",'
        parsed = parse_card_json(raw)
        self.assertEqual(parsed["question"], "tucet")
        self.assertEqual(parsed["answer"], "a dozen")

if __name__ == "__main__":
    unittest.main()


