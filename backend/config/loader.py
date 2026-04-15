from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"
DEFAULT_YAML_PATH = CONFIG_DIR / "default.yaml"
LOCAL_YAML_PATH = CONFIG_DIR / "local.yaml"
LOCAL_JSON_PATH = CONFIG_DIR / "local.json"
LEGACY_LOCAL_JSON_PATH = PROJECT_ROOT / "config.local.json"

_CACHE: dict[str, Any] | None = None
_CACHE_FINGERPRINT: tuple[tuple[str, int], ...] | None = None


def _safe_mtime(path: Path) -> int:
    try:
        if not path.exists():
            return -1
        return int(path.stat().st_mtime_ns)
    except Exception:
        return -1


def _fingerprint(paths: list[Path]) -> tuple[tuple[str, int], ...]:
    return tuple((str(p), _safe_mtime(p)) for p in paths)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        import yaml  # type: ignore
    except Exception:
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _set_nested(data: dict[str, Any], dotted_key: str, value: Any) -> None:
    keys = [x for x in dotted_key.split(".") if x]
    if not keys:
        return
    node: dict[str, Any] = data
    for k in keys[:-1]:
        cur = node.get(k)
        if not isinstance(cur, dict):
            cur = {}
            node[k] = cur
        node = cur
    node[keys[-1]] = value


def _apply_env_overrides(data: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(data)
    mappings: list[tuple[str, str, Any]] = [
        ("MYSQL_HOST", "mysql.host", str),
        ("MYSQL_PORT", "mysql.port", int),
        ("MYSQL_USER", "mysql.user", str),
        ("MYSQL_PASSWORD", "mysql.password", str),
        ("MYSQL_DATABASE", "mysql.database", str),
        ("MYSQL_ENABLED", "mysql.enabled", str),
        ("AUTH_ENABLED", "auth.enabled", str),
        ("AUTH_ALLOW_REGISTER", "auth.allow_register", str),
        ("OCR_PROVIDER", "ocr.provider", str),
        ("DASHSCOPE_API_KEY", "ocr.dashscope.api_key", str),
        ("DASHSCOPE_BASE_URL", "ocr.dashscope.base_url", str),
        ("DASHSCOPE_MODEL", "ocr.dashscope.model", str),
        ("LLM_VISION_ENABLED", "analysis.llm_vision.enabled", int),
        ("LLM_VISION_MODEL", "analysis.llm_vision.model", str),
        ("LLM_VISION_API_KEY", "analysis.llm_vision.api_key", str),
        ("CASE_GEN_ENABLED", "analysis.case_generation.enabled", int),
        ("CASE_GEN_MODEL", "analysis.case_generation.model", str),
        ("CASE_GEN_API_KEY", "analysis.case_generation.api_key", str),
        ("CASE_GEN_REQUEST_TIMEOUT", "analysis.case_generation.request_timeout", int),
        ("VECTOR_EMBEDDING_MODEL", "embedding.model", str),
        ("VECTOR_EMBED_BATCH_SIZE", "embedding.batch_size", int),
    ]
    for env_name, cfg_key, caster in mappings:
        raw = os.getenv(env_name)
        if raw is None or raw == "":
            continue
        try:
            value = caster(raw)
        except Exception:
            value = raw
        if cfg_key.endswith(".enabled"):
            value = bool(int(raw)) if str(raw).strip().isdigit() else str(raw).strip().lower() in {"1", "true", "yes", "on"}
        elif cfg_key == "auth.allow_register":
            value = bool(int(raw)) if str(raw).strip().isdigit() else str(raw).strip().lower() in {"1", "true", "yes", "on"}
        _set_nested(out, cfg_key, value)
    return out


def load_config(*, force_reload: bool = False) -> dict[str, Any]:
    global _CACHE, _CACHE_FINGERPRINT
    watched = [DEFAULT_YAML_PATH, LOCAL_YAML_PATH, LOCAL_JSON_PATH, LEGACY_LOCAL_JSON_PATH]
    fp = _fingerprint(watched)
    if not force_reload and _CACHE is not None and _CACHE_FINGERPRINT == fp:
        return copy.deepcopy(_CACHE)

    merged: dict[str, Any] = {}
    # 优先级：default.yaml < config.local.json < local.yaml < local.json < ENV
    merged = _deep_merge(merged, _read_yaml(DEFAULT_YAML_PATH))
    merged = _deep_merge(merged, _read_json(LEGACY_LOCAL_JSON_PATH))
    merged = _deep_merge(merged, _read_yaml(LOCAL_YAML_PATH))
    merged = _deep_merge(merged, _read_json(LOCAL_JSON_PATH))
    merged = _apply_env_overrides(merged)

    _CACHE = merged
    _CACHE_FINGERPRINT = fp
    return copy.deepcopy(merged)


def clear_config_cache() -> None:
    global _CACHE, _CACHE_FINGERPRINT
    _CACHE = None
    _CACHE_FINGERPRINT = None
