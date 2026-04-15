from __future__ import annotations

import json
import os
import re
from typing import Any, Callable

from backend.config.model_resolve import case_generation_model, dashscope_compat_base_url, llm_vision_model

try:
    from backend.services.normalize import normalize_case_priority as _case_priority
except Exception:
    try:
        from services.normalize import normalize_case_priority as _case_priority  # type: ignore
    except Exception:

        def _case_priority(raw: Any) -> str:
            s = str(raw or "").strip().upper()
            return s if s in ("P0", "P1", "P2", "P3") else "P2"


def _fallback_case_scope_assessment(
    *,
    has_overall: bool,
    analysis_excerpt: str,
    feature: str,
    has_content: bool,
    has_interaction: bool,
    has_data: bool,
) -> str:
    """LLM 不可用时，基于素材来源的规则兜底范围说明。"""
    src = "总体分析（analysis 字段）" if has_overall else "分项分析拼接（内容/交互/数据）"
    parts: list[str] = []
    if has_content:
        parts.append("需求内容分析")
    if has_interaction:
        parts.append("交互分析")
    if has_data:
        parts.append("数据分析")
    tail = "、".join(parts) if parts else "无分项"
    excerpt_lines = [ln.rstrip() for ln in analysis_excerpt.splitlines()[:14] if str(ln).strip()]
    excerpt_block = "\n".join(f"  - {ln}" for ln in excerpt_lines) or "  - （摘录为空）"
    return (
        "## 功能边界与假设\n"
        f"- 功能路径：{feature}\n"
        f"- 范围依据来源：{src}（可用分项：{tail}）\n\n"
        "## 必测维度检查清单（规则推断）\n"
        "- 主流程：建议必须覆盖（在登录/权限前提下）\n"
        "- 异常与校验：素材含字段/按钮/校验描述则必须覆盖\n"
        "- 边界：长度、数值、空值等素材提及则覆盖\n"
        "- 权限与数据隔离：素材提及角色、考点、可见范围则覆盖\n"
        "- 列表、统计、导出：素材提及则覆盖\n\n"
        "## 与主分析素材对齐（摘录）\n"
        f"{excerpt_block}\n\n"
        "## 建议用例数量级\n"
        "- 合计约 15–35 条（随素材增减），须包含主流程与关键异常\n\n"
        "## 信息缺口\n"
        "- 当前为规则兜底评估；补全并保存《总体分析》后可获得更精准的 LLM 范围评估。\n"
    )


