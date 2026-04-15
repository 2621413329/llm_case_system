"""Tests for backend/requirement_network.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.requirement_network import build_atomic_units_and_edges, split_into_atomic_rules


def _sample_record() -> dict:
    return {
        "id": 12,
        "system_name": "订单系统",
        "file_name": "订单系统_订单管理_新增订单.png",
        "menu_structure": [
            {"level": 1, "name": "订单管理"},
            {"level": 2, "name": "新增订单"},
        ],
        "manual": {
            "page_type": "form",
            "page_elements": [
                {
                    "name": "保存",
                    "element_type": "button",
                    "action": "保存",
                    "required": False,
                    "queryable": False,
                    "opens_modal": False,
                    "requires_confirm": True,
                },
                {
                    "name": "客户名称",
                    "element_type": "input",
                    "validation": "必填",
                    "required": True,
                    "queryable": True,
                },
            ],
        },
        "analysis_style_table": [
            {"element": "保存", "attribute": "按钮颜色", "requirement": "主按钮高亮显示"},
            {"element": "客户名称", "attribute": "输入框提示", "requirement": "未填写时显示错误"},
        ],
        "analysis_content": "客户名称不能为空；订单提交后必须生成订单编号；列表需要展示客户名称和状态。",
        "analysis_interaction": "点击保存后提交表单；校验失败时阻止提交并提示错误。",
        "analysis_data": {
            "current_function": {
                "menu_path": "订单管理 > 新增订单",
                "page_type": "form",
                "core_actions": ["保存", "返回"],
                "key_fields": ["客户名称", "订单日期"],
                "result_views": ["提交结果提示"],
            },
            "elements_overview": [
                {"name": "客户名称", "element_type": "input", "validation": "必填"},
            ],
            "upstream_dependencies": [
                {"source": "客户主数据", "data_object": "客户档案", "trigger": "选择客户", "rule": "仅可选择启用客户"},
            ],
            "downstream_impacts": [
                {"target": "订单列表", "action": "新增", "impact": "新增后列表可查询到该订单"},
            ],
        },
        "_vector_analysis_text": "新增订单页面必须先校验客户名称；点击保存后生成订单编号并返回列表。",
    }


class TestSplitIntoAtomicRules:
    def test_split_and_dedupe(self):
        parts = split_into_atomic_rules("A rule；A rule。\nSecond rule")
        assert parts == ["A rule", "Second rule"]

    def test_structured_page_line_kept_intact(self):
        # 使用转义避免部分环境下测试文件编码导致「页面=」前缀识别失败
        page = "\u9875\u9762"  # 页面
        line1 = page + "=listA\uFF1Bop=query\uFF1Bresult=list"
        line2 = page + "=listB\uFF1Bop=add\uFF1Btrigger=click\uFF1Bresult=modal"
        text = line1 + "\n" + line2
        parts = split_into_atomic_rules(text)
        assert len(parts) == 2
        assert parts[0].startswith(page + "=listA")
        assert "op=query" in parts[0]
        assert page + "=listB" in parts[1]

    def test_business_retrieval_line_fullwidth_semicolon_intact(self):
        """页面=…；操作=…；条件=…；结果=… 整行一条，不按分号切碎。"""
        page, op, cond, res = "\u9875\u9762", "\u64cd\u4f5c", "\u6761\u4ef6", "\u7ed3\u679c"
        line = (
            f"{page}=\u62a5\u540d\u4eba\u6570\u7edf\u8ba1\uFF1B{op}=\u9875\u9762\u52a0\u8f7d\uFF1B"
            f"{cond}=\u5f53\u524d\u767b\u5f55\u7528\u6237\uFF1B{res}=\u5c55\u793a\u8003\u70b9"
        )
        parts = split_into_atomic_rules(line)
        assert len(parts) == 1
        assert page + "=" in parts[0] and op + "=" in parts[0]

    def test_section_headers_skipped(self):
        text = "\u6838\u5fc3\u5904\u7406\u903b\u8f91\uFF1A\n- \u6743\u9650\u8fc7\u6ee4"
        parts = split_into_atomic_rules(text)
        assert not any(p == "\u6838\u5fc3\u5904\u7406\u903b\u8f91\uFF1A" for p in parts)
        assert any("\u6743\u9650" in p for p in parts)


class TestBuildAtomicUnitsAndEdges:
    def test_structured_content_contains_context(self):
        units, _ = build_atomic_units_and_edges(_sample_record())
        element_unit = next(unit for unit in units if unit["unit_type"] == "element" and "name=保存" in unit["content"])
        assert "system=订单系统" in element_unit["content"]
        assert "menu=订单管理 > 新增订单" in element_unit["content"]
        assert "page=form" in element_unit["content"]
        assert "source=element" in element_unit["content"]

    def test_vector_analysis_is_split_into_rules(self):
        units, _ = build_atomic_units_and_edges(_sample_record())
        vector_rules = [unit for unit in units if unit["unit_type"] == "vector_analysis_rule"]
        assert len(vector_rules) >= 2
        assert all("source=vector_rule" in unit["content"] for unit in vector_rules)

    def test_multiline_vector_text_yields_multiple_business_rules(self):
        """多行建库文本在入库前须保留换行，使【业务检索句】每行独立成 vector_analysis_rule。"""
        rec = _sample_record()
        page = "\u9875\u9762"
        rec["_vector_analysis_text"] = (
            "\u3010\u9700\u6c42\u5411\u91cf\u6784\u5efa\u5206\u6790\u7ed3\u679c\u3011\n\n"
            "\u5f53\u524d\u529f\u80fd\u65e8\u5728\u63d0\u4f9b\u7edf\u8ba1\u5c55\u793a\u3002\n\n"
            "\u3010\u4e1a\u52a1\u68c0\u7d22\u53e5\u3011\n"
            f"{page}=\u62a5\u540d\u4eba\u6570\u7edf\u8ba1\uFF1B\u64cd\u4f5c=\u52a0\u8f7d\uFF1B"
            f"\u6761\u4ef6=\u7528\u6237A\uFF1B\u7ed3\u679c=\u5c55\u793aA\n"
            f"{page}=\u62a5\u540d\u4eba\u6570\u7edf\u8ba1\uFF1B\u64cd\u4f5c=\u4e0b\u8f7d\uFF1B"
            f"\u6761\u4ef6=\u6709\u6570\u636e\uFF1B\u7ed3\u679c=\u6587\u4ef6"
        )
        units, _ = build_atomic_units_and_edges(rec)
        vector_rules = [u for u in units if u["unit_type"] == "vector_analysis_rule"]
        rule_texts = [u["content"] for u in vector_rules]
        load_hits = sum(1 for c in rule_texts if "\u52a0\u8f7d" in c and page + "=" in c)
        dl_hits = sum(1 for c in rule_texts if "\u4e0b\u8f7d" in c)
        assert load_hits >= 1
        assert dl_hits >= 1

    def test_requirement_rules_are_atomic(self):
        units, _ = build_atomic_units_and_edges(_sample_record())
        requirement_rules = [unit for unit in units if unit["unit_type"] == "requirement_rule"]
        assert len(requirement_rules) == 3
        assert any("rule=客户名称不能为空" in unit["content"] for unit in requirement_rules)
        assert any("rule=订单提交后必须生成订单编号" in unit["content"] for unit in requirement_rules)

    def test_edges_link_vector_and_requirement_units(self):
        units, edges = build_atomic_units_and_edges(_sample_record())
        vector_rule_keys = {unit["unit_key"] for unit in units if unit["unit_type"] == "vector_analysis_rule"}
        requirement_keys = {unit["unit_key"] for unit in units if unit["unit_type"] == "requirement_rule"}
        assert any(
            edge["from_unit_key"] in vector_rule_keys and edge["to_unit_key"] in requirement_keys
            for edge in edges
        )
