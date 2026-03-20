#!/usr/bin/env python3
"""
可选：调用 DashScope OpenAI 兼容接口的多模态模型，基于截图生成测试向深度分析。
与 OCR（识字）解耦：OCR 模型专注提取文字；此处使用通用视觉语言模型做理解与归纳。
"""

from __future__ import annotations

import base64
import json
import mimetypes
import urllib.error
import urllib.request
from pathlib import Path


def dashscope_multimodal_completion(
    image_path: Path,
    api_key: str,
    base_url: str,
    model: str,
    system_prompt: str,
    user_text: str,
    *,
    timeout: int = 120,
) -> tuple[bool, str]:
    """
    返回 (ok, content_or_error_message)。
    """
    mime, _ = mimetypes.guess_type(str(image_path))
    mime = mime or "image/png"
    b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
    data_url = f"data:{mime};base64,{b64}"

    messages: list[dict] = []
    if system_prompt.strip():
        messages.append({"role": "system", "content": system_prompt.strip()})
    messages.append(
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": data_url}},
                {"type": "text", "text": user_text.strip()},
            ],
        }
    )

    payload = {"model": model, "messages": messages, "temperature": 0.3}

    req = urllib.request.Request(
        url=f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", errors="replace")
        except Exception:
            detail = ""
        return False, f"HTTP {e.code}: {detail[:800]}"
    except Exception as e:
        return False, str(e)

    try:
        choice0 = (data.get("choices") or [{}])[0]
        msg = choice0.get("message") or {}
        content = msg.get("content")
        if content is None:
            return False, "模型返回空 content"
        return True, str(content).strip()
    except Exception as e:
        return False, f"解析响应失败: {e}"


def build_visual_analysis_prompts(breadcrumb: str, file_name: str, ocr_excerpt: str) -> tuple[str, str]:
    """(system_prompt, user_text)"""
    system = (
        "你是资深软件测试工程师，擅长从界面截图提炼可执行的测试关注点。"
        "输出必须具体、可核对，避免空泛套话。使用简体中文。"
    )
    ocr_part = (ocr_excerpt or "").strip()
    if len(ocr_part) > 2000:
        ocr_part = ocr_part[:2000] + "\n…(OCR 摘录已截断)"

    user = f"""请结合截图，输出「测试向」结构化分析（Markdown）。

**已知上下文（可能不完整）**
- 文件名/路径推断菜单：{breadcrumb or "（无）"}
- 原始文件名：{file_name or "（无）"}
- OCR 摘录（可能有错漏，以画面为准）：
```
{ocr_part or "（暂无 OCR 文本）"}
```

**请按以下标题组织（二级标题用 ##）**
## 1. 页面类型与业务目标
（1-4 句：列表/表单/详情/弹窗/混合？用户主要完成什么任务？）

## 2. 界面区域与关键元素
（分区描述：表格区、筛选区、工具栏、表单字段、分页等；指出可见的标签与按钮名称。）

## 3. 关键用户路径与状态
（典型操作流、列表行操作、弹窗链路；若可见则提状态标签/Tab/步骤。）

## 4. 高风险与易漏测点
（权限、并发、重复提交、边界数据、空态、错误提示、导出/批量操作等。）

## 5. 建议测试用例方向
（5-12 条短句，每条可被直接改写成用例步骤；尽量具体。）

不要重复 OCR 原文；不要编造截图中明显不存在的按钮或字段名称。"""
    return system, user


def try_visual_analysis_for_screenshot(
    image_path: Path,
    api_key: str,
    base_url: str,
    model: str,
    breadcrumb: str,
    file_name: str,
    ocr_excerpt: str,
    *,
    timeout: int = 120,
) -> tuple[bool, str]:
    if not image_path.is_file():
        return False, "截图文件不存在"
    sys_p, user_p = build_visual_analysis_prompts(breadcrumb, file_name, ocr_excerpt)
    return dashscope_multimodal_completion(
        image_path,
        api_key,
        base_url,
        model,
        sys_p,
        user_p,
        timeout=timeout,
    )


def _extract_json_object(raw: str) -> tuple[bool, str]:
    s = (raw or "").strip()
    if not s:
        return False, "空响应"
    # 兼容 ```json ... ``` 包裹
    if "```" in s:
        parts = s.split("```")
        for p in parts:
            p2 = p.strip()
            if not p2:
                continue
            if p2.lower().startswith("json"):
                p2 = p2[4:].strip()
            if p2.startswith("{") and p2.endswith("}"):
                return True, p2
    l = s.find("{")
    r = s.rfind("}")
    if l >= 0 and r > l:
        return True, s[l : r + 1]
    return False, "未找到 JSON 对象"


def _normalize_button(btn: dict) -> dict:
    name = str(btn.get("name") or "").strip()
    action = str(btn.get("action") or "").strip().lower()
    if action not in {"query", "create", "edit", "delete", "open"}:
        action = "open"
    return {
        "name": name,
        "action": action,
        "opens_modal": bool(btn.get("opens_modal")),
        "requires_confirm": bool(btn.get("requires_confirm")),
    }


def _normalize_field(fd: dict) -> dict:
    name = str(fd.get("name") or "").strip()
    ftype = str(fd.get("type") or "").strip().lower()
    if ftype not in {"text", "number", "email", "phone", "date", "select"}:
        ftype = "text"
    return {
        "name": name,
        "type": ftype,
        "required": bool(fd.get("required")),
        "queryable": bool(fd.get("queryable")),
        "validation": str(fd.get("validation") or "").strip(),
        "min_len": fd.get("min_len", ""),
        "max_len": fd.get("max_len", ""),
        "options": fd.get("options") if isinstance(fd.get("options"), list) else [],
    }


def build_manual_extract_prompts(breadcrumb: str, file_name: str, ocr_excerpt: str) -> tuple[str, str]:
    system = (
        "你是资深测试分析师。请仅基于截图可见信息提取“可编辑补录草稿”。"
        "返回严格 JSON，不要输出任何解释、注释、Markdown。"
    )
    ocr_part = (ocr_excerpt or "").strip()
    if len(ocr_part) > 2500:
        ocr_part = ocr_part[:2500] + "\n...(截断)"
    user = f"""请识别截图中的页面类型、按钮、字段，输出一个 JSON 对象，结构固定如下：
{{
  "page_type": "list|form|detail|modal|unknown",
  "buttons": [
    {{"name":"按钮文本","action":"query|create|edit|delete|open","opens_modal":false,"requires_confirm":false}}
  ],
  "fields": [
    {{"name":"字段名","type":"text|number|email|phone|date|select","required":false,"queryable":false,"validation":"","min_len":"","max_len":"","options":[]}}
  ],
  "control_logic": "一句话，可为空"
}}

约束：
1) 仅输出 JSON；不要 markdown。
2) buttons 只保留截图中明显可点击的操作按钮，去掉菜单、面包屑、图标文字、分页数字。
3) 字段名尽量用界面可见标签，避免臆测。
4) 如果不确定 required/queryable，默认 false。

上下文：
- 菜单路径：{breadcrumb or "（无）"}
- 文件名：{file_name or "（无）"}
- OCR 摘录（可能有误）：{ocr_part or "（无）"}
"""
    return system, user


def try_extract_manual_from_screenshot(
    image_path: Path,
    api_key: str,
    base_url: str,
    model: str,
    breadcrumb: str,
    file_name: str,
    ocr_excerpt: str,
    *,
    timeout: int = 120,
) -> tuple[bool, dict | str]:
    if not image_path.is_file():
        return False, "截图文件不存在"
    sys_p, user_p = build_manual_extract_prompts(breadcrumb, file_name, ocr_excerpt)
    ok, text = dashscope_multimodal_completion(
        image_path,
        api_key,
        base_url,
        model,
        sys_p,
        user_p,
        timeout=timeout,
    )
    if not ok:
        return False, text
    ok_json, json_text = _extract_json_object(text)
    if not ok_json:
        return False, f"模型未返回 JSON: {json_text}"
    try:
        data = json.loads(json_text)
    except Exception as e:
        return False, f"JSON 解析失败: {e}"
    if not isinstance(data, dict):
        return False, "JSON 顶层不是对象"

    page_type = str(data.get("page_type") or "unknown").strip().lower()
    if page_type not in {"list", "form", "detail", "modal", "unknown"}:
        page_type = "unknown"

    out_buttons: list[dict] = []
    raw_buttons = data.get("buttons")
    if isinstance(raw_buttons, list):
        for b in raw_buttons:
            if isinstance(b, dict):
                nb = _normalize_button(b)
                if nb["name"] and len(nb["name"]) <= 20:
                    out_buttons.append(nb)
    # 去重
    dedup_btn: list[dict] = []
    seen_btn: set[str] = set()
    for b in out_buttons:
        key = b["name"]
        if key in seen_btn:
            continue
        seen_btn.add(key)
        dedup_btn.append(b)

    out_fields: list[dict] = []
    raw_fields = data.get("fields")
    if isinstance(raw_fields, list):
        for f in raw_fields:
            if isinstance(f, dict):
                nf = _normalize_field(f)
                if nf["name"] and len(nf["name"]) <= 30:
                    out_fields.append(nf)
    dedup_fields: list[dict] = []
    seen_fd: set[str] = set()
    for f in out_fields:
        key = f["name"]
        if key in seen_fd:
            continue
        seen_fd.add(key)
        dedup_fields.append(f)

    out = {
        "page_type": page_type,
        "buttons": dedup_btn[:20],
        "fields": dedup_fields[:40],
        "control_logic": str(data.get("control_logic") or "").strip(),
    }
    return True, out
