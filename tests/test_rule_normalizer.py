"""Unit tests for backend/services/rule_normalizer.py

Focus on the documented normalization rules (rule -> normalized_text).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.services.rule_normalizer import normalize_rule_text


class TestRuleNormalizer:
    def test_example_1_repeat_submit(self):
        rr = normalize_rule_text("重复提交-体验：禁用态")
        assert rr.normalized_text == "提交按钮重复点击 → 按钮禁用"

    def test_example_2_form_validate(self):
        rr = normalize_rule_text("结果正确性与性能体验 - 新增/编辑：表单校验")
        assert rr.normalized_text == "提交数据 → 触发表单校验"

    def test_example_3_button_edit_product_rule(self):
        rr = normalize_rule_text("按钮与元编辑（按产品要求）")
        # 按文档：按钮编辑 → 按规则执行（此处 action 可能来自“编辑/规则”线索）
        assert rr.normalized_text in ("按钮编辑 → 按规则执行", "按钮编辑")

    def test_length_limit_30(self):
        rr = normalize_rule_text("当用户在系统管理的用户管理页面进行新增时，必须提示并校验手机号不能为空且格式正确")
        assert len(rr.normalized_text) <= 30

    def test_confidence_range(self):
        rr = normalize_rule_text("提交：提示并校验")
        assert 0.0 <= rr.confidence <= 1.0

    def test_multi_action_split(self):
        rr = normalize_rule_text("重复提交并且提示")
        assert isinstance(rr.normalized_texts, list)
        assert len(rr.normalized_texts) >= 2
        assert all(isinstance(x, str) for x in rr.normalized_texts)

