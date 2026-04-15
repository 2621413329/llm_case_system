from __future__ import annotations

import os

import numpy as np


_MODEL = None
_MODEL_NAME = None


def _get_default_model() -> str:
    try:
        from backend.config.loader import load_config
        from backend.config.model_resolve import embedding_model as _emb_model

        m = _emb_model(load_config())
        if m:
            return m
    except Exception:
        pass
    return os.getenv("VECTOR_EMBEDDING_MODEL") or ""


def _default_embed_batch_size() -> int:
    try:
        from backend.config.loader import load_config
        from backend.config.model_resolve import embed_batch_size as _emb_bs

        return _emb_bs(load_config())
    except Exception:
        pass
    try:
        return max(8, int(os.getenv("VECTOR_EMBED_BATCH_SIZE", "32")))
    except Exception:
        return 32


def get_embedder(model_name: str | None = None):
    """
    Lazy load: 避免启动时就加载模型导致阻塞。
    """
    global _MODEL, _MODEL_NAME
    model_name = (model_name or "").strip() or _get_default_model()
    if _MODEL is not None and _MODEL_NAME == model_name:
        return _MODEL

    # sentence-transformers 导入较慢；放到真正需要时再导入
    from sentence_transformers import SentenceTransformer  # type: ignore

    # 降低 tokenizer 并行带来的偶发资源问题
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

    _MODEL = SentenceTransformer(model_name)
    _MODEL_NAME = model_name
    return _MODEL


def embed_texts(
    texts: list[str], *, model_name: str | None = None, batch_size: int | None = None
) -> tuple[list[list[float]], str]:
    """
    返回 (embeddings, model_name)
    embeddings: list of vectors（Sentence-Transformers，L2 归一化）
    """
    stripped = [str(t or "").strip() for t in texts]
    if not stripped:
        return [], (model_name or "").strip() or _get_default_model()
    if not all(stripped):
        if not any(stripped):
            return [], (model_name or "").strip() or _get_default_model()
        raise ValueError("embed_texts: 不允许在同一次调用中混入空字符串与非空字符串，请在调用方对每条文本分别过滤")
    texts = stripped

    bs = int(batch_size) if batch_size is not None else _default_embed_batch_size()
    if bs < 1:
        bs = _default_embed_batch_size()

    embedder = get_embedder(model_name)
    model_used = _MODEL_NAME or _get_default_model()

    vecs = embedder.encode(
        texts,
        batch_size=bs,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    if isinstance(vecs, list):
        vecs = np.array(vecs, dtype=np.float32)
    vecs = np.asarray(vecs, dtype=np.float32)
    out = vecs.tolist()
    return out, model_used


def embed_one(text: str, *, model_name: str | None = None) -> tuple[list[float], str]:
    vecs, used = embed_texts([text], model_name=model_name)
    return (vecs[0] if vecs else []), used
