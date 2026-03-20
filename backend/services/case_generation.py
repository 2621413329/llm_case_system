from __future__ import annotations

import json
from typing import Any, Callable


def generate_cases_from_history(
    record: dict[str, Any],
    normalize_record: Callable[[dict[str, Any]], dict[str, Any]],
    normalize_case: Callable[[dict[str, Any]], dict[str, Any]],
    now_iso: Callable[[], str],
    manual_from_legacy_fields_buttons: Callable[[dict[str, Any]], dict[str, Any]],
    legacy_buttons_fields_from_elements: Callable[[dict[str, Any]], tuple[list[dict[str, Any]], list[dict[str, Any]]]],
    read_config: Callable[[], dict[str, Any]],
    get_llm_vision_runtime: Callable[[dict[str, Any]], tuple[bool, str, str, str]],
) -> list[dict[str, Any]]:
    record = normalize_record(record)
    ms = record.get("menu_structure") or []
    names = []
    if isinstance(ms, list):
        for x in ms:
            if isinstance(x, dict) and isinstance(x.get("name"), str):
                names.append(x["name"])
    feature = " / ".join(names) if names else record.get("file_name", "")
    history_id = record.get("id")

    manual = record.get("manual") if isinstance(record.get("manual"), dict) else {}
    manual = manual_from_legacy_fields_buttons(manual)
    buttons, fields = legacy_buttons_fields_from_elements(manual)

    def _field_name(f: Any) -> str:
        return f.get("name").strip() if isinstance(f, dict) and isinstance(f.get("name"), str) else ""

    def _bool(f: Any, k: str) -> bool:
        return bool(isinstance(f, dict) and f.get(k) is True)

    def _str(f: Any, k: str) -> str:
        return f.get(k).strip() if isinstance(f, dict) and isinstance(f.get(k), str) else ""

    def _int(f: Any, k: str) -> int | None:
        v = f.get(k) if isinstance(f, dict) else None
        try:
            return int(v) if v is not None and v != "" else None
        except Exception:
            return None

    def _is_empty_rule(v: str) -> bool:
        s = (v or "").strip().lower()
        return s in ["", "无", "空", "none", "null", "-", "--", "/", "n/a", "na", "未填写", "暂无"]

    def _classify_button(name: str, action: str) -> str:
        a = (action or "").strip().lower()
        n = name or ""
        if a == "query" or any(x in n for x in ["查询", "搜索", "筛选"]):
            return "query"
        if a == "create" or any(x in n for x in ["新增", "添加", "新建"]):
            return "create"
        if a == "edit" or any(x in n for x in ["编辑", "修改", "保存", "提交"]):
            return "edit"
        if a == "delete" or ("删除" in n):
            return "delete"
        if any(x in n for x in ["取消", "关闭", "返回"]):
            return "cancel"
        return "open"

    cases: list[dict[str, Any]] = []
    used_titles: set[str] = set()

    def _add_case(title_suffix: str, steps: list[str], expected: str) -> None:
        title = f"{feature} - {title_suffix}"
        if title in used_titles:
            return
        used_titles.add(title)
        cases.append(
            normalize_case(
                {
                    "id": 0,
                    "history_id": history_id,
                    "title": title,
                    "preconditions": "已登录且有权限访问该功能",
                    "steps": steps,
                    "expected": expected,
                    "status": "draft",
                    "run_notes": "",
                    "last_run_at": "",
                    "created_at": now_iso(),
                    "updated_at": now_iso(),
                }
            )
        )

    def _extract_json_array(raw: str) -> list[dict[str, Any]]:
        s = (raw or "").strip()
        if not s:
            return []
        if "```" in s:
            parts = s.split("```")
            for p in parts:
                t = p.strip()
                if t.lower().startswith("json"):
                    t = t[4:].strip()
                if t.startswith("[") and t.endswith("]"):
                    try:
                        arr = json.loads(t)
                        return arr if isinstance(arr, list) else []
                    except Exception:
                        pass
        l = s.find("[")
        r = s.rfind("]")
        if l >= 0 and r > l:
            try:
                arr = json.loads(s[l : r + 1])
                return arr if isinstance(arr, list) else []
            except Exception:
                return []
        return []

    def _fallback_cases_from_rule(fname: str, validation: str, required: bool, min_len: int | None, max_len: int | None) -> list[tuple[str, list[str], str]]:
        out: list[tuple[str, list[str], str]] = []
        rule = (validation or "").strip()
        if required:
            out.append((f"字段校验-{fname}-必填", [f"进入包含「{fname}」的表单", f"将「{fname}」置空后提交"], f"系统提示「{fname}」必填并阻止提交"))
        if any(x in rule for x in ["邮箱", "@"]):
            out.append((f"字段校验-{fname}-规则", [f"进入包含「{fname}」的表单", "输入非法邮箱格式（如 abc@）并提交"], f"系统按规则「{rule}」拦截并提示格式错误"))
        elif any(x in rule for x in ["手机", "电话", "11位", "数字"]):
            out.append((f"字段校验-{fname}-规则", [f"进入包含「{fname}」的表单", "输入非数字或位数不符内容并提交"], f"系统按规则「{rule}」拦截并提示输入错误"))
        elif any(x in rule for x in ["整数", "小数", "金额", "非负", "范围"]):
            out.append((f"字段校验-{fname}-规则", [f"进入包含「{fname}」的表单", "输入越界值（负数/超上限/非法小数位）并提交"], f"系统按规则「{rule}」拦截并给出明确提示"))
        else:
            out.append((f"字段校验-{fname}-规则", [f"进入包含「{fname}」的表单", f"按规则「{rule}」构造不合法输入并提交"], f"系统按规则拦截并提示「{fname}」校验失败"))
        if min_len is not None or max_len is not None:
            out.append((f"字段校验-{fname}-长度边界", [f"进入包含「{fname}」的表单", f"输入越界长度内容后提交（最小:{min_len or '-'} 最大:{max_len or '-'}）"], "系统对长度边界处理符合预期（拦截或提示）"))
        return out[:3]

    def _llm_cases_from_rule(fname: str, validation: str, required: bool, min_len: int | None, max_len: int | None) -> list[tuple[str, list[str], str]]:
        cfg = read_config()
        enabled, api_key, base_url, _ = get_llm_vision_runtime(cfg)
        if not enabled or not api_key:
            return []
        analysis_cfg = cfg.get("analysis") if isinstance(cfg.get("analysis"), dict) else {}
        case_cfg = analysis_cfg.get("case_generation") if isinstance(analysis_cfg.get("case_generation"), dict) else {}
        model = case_cfg.get("model") if isinstance(case_cfg.get("model"), str) and case_cfg.get("model") else "qwen-plus"
        prompt = (
            "你是测试工程师。请严格基于字段校验规则生成 1~3 条高质量测试用例，返回 JSON 数组。"
            "每项结构为 {\"title\":\"...\",\"steps\":[\"...\"],\"expected\":\"...\"}。"
            "不要输出任何解释。"
            f"\n字段名: {fname}"
            f"\n校验规则: {validation}"
            f"\nrequired: {required}"
            f"\nmin_len: {min_len if min_len is not None else ''}"
            f"\nmax_len: {max_len if max_len is not None else ''}"
        )
        payload = {"model": model, "messages": [{"role": "system", "content": "你擅长把校验规则转为可执行测试用例。"}, {"role": "user", "content": prompt}], "temperature": 0.3}
        try:
            import urllib.request

            req = urllib.request.Request(
                url=f"{base_url.rstrip('/')}/chat/completions",
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
            content = (((data.get("choices") or [{}])[0].get("message") or {}).get("content")) or ""
            arr = _extract_json_array(str(content))
            out: list[tuple[str, list[str], str]] = []
            for x in arr[:3]:
                if not isinstance(x, dict):
                    continue
                t = str(x.get("title") or "").strip()
                st = x.get("steps")
                e = str(x.get("expected") or "").strip()
                steps = [str(i).strip() for i in st] if isinstance(st, list) else []
                steps = [s for s in steps if s]
                if t and steps and e:
                    out.append((f"字段校验-{fname}-{t}", steps, e))
            return out
        except Exception:
            return []

    for b in buttons:
        if not isinstance(b, dict):
            continue
        bname = _str(b, "name") or "按钮"
        baction = _classify_button(bname, _str(b, "action"))
        requires_confirm = _bool(b, "requires_confirm")
        opens_modal = _bool(b, "opens_modal")
        if baction == "query":
            _add_case(f"按钮-{bname}-查询", ["保持默认筛选条件", f"点击「{bname}」"], "列表按预期返回数据，查询响应正常")
            continue
        if baction == "delete":
            _add_case(f"按钮-{bname}-删除", [f"点击「{bname}」", "确认删除操作"], "目标记录删除成功，列表刷新且提示清晰")
            if requires_confirm:
                _add_case(f"按钮-{bname}-删除取消", [f"点击「{bname}」", "在确认弹窗点击取消"], "不发生删除，列表数据保持不变")
            continue
        if baction == "cancel":
            _add_case(f"按钮-{bname}-取消关闭", [f"点击「{bname}」"], "当前弹窗/页面关闭，不产生数据变更")
            continue
        if baction in ["create", "edit"]:
            if opens_modal:
                _add_case(f"按钮-{bname}-打开弹窗", [f"点击「{bname}」"], "弹窗正常打开，可继续录入数据")
            _add_case(f"按钮-{bname}-提交主流程", [f"点击「{bname}」", "按字段规则填写数据并提交"], "提交成功并有明确成功提示")
            continue
        _add_case(f"按钮-{bname}-可用性", [f"点击「{bname}」"], "按钮可点击，交互无报错")

    for f in fields:
        fname = _field_name(f)
        if not fname:
            continue
        validation = _str(f, "validation")
        required = _bool(f, "required")
        min_len = _int(f, "min_len")
        max_len = _int(f, "max_len")
        if not _is_empty_rule(validation):
            ai_cases = _llm_cases_from_rule(fname, validation, required, min_len, max_len)
            if not ai_cases:
                ai_cases = _fallback_cases_from_rule(fname, validation, required, min_len, max_len)
            for title_suffix, steps, expected in ai_cases:
                _add_case(title_suffix, steps, expected)
            continue
        if required:
            _add_case(f"字段校验-{fname}-简要", [f"进入包含「{fname}」的表单", f"将「{fname}」置空后尝试提交"], f"若该字段为必填则提示必填并阻止提交；否则允许提交")
        elif min_len is not None or max_len is not None:
            _add_case(f"字段校验-{fname}-简要", [f"进入包含「{fname}」的表单", f"输入超出长度边界的值后提交（最小:{min_len or '-'} 最大:{max_len or '-'}）"], "系统对长度边界处理符合预期（拦截或提示）")
        else:
            _add_case(f"字段校验-{fname}-简要", [f"进入包含「{fname}」的表单", "输入无效值并提交（按页面实际约束）"], "系统对该字段给出明确提示或按约束处理")

    if not cases:
        _add_case("字段校验-简要", ["当前页面未配置有效字段规则", "补充“数据需求补充”中的字段校验规则后重新生成"], "生成结果应优先反映补录的校验规则")
    return cases
