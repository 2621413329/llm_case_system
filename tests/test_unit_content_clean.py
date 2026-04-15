"""Tests for backend/services/unit_content_clean.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.services.unit_content_clean import (
    filter_units_and_edges,
    is_id_like,
    is_low_information_structured_content,
    is_noise,
    normalize_unit_content,
)


class TestIsNoise:
    def test_empty(self):
        assert is_noise("") is True
        assert is_noise("   ") is True

    def test_repeated_char(self):
        assert is_noise("aaaa") is True

    def test_only_punct(self):
        assert is_noise("!!!") is True
        assert is_noise("---") is True

    def test_meaningful(self):
        assert is_noise("订单管理") is False
        assert is_noise("submit form") is False


class TestIsIdLike:
    def test_digits(self):
        assert is_id_like("12345") is True

    def test_uuid(self):
        assert is_id_like("550e8400-e29b-41d4-a716-446655440000") is True

    def test_hex(self):
        assert is_id_like("deadbeef1234") is True

    def test_natural_language(self):
        assert is_id_like("订单编号 10086 必须唯一") is False
        assert is_id_like("OCR result foo") is False


class TestNormalizeUnitContent:
    def test_too_short(self):
        assert normalize_unit_content({"content": "x"}) is None

    def test_short_chinese_ok(self):
        assert normalize_unit_content({"content": "表单"}) == "表单"
        assert normalize_unit_content({"content": "订单"}) == "订单"

    def test_drop_noise(self):
        assert normalize_unit_content({"content": "....."}) is None

    def test_drop_low_information_structured_content(self):
        assert normalize_unit_content({"content": "source=element; page=form; file=unknown"}) is None

    def test_keep_structured_content_with_business_fields(self):
        content = "system=订单系统; menu=订单管理 > 新增订单; source=element; name=保存; action=save"
        assert normalize_unit_content({"content": content}) == content

    def test_ok(self):
        content = "system=订单系统; menu=订单管理; rule=客户名称不能为空"
        assert normalize_unit_content({"content": content}) == content


class TestLowInformationStructuredContent:
    def test_detect_low_information_structured_content(self):
        assert is_low_information_structured_content("source=element; page=form; file=unknown") is True

    def test_ignore_plain_text(self):
        assert is_low_information_structured_content("点击保存后提交表单") is False


class TestFilterUnitsAndEdges:
    def test_prunes_edges(self):
        units = [
            {"unit_key": "a", "unit_type": "x", "content": "system=订单系统; menu=订单管理; rule=客户名称不能为空"},
            {"unit_key": "b", "unit_type": "x", "content": "x"},
        ]
        edges = [
            {"from_unit_key": "a", "to_unit_key": "b", "relation_type": "r"},
            {"from_unit_key": "a", "to_unit_key": "a", "relation_type": "self"},
        ]
        u2, e2 = filter_units_and_edges(units, edges)
        assert len(u2) == 1
        assert u2[0]["unit_key"] == "a"
        assert e2 == [edges[1]]
