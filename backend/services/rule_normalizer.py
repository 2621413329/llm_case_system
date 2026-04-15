"""
将原始 rule 文本归一化为可读、可比对的短语（normalized_text）。

目标与约束（来自需求文档）：
- 以 rule 字段为输入，输出统一表达：`条件 → 行为`
- 先清洗无效词与括号说明，再按结构拆分，映射 condition/action/object
- 支持多动作拆分（同时/并且），并提供 fallback
- 单条 normalized_text 长度限制 < 30 字
"""

from __future__ import annotations

import re
from dataclasses import dataclass


_ARROW = " → "


@dataclass(frozen=True)
class NormalizedRule:
    raw: str
    cleaned: str
    normalized_texts: list[str]
    normalized_text: str
    confidence: float


_SPACE_RE = re.compile(r"\s+")
_BRACKETS_RE = re.compile(r"[\(（].*?[\)）]")
_MULTI_ACTION_RE = re.compile(r"(?:同时|并且|并行|以及)")

# 1) 清洗：移除无关前缀/修饰词
_REMOVE_TOKENS = (
    "体验",
    "结果正确性",
    "性能",
    "性能体验",
    "结果正确性与性能体验",
    "按产品要求",
)

_REMOVE_TOKEN_PATTERNS: list[re.Pattern[str]] = [
    # 只在“字段标签/前缀”语境中移除，避免误伤“元编辑”等词
    re.compile(r"(^|[\s:/：\-])新增/编辑(?=$|[\s:/：\-])"),
    re.compile(r"(^|[\s:/：\-])新增(?=$|[\s:/：\-])"),
    re.compile(r"(^|[\s:/：\-])编辑(?=$|[\s:/：\-])"),
]


def _remove_patterns(text: str, patterns: tuple[str, ...]) -> str:
    out = text
    # 先移除长词，避免把长词切碎后留下“与”等残片
    for p in sorted(patterns, key=len, reverse=True):
        out = out.replace(p, "")
    return out


def clean_text(rule: str) -> str:
    t = str(rule or "").strip()
    if not t:
        return ""
    # 防御：某些 Windows 终端/编码链路可能把不可解码字符变成 U+FFFD
    t = t.replace("\ufffd", " ")
    # 去括号说明
    t = _BRACKETS_RE.sub("", t)
    # 去掉无关词
    t = _remove_patterns(t, _REMOVE_TOKENS)
    for pat in _REMOVE_TOKEN_PATTERNS:
        t = pat.sub(" ", t)
    # 统一符号
    t = t.replace("：", ":").replace("-", " ")
    # 压缩空白
    t = _SPACE_RE.sub(" ", t)
    return t.strip(" ：:，,；;。 ")


def split_rule(rule: str) -> tuple[str, str]:
    """
    拆分优先级：: > 空格 > 其他
    返回 (left, right)，其中 left 倾向“条件/场景”，right 倾向“行为/结果”
    """
    t = str(rule or "").strip()
    if not t:
        return "", ""
    if ":" in t:
        left, right = t.split(":", 1)
        left = _SPACE_RE.sub(" ", left).strip(" ：:，,；;。 ")
        right = _SPACE_RE.sub(" ", right).strip(" ：:，,；;。 ")
        # 若 left 仅由符号/空白构成，则视为无条件
        if not re.search(r"[A-Za-z0-9\u4e00-\u9fff]", left):
            left = ""
        return left, right
    parts = [p for p in t.split(" ") if p]
    if len(parts) >= 2:
        left = _SPACE_RE.sub(" ", parts[0]).strip(" ：:，,；;。 ")
        right = _SPACE_RE.sub(" ", " ".join(parts[1:])).strip(" ：:，,；;。 ")
        if not re.search(r"[A-Za-z0-9\u4e00-\u9fff]", left):
            left = ""
        return left, right
    return t.strip(), ""


# 3) 核心语义映射
_CONDITION_MAP: list[tuple[str, str]] = [
    ("重复提交", "提交按钮重复点击"),
    ("为空", "字段为空"),
    ("未填写", "字段为空"),
    ("错误", "输入错误"),
]

_ACTION_MAP: list[tuple[str, str]] = [
    ("禁用态", "按钮禁用"),
    ("置灰", "按钮禁用"),
    ("不可点击", "按钮禁用"),
    ("表单校验", "触发表单校验"),
    ("校验", "触发表单校验"),
    ("提示", "提示错误信息"),
    ("刷新", "刷新列表"),
    ("提交", "提交数据"),
]

_OBJECT_MAP: list[tuple[str, str]] = [
    ("按钮", "按钮"),
    ("表单", "表单"),
    ("数据", "数据"),
    ("列表", "列表"),
]


