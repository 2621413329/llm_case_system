from backend.services.semantic_unit_splitter import expand_semantic_units, split_to_semantic_units


def test_split_multi_connector():
    text = "点击保存按钮，并且刷新列表；金额不能为空"
    parts = expand_semantic_units([text])
    assert len(parts) >= 2


def test_page_line_preserved():
    text = "页面=订单管理；操作=查询"
    u = split_to_semantic_units(text)
    assert len(u) >= 1
    assert "页面=" in (u[0].get("content") or "")


def test_split_to_semantic_units_min_len():
    assert split_to_semantic_units("短") == []
