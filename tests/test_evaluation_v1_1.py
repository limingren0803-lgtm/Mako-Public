import unittest
from collections import Counter
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from core.intent_recognizer import IntentCategory, IntentRecognizer
from evaluation.evaluator import DEFAULT_DIALOG_CASES, DEFAULT_INTENT_CASES, EndToEndEvaluator, LLMJudge


CAREER_INTENTS = {
    "career_profile",
    "career_match",
    "career_jd",
    "career_resume",
    "career_interview",
    "career_planning",
}


class EvaluationDatasetTests(unittest.TestCase):
    def test_each_career_intent_has_at_least_three_default_cases(self):
        counts = Counter(case.expected_intent for case in DEFAULT_INTENT_CASES)
        for intent in CAREER_INTENTS:
            with self.subTest(intent=intent):
                self.assertGreaterEqual(counts[intent], 3)

    def test_default_intent_cases_have_unique_messages(self):
        messages = [case.message for case in DEFAULT_INTENT_CASES]
        self.assertEqual(len(messages), len(set(messages)))

    def test_default_career_cases_have_deterministic_keyword_routes(self):
        recognizer = IntentRecognizer(
            api_key="test",
            base_url="https://example.invalid",
        )
        for case in DEFAULT_INTENT_CASES:
            if case.expected_intent not in CAREER_INTENTS:
                continue
            with self.subTest(message=case.message):
                result = recognizer._pattern_recognize(case.message)
                self.assertEqual(IntentCategory(case.expected_intent), result["intent"])

    def test_dialog_dataset_contains_single_and_multi_turn_cases(self):
        self.assertTrue(any("question" in case for case in DEFAULT_DIALOG_CASES))
        self.assertTrue(any(len(case.get("turns", [])) >= 3 for case in DEFAULT_DIALOG_CASES))
        self.assertGreaterEqual(len(DEFAULT_DIALOG_CASES), 10)

    def test_dialog_turn_normalization_drops_blank_turns(self):
        turns = EndToEndEvaluator._dialog_turns(
            {"turns": ["第一轮", "", "  ", "第二轮"]}
        )
        self.assertEqual(["第一轮", "第二轮"], turns)

    def test_history_context_is_bounded_to_eight_messages(self):
        history = [
            {"role": "user", "content": f"message-{index}"}
            for index in range(10)
        ]

        context = EndToEndEvaluator._history_context(history)

        self.assertNotIn("message-0", context)
        self.assertNotIn("message-1", context)
        self.assertIn("message-2", context)
        self.assertIn("message-9", context)


class JudgeScoreBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_scores_fail_instead_of_polluting_evaluation(self):
        judge = LLMJudge(object(), "test-model")
        valid = '{"relevance": 1, "accuracy": 0, "completeness": 0.8, "helpfulness": 0.9}'
        invalid = (
            valid.replace('"relevance": 1', '"relevance": 9'),
            valid.replace('"relevance": 1', '"relevance": -1'),
            valid.replace('"relevance": 1', '"relevance": NaN'),
            valid.replace('"relevance": 1', '"relevance": "0.9"'),
            valid.replace('"relevance": 1', '"relevance": true'),
            valid.replace('"relevance": 1, ', ''),
        )
        with patch("evaluation.evaluator.create_message", new_callable=AsyncMock) as create:
            create.return_value = SimpleNamespace(content=[SimpleNamespace(type="text", text=valid)])
            self.assertFalse((await judge.judge("问题", "回答")).judge_failed)
            for raw in invalid:
                with self.subTest(raw=raw):
                    create.return_value = SimpleNamespace(content=[SimpleNamespace(type="text", text=raw)])
                    self.assertTrue((await judge.judge("问题", "回答")).judge_failed)


if __name__ == "__main__":
    unittest.main()
