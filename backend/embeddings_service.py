from __future__ import annotations

import os
import hashlib

import numpy as np


_MODEL = None
_MODEL_NAME = None


def _provider() -> str:
    """
    默认使用“轻量哈希向量”，保证构建网络库不会因为首次下载模型而卡死。
    如需更高质量 embedding，显式设置：
      VECTOR_EMBEDDING_PROVIDER=sentence_transformers
      VECTOR_EMBEDDING_MODEL=...
    """
    return (os.getenv("VECTOR_EMBEDDING_PROVIDER") or "hash").strip().lower()


def _get_default_model() -> str:
    # 默认一个中文/多语言效果相对不错的轻量模型
    # 如需替换可在环境变量 VECTOR_EMBEDDING_MODEL 指定。
    return os.getenv("VECTOR_EMBEDDING_MODEL") or "paraphrase-multilingual-MiniLM-L12-v2"


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


def _hash_embed(texts: list[str], *, dim: int = 384) -> list[list[float]]:
    """
    零依赖、快速的“向量化占位实现”。
    - 使用字符 n-gram + 哈希桶构建向量
    - 向量 L2 归一化，便于余弦相似度检索
    """
    dim = int(dim) if dim else 384
    out: list[list[float]] = []
    for t in texts:
        t = str(t or "")
        if not t:
            out.append([0.0] * dim)
            continue
        vec = np.zeros((dim,), dtype=np.float32)
        grams = [t[i : i + 3] for i in range(0, max(1, len(t) - 2))]
        for g in grams:
            h = int(hashlib.sha1(g.encode("utf-8")).hexdigest(), 16)
            idx = h % dim
            vec[idx] += 1.0
        n = float(np.linalg.norm(vec))
        if n > 0:
            vec = vec / n
        out.append(vec.tolist())
    return out


def embed_texts(texts: list[str], *, model_name: str | None = None, batch_size: int = 16) -> tuple[list[list[float]], str]:
    """
    返回 (embeddings, model_name)
    embeddings: list of vectors
    """
    texts = [str(t or "").strip() for t in texts]
    if not texts:
        return [], (model_name or "").strip() or _get_default_model()
    # 保持输入长度一致：空内容也给一个占位，避免调用方对齐出错
    texts = [t if t else " " for t in texts]

    provider = _provider()
    if provider not in ["sentence_transformers", "st"]:
        dim = int(os.getenv("VECTOR_HASH_DIM") or 384)
        return _hash_embed(texts, dim=dim), "hash"

    # provider=sentence_transformers：走真实 embedding（首次下载可能较慢）
    embedder = get_embedder(model_name)
    model_used = _MODEL_NAME or _get_default_model()

    vecs = embedder.encode(
        texts,
        batch_size=batch_size,
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

