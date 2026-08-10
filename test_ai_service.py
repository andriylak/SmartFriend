import unittest
from ai_service import (
    clean_json_text,
    parse_card_json,
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

    def test_preset_prompts_exist(self):
        self.assertIn("language", PRESET_PROMPTS)
        self.assertIn("definitions", PRESET_PROMPTS)
        self.assertIn("programming", PRESET_PROMPTS)
        self.assertIn("trivia", PRESET_PROMPTS)
        self.assertIn("custom", PRESET_PROMPTS)

if __name__ == "__main__":
    unittest.main()
