"""Unit tests for the pure prompt/parse helpers in ollama_client.py.

Run: python3 -m unittest test_ollama_client -v
"""
import unittest

import ollama_client


class TestBuildContinuityPrompt(unittest.TestCase):
    def test_prompt_includes_all_three_texts(self):
        prompt = ollama_client.build_continuity_prompt(
            last_user="turn on the lights",
            last_assistant="done",
            new_user="what's the weather",
        )
        self.assertIn("turn on the lights", prompt)
        self.assertIn("done", prompt)
        self.assertIn("what's the weather", prompt)
        self.assertIn("SAME", prompt)
        self.assertIn("UNRELATED", prompt)


class TestParseContinuityResponse(unittest.TestCase):
    def test_same_is_true(self):
        self.assertTrue(ollama_client.parse_continuity_response("SAME"))

    def test_unrelated_is_false(self):
        self.assertFalse(ollama_client.parse_continuity_response("UNRELATED"))

    def test_lowercase_handled(self):
        self.assertFalse(ollama_client.parse_continuity_response("unrelated"))
        self.assertTrue(ollama_client.parse_continuity_response("same"))

    def test_extra_whitespace_and_words_handled(self):
        self.assertFalse(
            ollama_client.parse_continuity_response("  This is UNRELATED to the prior topic.\n")
        )

    def test_ambiguous_response_defaults_to_same(self):
        # No "UNRELATED" substring present -> defaults to same/append per
        # the plan's stated failure-mode rationale.
        self.assertTrue(ollama_client.parse_continuity_response("I'm not sure what you mean"))


if __name__ == "__main__":
    unittest.main()
