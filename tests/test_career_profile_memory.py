import json
import unittest
from datetime import datetime

from api.main import _should_update_career_profile
from core.career_profile import CareerProfile
from memory.conversation_memory import MemoryContext, MemoryManager, Message, MsgRole
from pydantic import ValidationError


class CareerProfileTriggerTests(unittest.TestCase):
    def test_trivial_messages_do_not_trigger_profile_updates(self):
        for message in ("", "谢谢", "好的", "继续", "OK", "thank you"):
            with self.subTest(message=message):
                self.assertFalse(_should_update_career_profile(message))

    def test_explicit_career_information_triggers_profile_updates(self):
        messages = (
            "我本科读的是市场营销",
            "我有一段产品运营实习",
            "我会 SQL 和 Python",
            "我的目标岗位是产品经理",
            "我想在上海工作",
            "我不能接受长期出差",
        )
        for message in messages:
            with self.subTest(message=message):
                self.assertTrue(_should_update_career_profile(message))


class CareerProfileSchemaTests(unittest.TestCase):
    def test_city_alias_is_serialized_as_location(self):
        profile = CareerProfile.model_validate(
            {"location_preferences": [{"city": "上海", "status": "confirmed"}]}
        )

        dumped = profile.model_dump(mode="json", by_alias=True)

        self.assertEqual("上海", dumped["location_preferences"][0]["location"])
        self.assertNotIn("city", dumped["location_preferences"][0])

    def test_invalid_skill_record_is_rejected(self):
        with self.assertRaises(ValidationError):
            CareerProfile.model_validate({"skills": [{"evidence": ["项目经历"]}]})


class ConservativeProfileMergeTests(unittest.TestCase):
    def test_empty_incoming_profile_preserves_existing_data(self):
        existing = {
            "skills": [{"name": "SQL", "evidence": ["课程项目"]}],
            "target_roles": [{"role": "产品运营", "status": "confirmed"}],
            "last_updated": "2026-08-01T10:00:00",
        }

        merged = MemoryManager._merge_career_profile(existing, {})

        self.assertEqual("SQL", merged["skills"][0]["name"])
        self.assertEqual("产品运营", merged["target_roles"][0]["role"])
        self.assertEqual("2026-08-01T10:00:00", merged["last_updated"])

    def test_new_list_items_are_appended_without_removing_existing_items(self):
        existing = {
            "skills": [{"name": "SQL", "evidence": ["课程项目"]}],
            "questions_to_confirm": ["确认可入职时间"],
        }
        incoming = {
            "skills": [{"name": "Python", "evidence": ["数据分析项目"]}],
            "questions_to_confirm": ["确认期望城市"],
        }

        merged = MemoryManager._merge_career_profile(existing, incoming)

        self.assertEqual(["SQL", "Python"], [item["name"] for item in merged["skills"]])
        self.assertEqual(
            ["确认可入职时间", "确认期望城市"],
            merged["questions_to_confirm"],
        )

    def test_identical_list_items_are_not_duplicated(self):
        skill = {"name": "SQL", "evidence": ["课程项目"]}

        merged = MemoryManager._merge_career_profile(
            {"skills": [skill]},
            {"skills": [skill]},
        )

        self.assertEqual(1, len(merged["skills"]))

    def test_confirmed_location_status_is_not_downgraded(self):
        existing = {
            "location_preferences": [
                {
                    "location": "上海",
                    "level": "strong_preference",
                    "status": "confirmed",
                }
            ]
        }
        incoming = {
            "location_preferences": [
                {"city": "上海", "level": "hard_constraint", "status": "unconfirmed"}
            ]
        }

        merged = MemoryManager._merge_career_profile(existing, incoming)
        location = merged["location_preferences"][0]

        self.assertEqual("上海", location["location"])
        self.assertEqual("confirmed", location["status"])
        self.assertEqual("hard_constraint", location["level"])
        self.assertNotIn("city", location)

    def test_valid_incoming_scalar_replaces_existing_scalar(self):
        merged = MemoryManager._merge_career_profile(
            {"last_updated": "2026-08-01T10:00:00"},
            {"last_updated": "2026-08-10T10:00:00"},
        )

        self.assertEqual("2026-08-10T10:00:00", merged["last_updated"])


class MemoryCompatibilityTests(unittest.TestCase):
    def test_redis_key_namespaces_remain_compatible(self):
        self.assertEqual("wm:user-1:conv-1", MemoryManager._wm_key("user-1", "conv-1"))
        self.assertEqual(
            "summary:user-1:conv-1",
            MemoryManager._summary_key("user-1", "conv-1"),
        )

    def test_prompt_context_keeps_section_order_and_cleans_surrogates(self):
        context = MemoryContext(
            summary="已确认目标岗位\ud800",
            relevant_history=["上一轮讨论了简历"],
            user_profile={"career_profile": {"skills": [{"name": "SQL"}]}},
            recent_messages=[
                Message(
                    role=MsgRole.USER,
                    content="我想投产品运营",
                    timestamp=datetime(2026, 8, 10, 9, 0, 0),
                )
            ],
        )

        prompt = context.to_prompt_text()

        headings = ["[会话摘要]", "[相关历史]", "[用户画像]", "[最近对话]"]
        positions = [prompt.index(heading) for heading in headings]
        self.assertEqual(sorted(positions), positions)
        self.assertNotIn("\ud800", prompt)
        self.assertIn("user: 我想投产品运营", prompt)


class _FakeProfileCollection:
    def get(self, **kwargs):
        return {
            "documents": [
                json.dumps({"version": "old"}),
                json.dumps({"version": "new"}),
            ],
            "metadatas": [
                {"ts": "2026-08-01T10:00:00"},
                {"ts": "2026-08-10T10:00:00"},
            ],
        }


class ProfileStorageSelectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_latest_profile_is_selected_by_timestamp(self):
        manager = object.__new__(MemoryManager)
        manager._profile = _FakeProfileCollection()

        profile = await manager._get_profile("user-1")

        self.assertEqual({"version": "new"}, profile)


if __name__ == "__main__":
    unittest.main()