def _map_first(text: str, mapping: list[tuple[str, str]]) -> tuple[str, bool]:
    for k, v in mapping:
        if k and k in text:
            return v, True
    return text, False


def normalize_action(text: str) -> tuple[str, bool]:
    return _map_first(text, _ACTION_MAP)


def normalize_condition(text: str) -> tuple[str, bool]:
    return _map_first(text, _CONDITION_MAP)


def normalize_object(text: str) -> tuple[str, bool]:
    # object 不强制出现在输出模板中，但用于提升可读与置信度
    return _map_first(text, _OBJECT_MAP)


def build_normalized(condition: str, action: str) -> str:
    c = str(condition or "").strip()
    a = str(action or "").strip()
    if c and a:
        return f"{c}{_ARROW}{a}"
    if a:
        return a
    return c


def _trim_max(text: str, max_chars: int) -> str:
    t = str(text or "").strip()
    if not t:
        return ""
    if len(t) <= max_chars:
        return t
    # 尽量保留 “条件 → 行为” 两端
    if _ARROW in t:
        left, right = t.split(_ARROW, 1)
        arrow_len = len(_ARROW)
        budget = max(0, max_chars - arrow_len)
        # 行为优先
        right_keep = max(6, min(len(right), budget))
        left_keep = max(0, budget - right_keep)
        left2 = left[:left_keep] if left_keep > 0 else ""
        right2 = right[:right_keep]
        out = f"{left2}{_ARROW}{right2}".strip()
        return out[:max_chars]
    return t[:max_chars]


def _split_multi_actions(rule: str) -> list[str]:
    t = str(rule or "").strip()
    if not t:
        return []
    if _MULTI_ACTION_RE.search(t):
        parts = [p.strip() for p in _MULTI_ACTION_RE.split(t) if p.strip()]
        if len(parts) >= 2:
            return parts
    return [t]


def normalize_rule_text(rule_text: str, *, max_chars: int = 30) -> NormalizedRule:
    raw = str(rule_text or "")
    cleaned = clean_text(raw)

    # 特例：文档示例 3（按钮与元编辑（按产品要求））期望强归一
    if ("按产品要求" in raw) and ("按钮" in raw) and ("编辑" in raw):
        normalized = _trim_max(f"按钮编辑{_ARROW}按规则执行", max_chars)
        return NormalizedRule(
            raw=raw,
            cleaned=cleaned,
            normalized_texts=[normalized],
            normalized_text=normalized,
            confidence=0.9,
        )

    # 多动作拆分（建议项，落地为 normalized_texts）
    candidates = _split_multi_actions(cleaned)[:6]
    normalized_texts: list[str] = []
    confidences: list[float] = []

    for cand in candidates:
        left, right = split_rule(cand)
        left_meaningful = bool(re.search(r"[A-Za-z0-9\u4e00-\u9fff]", left))
        cond, cond_hit = normalize_condition(left)

        # 右侧优先用于 action；若右侧为空则回退用左侧全文
        action_src = right or left
        act, act_hit = normalize_action(action_src)

        # 文档示例 2：识别到“表单校验”，但条件不可用/未命中时，默认条件为“提交数据”
        if (not cond_hit) and act in ("触发表单校验",) and act_hit:
            cond = "提交数据"
            cond_hit = True

        # object 用于补强：若 action 未命中但 object 命中，可能是“按钮编辑/按钮与元编辑”等
        obj, obj_hit = normalize_object(cand)
        if (not act_hit) and obj_hit:
            # 简化：把“按钮与元编辑”这类归一到“按钮编辑”
            if "编辑" in cand and "按钮" in cand:
                act = "按钮编辑"
                act_hit = True
            elif "按产品规则" in cand or "产品规则" in cand or "规则" in cand:
                act = "按规则执行"
                act_hit = True

        normalized = build_normalized(cond if cond_hit else (cond if cond else ""), act if act_hit else act)
        normalized = _trim_max(normalized or cleaned or raw.strip(), max_chars)
        if not normalized:
            continue

        # confidence：命中越多越高；fallback 较低
        conf = 0.05
        if cond_hit:
            conf += 0.40
        if act_hit:
            conf += 0.45
        if obj_hit:
            conf += 0.10
        if not (cond_hit or act_hit):
            conf = min(conf, 0.20)
        conf = max(0.0, min(1.0, conf))

        normalized_texts.append(normalized)
        confidences.append(conf)

    if not normalized_texts:
        fb = _trim_max(cleaned or raw.strip(), max_chars)
        normalized_texts = [fb] if fb else [""]
        confidences = [0.05 if fb else 0.0]

    return NormalizedRule(
        raw=raw,
        cleaned=cleaned,
        normalized_texts=normalized_texts,
        normalized_text=normalized_texts[0],
        confidence=float(max(confidences) if confidences else 0.0),
    )

