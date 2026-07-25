#!/usr/bin/env python3
"""画像对话引擎（spec 阶段 D2）：解析协议 / 归一化 / 轮次硬顶 / prompt 构造"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from analyzer.profile_interview import (
    MAX_INTERVIEW_ROUNDS,
    build_interview_system_prompt,
    normalize_career_profile,
    parse_interview_reply,
    should_force_finish,
)

SCHEMA_KEYS = ("target_directions", "transition", "cities", "salary_floor",
               "hard_avoids", "seniority", "notes")


class TestParseInterviewReply:
    def test_ask_action(self):
        out = parse_interview_reply(
            '{"action": "ask", "message": "你想转型吗？"}')
        assert out["action"] == "ask"
        assert out["message"] == "你想转型吗？"

    def test_finish_action_with_profile(self):
        raw = json.dumps({"action": "finish", "message": "画像完成",
                          "profile": {"target_directions": ["风控"]}},
                         ensure_ascii=False)
        out = parse_interview_reply(raw)
        assert out["action"] == "finish"
        assert out["profile"]["target_directions"] == ["风控"]

    def test_json_fence_tolerated(self):
        out = parse_interview_reply(
            '```json\n{"action": "ask", "message": "问题"}\n```')
        assert out["action"] == "ask"

    def test_malformed_degrades_to_ask_with_original_text(self):
        out = parse_interview_reply("这不是 JSON，只是普通追问文本")
        assert out["action"] == "ask"
        assert "普通追问文本" in out["message"]
        assert out.get("profile") is None

    def test_invalid_action_degrades(self):
        out = parse_interview_reply('{"action": "自造动作", "message": "x"}')
        assert out["action"] == "ask"


class TestNormalizeCareerProfile:
    def test_missing_keys_defaulted(self):
        out = normalize_career_profile({})
        for key in SCHEMA_KEYS:
            assert key in out
        assert out["target_directions"] == []
        assert out["hard_avoids"] == []
        assert out["transition"] is None

    def test_directions_trimmed_to_three(self):
        out = normalize_career_profile(
            {"target_directions": ["a", "b", "c", "d", "e"]})
        assert len(out["target_directions"]) == 3

    def test_non_list_fields_coerced(self):
        out = normalize_career_profile(
            {"target_directions": "风控", "hard_avoids": None})
        assert isinstance(out["target_directions"], list)
        assert out["hard_avoids"] == []

    def test_transition_structure_validated(self):
        out = normalize_career_profile(
            {"transition": {"is_transition": True, "from": "券商", "to": "买方"}})
        assert out["transition"]["is_transition"] is True
        # 结构不完整 → 置 None
        out2 = normalize_career_profile({"transition": "想转型"})
        assert out2["transition"] is None


class TestForceFinish:
    def _msgs(self, assistant_rounds):
        msgs = []
        for _ in range(assistant_rounds):
            msgs.append({"role": "assistant", "content": "问"})
            msgs.append({"role": "user", "content": "答"})
        return msgs

    def test_below_limit_false(self):
        assert should_force_finish(self._msgs(MAX_INTERVIEW_ROUNDS - 1)) is False

    def test_at_limit_true(self):
        assert should_force_finish(self._msgs(MAX_INTERVIEW_ROUNDS)) is True


class TestSystemPrompt:
    def test_contains_resume_and_schema(self):
        prompt = build_interview_system_prompt("这是一份市场风险管理简历全文")
        assert "市场风险管理简历全文" in prompt
        for key in SCHEMA_KEYS:
            assert key in prompt, f"system prompt 缺 schema 键 {key}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
