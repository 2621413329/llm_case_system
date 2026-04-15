"""
从合并后的配置（default.yaml + local 覆盖 + 环境变量）解析各类模型名与相关参数。
业务代码中不要硬编码模型 ID，统一由此模块从配置读取。
"""
from __future__ import annotations

from typing import Any

# 兼容模式根地址：仅在各配置块均未写 base_url 时使用（非「模型名」）
DEFAULT_DASHSCOPE_COMPAT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"


def _s(v: Any) -> str:
    return v.strip() if isinstance(v, str) and v.strip() else ""


def dashscope_compat_base_url(cfg: dict[str, Any]) -> str:
    o = cfg.get("ocr") if isinstance(cfg.get("ocr"), dict) else {}
    ds = o.get("dashscope") if isinstance(o.get("dashscope"), dict) else {}
    u = _s(ds.get("base_url"))
    if u:
        return u
    a = cfg.get("analysis") if isinstance(cfg.get("analysis"), dict) else {}
    for key in ("case_generation", "llm_vision"):
        sub = a.get(key) if isinstance(a.get(key), dict) else {}
        u = _s(sub.get("base_url"))
        if u:
            return u
    return DEFAULT_DASHSCOPE_COMPAT_BASE_URL


def llm_vision_model(cfg: dict[str, Any]) -> str:
    a = cfg.get("analysis") if isinstance(cfg.get("analysis"), dict) else {}
    lv = a.get("llm_vision") if isinstance(a.get("llm_vision"), dict) else {}
    return _s(lv.get("model"))


def case_generation_model(cfg: dict[str, Any]) -> str:
    a = cfg.get("analysis") if isinstance(cfg.get("analysis"), dict) else {}
    cg = a.get("case_generation") if isinstance(a.get("case_generation"), dict) else {}
    m = _s(cg.get("model"))
    if m:
        return m
    return llm_vision_model(cfg)


def ocr_dashscope_model(cfg: dict[str, Any]) -> str:
    o = cfg.get("ocr") if isinstance(cfg.get("ocr"), dict) else {}
    ds = o.get("dashscope") if isinstance(o.get("dashscope"), dict) else {}
    return _s(ds.get("model"))


def embedding_model(cfg: dict[str, Any]) -> str:
    e = cfg.get("embedding") if isinstance(cfg.get("embedding"), dict) else {}
    return _s(e.get("model"))


def embed_batch_size(cfg: dict[str, Any]) -> int:
    e = cfg.get("embedding") if isinstance(cfg.get("embedding"), dict) else {}
    raw = e.get("batch_size", 32)
    try:
        return max(8, int(raw))
    except (TypeError, ValueError):
        return 32
