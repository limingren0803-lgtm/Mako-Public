import unittest
from pathlib import Path

from agents.agent_orchestrator import CAREER_MAX_TOKENS, AgentOrchestrator, AgentType
from core.intent_recognizer import IntentCategory, IntentRecognizer
from core.skill_loader import SkillManager


ROOT = Path(__file__).resolve().parents[1]


class CareerSkillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manager = SkillManager(ROOT / "skills", max_prompt_chars=18000)
        cls.manager.load()

    def test_only_canonical_skill_files_are_loaded(self):
        self.assertEqual(8, len(self.manager.skills))
        self.assertEqual([], self.manager.errors)
        self.assertFalse(any("backup" in skill.path.lower() for skill in self.manager.skills))

    def test_each_career_intent_loads_only_its_skill(self):
        expected = {
            "career_profile": "求职背景竞争力诊断",
            "career_match": "求职岗位方向匹配",
            "career_jd": "具体职位JD分析",
            "career_resume": "求职简历优化",
            "career_interview": "求职笔面试准备",
            "career_planning": "求职行动与能力补强规划",
        }
        for intent, skill_name in expected.items():
            with self.subTest(intent=intent):
                prompt = self.manager.prompt_for("测试请求", "career", intent=intent)
                self.assertIn(f"### {skill_name}", prompt)
                for other_name in set(expected.values()) - {skill_name}:
                    self.assertNotIn(f"### {other_name}", prompt)

    def test_all_career_skill_contracts_are_injected_completely(self):
        career_skills = [
            skill for skill in self.manager.skills
            if skill.intent and skill.intent.startswith("career_")
        ]
        self.assertEqual(6, len(career_skills))
        for skill in career_skills:
            with self.subTest(intent=skill.intent):
                prompt = self.manager.prompt_for("", "career", intent=skill.intent)
                last_rule = next(
                    line.strip()
                    for line in reversed(skill.content.splitlines())
                    if line.strip()
                )
                self.assertIn(last_rule, prompt)
                self.assertFalse(prompt.rstrip().endswith("..."))

    def test_unknown_career_intent_does_not_fall_back_to_keywords(self):
        prompt = self.manager.prompt_for(
            "根据这份JD和简历准备面试",
            "career",
            intent="career_unknown",
        )
        self.assertEqual("", prompt)

    def test_non_career_agents_keep_keyword_fallback(self):
        general_prompt = self.manager.prompt_for("请帮我整理信息", "general", intent="request")
        technical_prompt = self.manager.prompt_for("接口报错 500", "technical", intent="technical")
        self.assertIn("通用请求处理", general_prompt)
        self.assertIn("技术支持处理规范", technical_prompt)

    def test_every_career_skill_contains_a_non_fabrication_rule(self):
        career_skills = [skill for skill in self.manager.skills if skill.intent]
        for skill in career_skills:
            with self.subTest(intent=skill.intent):
                self.assertTrue(
                    "虚构" in skill.content or "编造" in skill.content,
                    f"{skill.intent} 缺少不虚构规则",
                )

    def test_career_output_budget_supports_full_v1_templates(self):
        self.assertGreaterEqual(CAREER_MAX_TOKENS, 4096)


class CareerIntentTests(unittest.TestCase):
    def setUp(self):
        self.recognizer = IntentRecognizer(
            api_key="test",
            base_url="https://example.invalid",
        )

    def test_domain_keywords_beat_generic_question_words(self):
        cases = {
            "简历怎么优化": IntentCategory.CAREER_RESUME,
            "这个岗位JD有什么要求": IntentCategory.CAREER_JD,
            "我适合哪些岗位": IntentCategory.CAREER_MATCH,
            "怎么分析我的求职竞争力": IntentCategory.CAREER_PROFILE,
            "面试怎么准备": IntentCategory.CAREER_INTERVIEW,
            "秋招怎么规划": IntentCategory.CAREER_PLANNING,
        }
        for message, expected in cases.items():
            with self.subTest(message=message):
                result = self.recognizer._pattern_recognize(message)
                self.assertEqual(expected, result["intent"])

    def test_cache_key_includes_recent_history(self):
        message = "这个呢？"
        resume_history = [{"role": "user", "content": "帮我看简历"}]
        jd_history = [{"role": "user", "content": "帮我分析JD"}]
        self.assertNotEqual(
            self.recognizer._cache_key(message, resume_history),
            self.recognizer._cache_key(message, jd_history),
        )

    def test_all_six_career_intents_route_to_career_agent(self):
        expected = {
            IntentCategory.CAREER_PROFILE,
            IntentCategory.CAREER_MATCH,
            IntentCategory.CAREER_JD,
            IntentCategory.CAREER_RESUME,
            IntentCategory.CAREER_INTERVIEW,
            IntentCategory.CAREER_PLANNING,
        }
        actual = {
            intent
            for intent, agent_type in AgentOrchestrator._INTENT_ROUTING.items()
            if agent_type == AgentType.CAREER
        }
        self.assertEqual(expected, actual)


if __name__ == "__main__":
    unittest.main()