def generate_cases_from_history(
    record: dict[str, Any],
    normalize_record: Callable[[dict[str, Any]], dict[str, Any]],
    normalize_case: Callable[[dict[str, Any]], dict[str, Any]],
    now_iso: Callable[[], str],
    manual_from_legacy_fields_buttons: Callable[[dict[str, Any]], dict[str, Any]],
    legacy_buttons_fields_from_elements: Callable[[dict[str, Any]], tuple[list[dict[str, Any]], list[dict[str, Any]]]],
    read_config: Callable[[], dict[str, Any]],
    get_llm_vision_runtime: Callable[[dict[str, Any]], tuple[bool, str, str, str]],
    read_requirement_network_for_search: Callable[..., list[dict[str, Any]]] | None = None,
    emit: Callable[[dict[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
    record = normalize_record(record)
    history_id = record.get("id")
    has_overall_analysis = bool(str(record.get("analysis") or "").strip())
    menu_names = []
    ms = record.get("menu_structure")
    if isinstance(ms, list):
        for x in ms:
            if isinstance(x, dict) and isinstance(x.get("name"), str):
                menu_names.append(x.get("name"))
    feature = " / ".join([str(x) for x in menu_names if str(x).strip()]) or str(record.get("file_name") or "页面")

    def _emit(event: str, msg: str = "", **kwargs: Any) -> None:
        if not callable(emit):
            return
        payload: dict[str, Any] = {"event": event}
        if msg:
            payload["msg"] = msg
        payload.update(kwargs)
        try:
            emit(payload)
        except Exception:
            pass

    def _clip(text: Any, limit: int = 400) -> str:
        s = str(text or "").strip()
        if len(s) <= limit:
            return s
        return s[: max(0, limit - 3)] + "..."

    def _case_http_timeout() -> int:
        cfg = read_config()
        analysis_cfg = cfg.get("analysis") if isinstance(cfg.get("analysis"), dict) else {}
        case_cfg = analysis_cfg.get("case_generation") if isinstance(analysis_cfg.get("case_generation"), dict) else {}
        raw = case_cfg.get("request_timeout", case_cfg.get("http_timeout"))
        try:
            t = int(raw) if raw is not None and str(raw).strip() else 180
        except Exception:
            t = 180
        return max(30, min(600, t))

    manual_raw = record.get("manual")
    if not isinstance(manual_raw, dict):
        manual_raw = {}
    try:
        manual = manual_from_legacy_fields_buttons(manual_raw)
    except Exception:
        manual = manual_raw
    try:
        buttons, fields = legacy_buttons_fields_from_elements(manual if isinstance(manual, dict) else {})
    except Exception:
        buttons, fields = ([], [])
    buttons = buttons if isinstance(buttons, list) else []
    fields = fields if isinstance(fields, list) else []

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

    ad_obj = record.get("analysis_data")
    if isinstance(ad_obj, dict):
        eo = ad_obj.get("elements_overview")
        if isinstance(eo, list):
            known = {_field_name(x) for x in fields if isinstance(x, dict)}
            for item in eo[:200]:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or "").strip()
                if not name or name in known:
                    continue
                fobj = {
                    "name": name,
                    "required": bool(item.get("required")),
                    "validation": str(item.get("validation") or "").strip(),
                    "min_len": item.get("min_len"),
                    "max_len": item.get("max_len"),
                }
                fields.append(fobj)
                known.add(name)

    analysis_text = str(record.get("analysis") or "").strip()
    if not analysis_text:
        fallback_parts: list[str] = []
        content_text = str(record.get("analysis_content") or "").strip()
        interaction_text = str(record.get("analysis_interaction") or "").strip()
        data_raw = record.get("analysis_data")
        data_text = ""
        if isinstance(data_raw, str):
            data_text = data_raw.strip()
        elif data_raw not in (None, ""):
            try:
                data_text = json.dumps(data_raw, ensure_ascii=False)
            except Exception:
                data_text = str(data_raw)
            data_text = data_text.strip()
        if content_text:
            fallback_parts.append("【需求内容分析】\n" + content_text[:6000])
        if interaction_text:
            fallback_parts.append("【交互分析】\n" + interaction_text[:5000])
        if data_text:
            fallback_parts.append("【数据分析】\n" + data_text[:5000])
        if not fallback_parts:
            raise RuntimeError("缺少可生成依据：请先生成需求分析（内容/交互/数据）或保存 AI 分析结果后再生成用例。")
        analysis_text = "\n\n".join(fallback_parts)
        _emit("stage", "主分析为空，已回退使用分析子结果拼接上下文", history_id=history_id)

    cases: list[dict[str, Any]] = []
    used_titles: set[str] = set()
    used_title_keys: set[str] = set()
    used_shape_keys: set[str] = set()
    generic_prefix_count: dict[str, int] = {}

    def _title_key(title: str) -> str:
        return " ".join(str(title or "").strip().lower().split())

    def _norm_text(s: Any) -> str:
        t = str(s or "").strip().lower()
        t = re.sub(r"\s+", "", t)
        # 去除常见序号、轮次、括号数字，提升“近重复”识别能力
        t = re.sub(r"(轮次|第)\d+", "", t)
        t = re.sub(r"[（(]\d+[）)]", "", t)
        t = re.sub(r"\d+", "", t)
        return t

    def _generic_prefix(s: str) -> str:
        t = str(s or "").strip()
        prefixes = [
            "主流程",
            "异常流程",
            "边界流程",
            "字段校验",
            "交互逻辑",
            "状态流转",
            "查询行为",
            "数据联动",
            "权限校验",
        ]
        for p in prefixes:
            if t.startswith(p):
                return p
        return ""

    def _shape_key(title_suffix: str, steps: list[str], expected: str) -> str:
        title_n = _norm_text(title_suffix)
        steps_n = "|".join(_norm_text(x) for x in steps[:6] if _norm_text(x))
        expected_n = _norm_text(expected)
        return f"{title_n}##{steps_n}##{expected_n}"

    def _contains_any(text: str, kws: list[str]) -> bool:
        s = str(text or "").lower()
        return any(k in s for k in kws)

    def _is_positive_case(title_suffix: str, steps: list[str], expected: str) -> bool:
        blob = " ".join([str(title_suffix or ""), str(expected or "")] + [str(x or "") for x in steps])
        # 负向/异常/拦截信号：命中任一即判为非正向
        negative_kws = [
            "异常",
            "失败",
            "报错",
            "错误",
            "拦截",
            "阻止",
            "无权限",
            "越权",
            "拒绝",
            "不允许",
            "为空",
            "空值",
            "缺失",
            "非法",
            "无效",
            "边界",
            "超长",
            "超限",
            "删除",
            "回滚",
            "超时",
            "重复提交",
        ]
        if _contains_any(blob, negative_kws):
            return False
        # 正向信号：用于确认是主路径可用性场景
        positive_kws = ["成功", "可见", "展示", "保存", "提交", "生效", "通过", "正确", "返回列表", "回显一致"]
        return _contains_any(blob, positive_kws)

    def _add_case(
        title_suffix: str,
        steps: list[str],
        expected: str,
        priority: str | None = None,
        *,
        source: str = "llm",
    ) -> None:
        suffix = str(title_suffix or "").strip()
        if not suffix:
            suffix = "通用场景"
        steps_clean = [str(s).strip() for s in steps if str(s).strip()]
        expected_clean = str(expected or "").strip()
        if not steps_clean or not expected_clean:
            return

        if source == "llm":
            gp = _generic_prefix(suffix)
            if gp:
                c = int(generic_prefix_count.get(gp) or 0)
                # 同类模板前缀最多保留 2 条，鼓励多样化标题
                if c >= 2:
                    return
                generic_prefix_count[gp] = c + 1
            sk = _shape_key(suffix, steps_clean, expected_clean)
            if sk in used_shape_keys:
                return
            used_shape_keys.add(sk)

        title = f"{feature} - {suffix}"
        tkey = _title_key(title)
        if title in used_titles or tkey in used_title_keys:
            return
        used_titles.add(title)
        used_title_keys.add(tkey)
        cases.append(
            normalize_case(
                {
                    "id": 0,
                    "history_id": history_id,
                    "title": title,
                    "preconditions": "已登录且有权限访问该功能",
                    "steps": steps_clean,
                    "expected": expected_clean,
                    "step_expected": [],
                    "priority": priority or "P2",
                    "status": "draft",
                    "run_notes": "",
                    "last_run_at": "",
                    "executor_id": None,
                    "executor_name": "",
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
            for p in s.split("```"):
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

    def _resolve_case_generation_runtime() -> tuple[bool, str, str, str]:
        cfg = read_config()
        analysis_cfg = cfg.get("analysis") if isinstance(cfg.get("analysis"), dict) else {}
        case_cfg = analysis_cfg.get("case_generation") if isinstance(analysis_cfg.get("case_generation"), dict) else {}
        vision_cfg = analysis_cfg.get("llm_vision") if isinstance(analysis_cfg.get("llm_vision"), dict) else {}
        ocr_cfg = cfg.get("ocr") if isinstance(cfg.get("ocr"), dict) else {}
        ds_cfg = ocr_cfg.get("dashscope") if isinstance(ocr_cfg.get("dashscope"), dict) else {}

        enabled_raw = case_cfg.get("enabled")
        enabled = True if enabled_raw is None else bool(enabled_raw)
        api_key = ""
        if isinstance(case_cfg.get("api_key"), str) and case_cfg.get("api_key").strip():
            api_key = case_cfg.get("api_key").strip()
        elif isinstance(vision_cfg.get("api_key"), str) and vision_cfg.get("api_key").strip():
            api_key = vision_cfg.get("api_key").strip()
        elif isinstance(ds_cfg.get("api_key"), str) and ds_cfg.get("api_key").strip():
            api_key = ds_cfg.get("api_key").strip()
        else:
            api_key = os.getenv("DASHSCOPE_API_KEY") or ""

        base_url = ""
        if isinstance(case_cfg.get("base_url"), str) and case_cfg.get("base_url").strip():
            base_url = case_cfg.get("base_url").strip()
        elif isinstance(vision_cfg.get("base_url"), str) and vision_cfg.get("base_url").strip():
            base_url = vision_cfg.get("base_url").strip()
        elif isinstance(ds_cfg.get("base_url"), str) and ds_cfg.get("base_url").strip():
            base_url = ds_cfg.get("base_url").strip()
        else:
            base_url = dashscope_compat_base_url(cfg)
        model = case_generation_model(cfg)
        # Guard: realtime models are not stable for this sync chat/completions path.
        if isinstance(model, str) and "realtime" in model.lower():
            fallback_model = llm_vision_model(cfg)
            if isinstance(fallback_model, str) and fallback_model.strip() and "realtime" not in fallback_model.lower():
                model = fallback_model.strip()
        return enabled and bool(api_key), api_key, base_url, model

    def _llm_plain_chat(system: str, user: str, *, max_tokens: int = 2000) -> str:
        enabled, api_key, base_url, model = _resolve_case_generation_runtime()
        if not enabled or not api_key:
            return ""
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.25,
            "top_p": 0.9,
            "max_tokens": max_tokens,
        }
        _emit(
            "ai_request",
            "请求 LLM 生成用例范围评估",
            history_id=history_id,
            prompt_preview=_clip(user, 900),
        )
        try:
            import urllib.request

            req = urllib.request.Request(
                url=f"{base_url.rstrip('/')}/chat/completions",
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=_case_http_timeout()) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
            content = (((data.get("choices") or [{}])[0].get("message") or {}).get("content")) or ""
            text = str(content).strip()
            _emit(
                "ai_response",
                "LLM 已返回用例范围评估",
                history_id=history_id,
                response_preview=_clip(text, 800),
            )
            return text
        except Exception as e:
            _emit("error", f"范围评估 LLM 调用失败：{e}", history_id=history_id)
            return ""

    _emit(
        "log",
        "正在基于主分析素材生成「用例生成范围评估」…",
        history_id=history_id,
    )
    scope_user = (
        "你是测试负责人。请仅根据下列《主分析素材》输出《用例生成范围评估》（中文，可用 ## 标题分段）。\n"
        "未在素材中出现的内容不要编造，用「待确认」标注。\n\n"
        "输出必须包含：\n"
        "## 功能边界与假设\n"
        "## 必测维度检查清单（主流程、异常、边界、权限、数据一致性、导出/下载、空数据等；"
        "每项标注：必须覆盖 / 建议覆盖 / 素材未涉及）\n"
        "## 与总体分析对齐的关键验证点（摘录素材中可测、可执行的陈述）\n"
        "## 建议用例产出侧重与数量级（例如主流程 4–8 条、异常 3–6 条，给区间）\n"
        "## 信息缺口与待确认\n\n"
        f"《主分析素材》（节选，不超过约 6000 字）：\n---\n{analysis_text[:6000]}\n---\n"
        f"功能路径：{feature}\n"
    )
    scope_body = _llm_plain_chat(
        "你只依据用户提供的素材做测试范围评估，不臆造业务规则；输出供后续生成测试用例时严格遵守。",
        scope_user,
        max_tokens=2200,
    )
    if not scope_body.strip():
        scope_body = _fallback_case_scope_assessment(
            has_overall=has_overall_analysis,
            analysis_excerpt=analysis_text[:2000],
            feature=feature,
            has_content=bool(str(record.get("analysis_content") or "").strip()),
            has_interaction=bool(str(record.get("analysis_interaction") or "").strip()),
            has_data=bool(record.get("analysis_data")),
        )
    _emit(
        "scope_assessment",
        msg="用例生成范围评估",
        scope_text=scope_body.strip(),
        has_overall_analysis=has_overall_analysis,
        history_id=history_id,
    )

    def _compact_json(v: Any, max_len: int = 600) -> str:
        try:
            s = json.dumps(v, ensure_ascii=False)
        except Exception:
            s = str(v or "")
        s = s.replace("\n", " ").strip()
        if len(s) > max_len:
            s = s[: max_len - 3] + "..."
        return s

    def _collect_vector_context(limit_same: int = 60, limit_global: int = 80) -> tuple[str, int]:
        if not callable(read_requirement_network_for_search):
            return "", 0
        hid = record.get("id")
        sid = record.get("system_id")
        try:
            hid_i = int(hid) if hid is not None else None
        except Exception:
            hid_i = None
        try:
            sid_i = int(sid) if sid is not None else None
        except Exception:
            sid_i = None
        try:
            same = read_requirement_network_for_search(history_id=hid_i, system_id=sid_i) if hid_i is not None else []
            if sid_i is not None:
                all_units = read_requirement_network_for_search(history_id=None, system_id=sid_i)
            else:
                all_units = []
        except Exception:
            return "", 0
        same = same if isinstance(same, list) else []
        all_units = all_units if isinstance(all_units, list) else []

        selected: list[dict[str, Any]] = []
        seen: set[str] = set()
        cross_count = 0
        for u in same[: max(0, int(limit_same))]:
            if not isinstance(u, dict):
                continue
            key = f"{u.get('history_id')}::{u.get('unit_key')}"
            if key in seen:
                continue
            seen.add(key)
            selected.append(u)
        for u in all_units:
            if len(selected) >= int(limit_same) + int(limit_global):
                break
            if not isinstance(u, dict):
                continue
            if str(u.get("unit_type") or "").strip() not in ["cross_page_link", "cross_page_dependency"]:
                continue
            key = f"{u.get('history_id')}::{u.get('unit_key')}"
            if key in seen:
                continue
            seen.add(key)
            selected.append(u)
            cross_count += 1
        for u in all_units:
            if len(selected) >= int(limit_same) + int(limit_global):
                break
            if not isinstance(u, dict):
                continue
            key = f"{u.get('history_id')}::{u.get('unit_key')}"
            if key in seen:
                continue
            seen.add(key)
            selected.append(u)

        lines: list[str] = []
        for u in selected:
            ut = str(u.get("unit_type") or "").strip() or "unknown"
            content = str(u.get("content") or "").strip()
            if len(content) > 260:
                content = content[:257] + "..."
            lines.append(f"- [{ut}] {content} | metadata={_compact_json(u.get('metadata'), max_len=300)}")
        return "\n".join(lines[:220])[:28000], cross_count

    def _llm_generate(prompt: str, *, temperature: float = 0.2, max_tokens: int = 5200) -> list[tuple[str, list[str], str, str]]:
        enabled, api_key, base_url, model = _resolve_case_generation_runtime()
        if not enabled or not api_key:
            return []
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "你是资深测试工程师，擅长从需求上下文生成可执行测试用例。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "top_p": 0.9,
            "max_tokens": max_tokens,
        }
        _emit("ai_request", "请求 LLM 生成测试用例", history_id=history_id, prompt_preview=_clip(prompt, 1000))
        try:
            import urllib.request

            req = urllib.request.Request(
                url=f"{base_url.rstrip('/')}/chat/completions",
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=_case_http_timeout()) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
            content = (((data.get("choices") or [{}])[0].get("message") or {}).get("content")) or ""
            arr = _extract_json_array(str(content))
            _emit("ai_response", f"LLM 返回候选 {len(arr)} 条", history_id=history_id, response_preview=_clip(content, 900))
            out: list[tuple[str, list[str], str, str]] = []
            for x in arr[:80]:
                if not isinstance(x, dict):
                    continue
                t = str(x.get("title") or "").strip()
                e = str(x.get("expected") or "").strip()
                st = x.get("steps")
                steps = [str(i).strip() for i in st] if isinstance(st, list) else []
                steps = [s for s in steps if s]
                if t and e and steps:
                    pr = _case_priority(x.get("priority"))
                    # 规则：P0 仅允许正向主流程；非正向自动降级为 P1
                    if pr == "P0" and not _is_positive_case(t, steps, e):
                        pr = "P1"
                    out.append((t, steps, e, pr))
            return out
        except Exception as e:
            _emit("error", f"LLM 调用失败：{e}", history_id=history_id)
            return []

    vector_ctx, cross_hint_count = _collect_vector_context()
    cross_rule = ""
    if cross_hint_count > 0:
        cross_rule = f"\n8) 至少输出 {max(2, min(8, 2 + int(cross_hint_count / 4)))} 条跨页面联动用例。"
    scope_for_prompt = scope_body.strip()[:4500]
    overall_hint = (
        "《总体分析》字段已提供，主分析以总体分析为优先主干。"
        if has_overall_analysis
        else "《总体分析》未提供，主分析由分项结果拼接；用例仍须与下列范围评估及素材一致。"
    )
    prompt = (
        "请基于以下上下文生成 JSON 数组测试用例。\n"
        "每项结构：{\"title\":\"...\",\"steps\":[\"...\"],\"expected\":\"...\",\"priority\":\"P0|P1|P2|P3\"}\n"
        f"范围约束：{overall_hint}\n"
        "你必须遵守下方【用例生成范围评估】中的「必须覆盖」「建议覆盖」组织用例；"
        "对标注为「素材未涉及」的维度不要硬编业务细节，可写「待确认」类步骤。\n"
        "同时覆盖主流程、异常流程、边界条件、权限与数据联动场景（与评估一致）。\n"
        "优先级规则：P0 只能用于正向主流程成功场景；异常/边界/权限拦截/校验失败类场景最高标记到 P1。\n"
        "标题去模板化要求：不要使用“主流程-”“异常流程-”“边界流程-”“字段校验-”等固定前缀命名；"
        "标题请写成“业务动作 + 条件 + 结果/目的”的具体表达。\n"
        "避免重复：同一类动作不要只改序号或轮次，不要输出语义重复用例。\n"
        "不要输出解释文字，不要 markdown，仅输出 JSON 数组。"
        + cross_rule
        + f"\n\n功能: {feature}"
        + f"\n\n【用例生成范围评估】\n{scope_for_prompt}"
        + f"\n\n【主分析】\n{analysis_text[:6000]}"
        + f"\n\n【内容分析】\n{str(record.get('analysis_content') or '')[:3000]}"
        + f"\n\n【交互分析】\n{str(record.get('analysis_interaction') or '')[:3000]}"
        + f"\n\n【数据分析】\n{_compact_json(record.get('analysis_data'), max_len=4000)}"
        + f"\n\n【需求池上下文】\n{vector_ctx[:28000]}"
    )
    generated = _llm_generate(prompt, temperature=0.2, max_tokens=5200)
    if not generated:
        raise RuntimeError("LLM 生成失败：无法基于当前分析结果生成测试用例。")

    for title_suffix, steps, expected, pr in generated:
        _add_case(title_suffix, steps, expected, pr)

    # 保底补齐关键上下游联动用例
    _add_case(
        "数据联动-新增后列表可见",
        ["新增一条合法业务数据并保存成功", "返回列表页并刷新数据"],
        "新增数据在列表中可见，关键字段展示与录入一致",
        "P1",
        source="fallback",
    )
    _add_case(
        "数据联动-删除后查询隔离",
        ["删除一条目标数据并确认操作", "使用该数据特征值执行筛选查询"],
        "已删除数据不再被命中，列表与统计结果一致",
        "P1",
        source="fallback",
    )

    for f in fields[:80]:
        fname = _field_name(f)
        if not fname:
            continue
        validation = _str(f, "validation")
        required = _bool(f, "required")
        min_len = _int(f, "min_len")
        max_len = _int(f, "max_len")
        if required:
            _add_case(
                f"字段校验-{fname}-必填",
                [f"进入包含{fname}的表单", f"将{fname}置空后提交"],
                f"系统提示{fname}必填并阻止提交",
                "P1",
                source="field_rule",
            )
        if min_len is not None or max_len is not None:
            _add_case(
                f"字段校验-{fname}-长度边界",
                [f"输入最小/最大边界值并提交（min={min_len}, max={max_len}）"],
                f"{fname}长度边界处理符合预期，越界值被拦截或提示",
                "P1",
                source="field_rule",
            )
        if not _is_empty_rule(validation):
            _add_case(
                f"字段校验-{fname}-规则",
                [f"输入不符合规则的{fname}并提交"],
                f"系统对{fname}给出明确校验提示并阻止无效提交",
                "P1",
                source="field_rule",
            )

    _emit("done", f"生成完成，共 {len(cases)} 条用例", history_id=history_id, generated_count=len(cases))
    return cases
