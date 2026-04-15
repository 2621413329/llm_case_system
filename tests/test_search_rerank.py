"""Tests for backend/services/search_rerank.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.services.search_rerank import rerank_results


class TestRerankResults:
    def test_boost_metadata_name_match(self):
        results = [
            {
                "unit_key": "a",
                "unit_type": "requirement_rule",
                "score": 0.81,
                "content": "system=订单系统; menu=订单管理; rule=新增订单后返回列表",
                "metadata": {},
            },
            {
                "unit_key": "b",
                "unit_type": "element",
                "score": 0.8,
                "content": "system=订单系统; menu=订单管理; source=element; name=保存; action=save",
                "metadata": {"name": "保存", "action": "save"},
            },
        ]
        ranked = rerank_results("保存按钮", results)
        assert ranked[0]["unit_key"] == "b"

    def test_keep_order_when_no_query_tokens(self):
        results = [
            {"unit_key": "a", "unit_type": "element", "score": 0.7, "content": "x", "metadata": {}},
            {"unit_key": "b", "unit_type": "element", "score": 0.6, "content": "y", "metadata": {}},
        ]
        ranked = rerank_results("", results)
        assert [item["unit_key"] for item in ranked] == ["a", "b"]
