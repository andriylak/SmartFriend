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
        self.assertTrue(hasattr(config, "GEMINI_MAX_RETRIES"))
        self.assertEqual(config.GEMINI_MAX_RETRIES, 5)

    def test_parse_card_json_truncated(self):
        raw = '{\n  "question": "tucet",\n  "answer": "a dozen",'
        parsed = parse_card_json(raw)
        self.assertEqual(parsed["question"], "tucet")
        self.assertEqual(parsed["answer"], "a dozen")

    def test_generate_ai_card_retries_on_503_and_succeeds(self):
        import asyncio
        from unittest.mock import patch, AsyncMock, MagicMock
        from ai_service import generate_ai_card

        # Mock responses: 4 overloads (503), then 1 success (200)
        overload_resp = AsyncMock()
        overload_resp.status = 503
        overload_resp.text = AsyncMock(return_value='{"error": {"code": 503, "message": "The model is overloaded. Please try again later."}}')

        success_resp = AsyncMock()
        success_resp.status = 200
        success_resp.json = AsyncMock(return_value={
            "candidates": [{
                "content": {
                    "parts": [{"text": '{"question": "sol", "answer": "sun", "comment": "Spanish noun"}'}]
                }
            }]
        })

        # Responses sequence: 4 fails, then success
        resp_sequence = [overload_resp, overload_resp, overload_resp, overload_resp, success_resp]

        class MockPostContext:
            def __init__(self, resp):
                self.resp = resp
            async def __aenter__(self):
                return self.resp
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None

        call_idx = 0
        def mock_post(*args, **kwargs):
            nonlocal call_idx
            idx = min(call_idx, len(resp_sequence) - 1)
            call_idx += 1
            return MockPostContext(resp_sequence[idx])

        mock_session_instance = MagicMock()
        mock_session_instance.post = MagicMock(side_effect=mock_post)

        class MockSessionContext:
            async def __aenter__(self):
                return mock_session_instance
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None

        async def run_test():
            with patch("config.GEMINI_API_KEY", "fake_key"), \
                 patch("config.FALLBACK_MODELS", []), \
                 patch("aiohttp.ClientSession", return_value=MockSessionContext()), \
                 patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:

                card = await generate_ai_card(preset_key="language", topic="sol", max_retries=5)
                self.assertEqual(card["question"], "sol")
                self.assertEqual(card["answer"], "sun")
                # Should have slept 4 times before the 5th attempt succeeded
                self.assertEqual(mock_sleep.call_count, 4)

        asyncio.run(run_test())

    def test_generate_ai_card_exhausts_all_retries_and_raises(self):
        import asyncio
        from unittest.mock import patch, AsyncMock, MagicMock
        from ai_service import generate_ai_card

        overload_resp = AsyncMock()
        overload_resp.status = 503
        overload_resp.text = AsyncMock(return_value='{"error": {"code": 503, "message": "The model is overloaded. Please try again later."}}')

        class MockPostContext:
            async def __aenter__(self):
                return overload_resp
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None

        mock_session_instance = MagicMock()
        mock_session_instance.post = MagicMock(return_value=MockPostContext())

        class MockSessionContext:
            async def __aenter__(self):
                return mock_session_instance
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None

        async def run_test():
            with patch("config.GEMINI_API_KEY", "fake_key"), \
                 patch("config.FALLBACK_MODELS", []), \
                 patch("aiohttp.ClientSession", return_value=MockSessionContext()), \
                 patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:

                with self.assertRaises(RuntimeError) as ctx:
                    await generate_ai_card(preset_key="language", topic="sol", max_retries=5)

                self.assertIn("failed after 5 attempts", str(ctx.exception))
                self.assertIn("The model is overloaded", str(ctx.exception))
                # 5 attempts -> 4 retries/sleeps
                self.assertEqual(mock_sleep.call_count, 4)

        asyncio.run(run_test())

if __name__ == "__main__":
    unittest.main()


