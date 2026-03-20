from __future__ import annotations

from typing import Any


def menu_names(record: dict[str, Any]) -> list[str]:
    ms = record.get("menu_structure") or []
    names: list[str] = []
    if isinstance(ms, list):
        for x in ms:
            if isinstance(x, dict) and isinstance(x.get("name"), str):
                names.append(x["name"])
    return names


def breadcrumb_for_record(record: dict[str, Any]) -> str:
    names = menu_names(record)
    return " > ".join(names) if names else "（未解析菜单）"


def contextual_hints_from_menu(names: list[str]) -> list[str]:
    if not names:
        return ["路径信息较少：请对照截图确认业务对象、主操作入口与关键字段。"]
    blob = "".join(names)
    hints: list[str] = []
    keyword_rows: list[tuple[list[str], str]] = [
        (["订单", "采购", "销售", "合同", "报价", "开票", "收款"], "交易/订单类：状态流转、金额与数量精度、审核/作废/回退、导出与打印、幂等与重复下单。"),
        (["用户", "客户", "会员", "账号", "组织", "员工", "角色"], "主数据与账号：新增/编辑/禁用、重置密码、敏感字段脱敏、角色权限与操作审计。"),
        (["库存", "仓库", "物料", "商品", "SKU", "入库", "出库"], "库存仓储：数量冻结、批次/效期、盘点差异、负库存与预警、并发修改。"),
        (["报表", "统计", "看板", "Dashboard", "大屏"], "报表看板：筛选维度组合、大数据量与超时、导出、空数据与无权限提示。"),
        (["配置", "设置", "参数", "字典", "模板"], "配置类：生效范围、脏数据回滚、必填与非法值拦截、变更审计。"),
        (["审批", "流程", "待办", "工单"], "流程类：撤回/驳回/转办、并发节点、通知与待办列表一致性。"),
        (["日志", "审计", "操作记录"], "审计日志：记录完整性、查询筛选、导出权限与时间范围边界。"),
    ]
    for keys, line in keyword_rows:
        if any(k in blob for k in keys):
            hints.append(line)
    if not hints:
        hints.append("通用：主列表/表单的核心字段校验、主操作成功/失败提示、列表刷新与分页。")
    return hints


def build_analysis(record: dict[str, Any]) -> str:
    names = menu_names(record)
    breadcrumb = breadcrumb_for_record(record)
    file_name = record.get("file_name") if isinstance(record.get("file_name"), str) else ""
    ctx_lines = contextual_hints_from_menu(names)
    lines = [
        f"来源截图：{file_name}",
        f"功能入口：{breadcrumb}",
        "",
        "【基于菜单路径的测试关注点提示】（须与截图互相印证，不能替代实际界面）：",
    ]
    for h in ctx_lines:
        lines.append(f"- {h}")
    lines.extend(
        [
            "",
            "可能涉及的功能点（可按实际页面调整）：",
            "- 页面展示：列表/表单/详情/弹窗与空态/加载态",
            "- 查询筛选：条件组合、重置、结果正确性与性能体感",
            "- 新增/编辑：表单校验、提交、成功/失败提示与数据回显",
            "- 删除与危险操作：二次确认、幂等、失败回滚提示",
            "- 权限与异常：无权限、网络/接口失败、越权与数据隔离",
            "",
            "测试用例方向（通用骨架）：",
            "- 主流程：最短成功路径 + 关键分支",
            "- 边界：必填/长度/格式/数值上下限",
            "- 异常：接口错误码、超时、重复提交",
            "- 体验：禁用态、loading、键盘与无障碍（按产品要求）",
        ]
    )
    return "\n".join(lines)


def infer_container(record: dict[str, Any], ocr_text: str) -> str:
    manual = record.get("manual") if isinstance(record.get("manual"), dict) else {}
    page_type = manual.get("page_type") if isinstance(manual.get("page_type"), str) else ""
    if page_type == "modal":
        return "弹窗"
    if page_type == "form":
        return "表单"
    t = "".join((ocr_text or "").split())
    if any(x in t for x in ["取消", "确定", "关闭", "返回"]):
        return "弹窗"
    return "页面"


def build_tested_items_from_ocr(record: dict[str, Any], ocr_text: str) -> tuple[list[dict[str, Any]], str]:
    container = infer_container(record, ocr_text)
    t = "".join((ocr_text or "").split())
    field_map: list[tuple[list[str], str, list[str]]] = [
        (["姓名"], "姓名", ["必填性校验（空值不可提交/有明确提示）", "长度边界校验（最小/最大长度按规则）", "特殊字符/空格规则校验（提示清晰、禁止非法提交）", "正确输入后允许提交且数据回显一致"]),
        (["手机号", "电话", "手机"], "手机号", ["必填性校验", "格式校验（仅数字/允许前缀规则按产品约定）", "长度边界校验", "输入非法值时提示文案准确且禁止提交"]),
        (["邮箱"], "邮箱", ["必填性校验", "邮箱格式校验（如需包含@与域名）", "长度边界校验", "输入非法值时提示文案准确且禁止提交"]),
        (["用户名", "账号", "登录名"], "用户名/账号", ["必填性校验", "字符集/长度校验（去除首尾空格/非法字符提示）", "输入非法值禁止提交", "正确输入后提交成功提示与回显正确"]),
        (["密码"], "密码", ["必填性校验", "长度边界校验（最小/最大长度）", "错误/弱密码规则提示（如有强度要求）", "正确输入后提交成功且不会出现异常"]),
    ]
    tested_items: list[dict[str, Any]] = []

    def _push(title: str, direction: list[str]) -> None:
        if any(x.get("title") == title for x in tested_items):
            return
        tested_items.append({"title": title, "direction": "\n".join(direction)})

    for keys, display_name, directions in field_map:
        if any(k in t for k in keys):
            _push(f"{container}内填写处 - {display_name}", directions)

    if not tested_items:
        _push(f"{container}通用验证", ["验证关键区域可见且无明显报错", "按钮交互：可点/loading/禁用态正确", "接口失败时错误提示清晰", "异常/边界值行为符合预期"])

    bullet_lines = []
    for it in tested_items[:12]:
        dir_text = str(it.get("direction") or "")
        bullet_lines.append(f"- {it.get('title')}\n  {dir_text.replace(chr(10), chr(10) + '  ')}")
    suffix = "\n\nOCR识别修正后的被测项建议：\n" + "\n".join(bullet_lines)
    return tested_items[:12], suffix
