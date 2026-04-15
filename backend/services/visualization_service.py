"""
需求向量可视化：2D 降维（t-SNE / UMAP / PCA）、基于余弦相似度的语义邻接图。
"""

from __future__ import annotations

import re
from typing import Any

import numpy as np

# 与方案一致：按类型区分相似边阈值（余弦，向量已 L2 归一化时等价于点积）
DEFAULT_TYPE_THRESHOLDS: dict[str, float] = {
    "interaction": 0.7,
    "data": 0.75,
    "style": 0.8,
    "default": 0.72,
}

# Cross-page weighting:
# 1) Different page_leaf => strong proportional penalty.
# 2) If cross-page data-linkage is detected, recover part of the score.
DIFF_PAGE_PENALTY = 0.32
DIFF_PAGE_RECOVER_BASE = 0.56
DIFF_PAGE_RECOVER_MAX = 0.9
DIFF_PAGE_LINKAGE_BONUS = 0.05
SAME_PAGE_LINKAGE_BONUS = 0.02

_KV_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=([^;]+)")
_TOKEN_SPLIT_RE = re.compile(r"[\s,.;:|/\\>\-_=，。；：、（）()\[\]{}]+")
_TOKEN_VALID_RE = re.compile(r"^[A-Za-z0-9\u4e00-\u9fff]{2,40}$")
_LINKAGE_TYPE_HINTS = ("data_", "cross_page_link", "interaction_rule", "vector_analysis_rule", "requirement_rule")
_LINKAGE_TEXT_HINTS = (
    "cross_page",
    "data_flow",
    "联动",
    "上游",
    "下游",
    "upstream",
    "downstream",
    "impact",
    "target",
)
_LINKAGE_KV_KEYS = (
    "action",
    "target",
    "impact",
    "data_object",
    "trigger",
    "from_field",
    "to_field",
    "relation",
    "rule",
    "requirement",
    "name",
    "element",
)


def _category_for_unit_type(unit_type: str) -> str:
    ut = str(unit_type or "").lower()
    if "interaction" in ut:
        return "interaction"
    if ut.startswith("style") or "style" in ut:
        return "style"
    if ut.startswith("data") or "data" in ut or ut in ("element",):
        return "data"
    return "default"


def threshold_for_unit_type(unit_type: str, overrides: dict[str, float] | None = None) -> float:
    cat = _category_for_unit_type(unit_type)
    o = overrides or {}
    if cat in o:
        return float(o[cat])
    if "default" in o:
        return float(o["default"])
    return DEFAULT_TYPE_THRESHOLDS.get(cat, DEFAULT_TYPE_THRESHOLDS["default"])


def _parse_kv(content: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in _KV_RE.findall(str(content or "")):
        kk = str(k or "").strip().lower()
        vv = str(v or "").strip()
        if kk and vv and kk not in out:
            out[kk] = vv
    return out


def _extract_page_leaf(node: dict[str, Any]) -> str:
    page = str(node.get("page_leaf") or "").strip()
    if page:
        return page
    kv = _parse_kv(str(node.get("content") or ""))
    return str(kv.get("page_leaf") or "").strip()


def _tokenize_value(text: str) -> set[str]:
    out: set[str] = set()
    for part in _TOKEN_SPLIT_RE.split(str(text or "")):
        p = str(part or "").strip().casefold()
        if not p:
            continue
        if _TOKEN_VALID_RE.fullmatch(p):
            out.add(p)
    return out


def _is_linkage_type(unit_type: str) -> bool:
    ut = str(unit_type or "").strip().lower()
    return any(ut.startswith(h) or ut == h for h in _LINKAGE_TYPE_HINTS)


def _extract_linkage_terms(node: dict[str, Any]) -> set[str]:
    content = str(node.get("content") or "")
    kv = _parse_kv(content)
    out: set[str] = set()
    for k in _LINKAGE_KV_KEYS:
        v = kv.get(k)
        if v:
            out.update(_tokenize_value(v))
    if not out:
        out.update(_tokenize_value(content))
    return out


def _linkage_strength(node_a: dict[str, Any], node_b: dict[str, Any]) -> float:
    uta = str(node_a.get("unit_type") or "")
    utb = str(node_b.get("unit_type") or "")
    if not (_is_linkage_type(uta) and _is_linkage_type(utb)):
        return 0.0

    ta = _extract_linkage_terms(node_a)
    tb = _extract_linkage_terms(node_b)
    if not ta or not tb:
        return 0.0

    inter = ta.intersection(tb)
    if not inter:
        return 0.0

    denom = float(max(1, min(len(ta), len(tb))))
    strength = min(1.0, float(len(inter)) / denom)

    low_a = str(node_a.get("content") or "").casefold()
    low_b = str(node_b.get("content") or "").casefold()
    if any(h in low_a or h in low_b for h in _LINKAGE_TEXT_HINTS):
        strength = min(1.0, strength + 0.12)
    return strength


def _weighted_similarity(node_a: dict[str, Any], node_b: dict[str, Any], raw_similarity: float) -> float:
    s = float(max(0.0, min(1.0, raw_similarity)))
    pa = _extract_page_leaf(node_a)
    pb = _extract_page_leaf(node_b)
    linkage = _linkage_strength(node_a, node_b)

    if pa and pb and pa != pb:
        penalized = s * DIFF_PAGE_PENALTY
        if linkage <= 1e-8:
            return penalized
        # Recover part of the score when cross-page data linkage is real.
        recover_ratio = DIFF_PAGE_RECOVER_BASE + (DIFF_PAGE_RECOVER_MAX - DIFF_PAGE_RECOVER_BASE) * linkage
        recovered = s * recover_ratio + DIFF_PAGE_LINKAGE_BONUS * linkage
        return float(max(penalized, min(1.0, recovered)))

    if linkage > 1e-8:
        return float(min(1.0, s + SAME_PAGE_LINKAGE_BONUS * linkage))
    return s


def reduce_embeddings_to_2d(
    vectors: np.ndarray,
    *,
    method: str = "tsne",
    random_state: int = 42,
) -> tuple[np.ndarray, str]:
    """
    将 (n, dim) 向量降为 (n, 2)。样本过少时用 PCA；t-SNE 失败时回退 PCA。
    返回 (coords, method_used)。
    """
    if vectors.size == 0:
        return np.zeros((0, 2), dtype=np.float64), method
    n = int(vectors.shape[0])
    if n == 1:
        return np.array([[0.0, 0.0]], dtype=np.float64), "singleton"
    if n == 2:
        return np.array([[0.0, 0.0], [1.0, 0.0]], dtype=np.float64), "two_points"

    X = np.asarray(vectors, dtype=np.float64)
    m = str(method or "tsne").strip().lower()

    if m == "umap":
        try:
            import umap  # type: ignore

            reducer = umap.UMAP(n_components=2, random_state=random_state, metric="cosine")
            return np.asarray(reducer.fit_transform(X), dtype=np.float64), "umap"
        except Exception:
            m = "tsne"

    if m == "tsne" and n >= 4:
        try:
            from sklearn.manifold import TSNE  # type: ignore

            perplexity = max(5.0, min(30.0, float(n - 1)))
            tsne = TSNE(
                n_components=2,
                random_state=random_state,
                perplexity=perplexity,
                init="random",
                learning_rate="auto",
            )
            return np.asarray(tsne.fit_transform(X), dtype=np.float64), "tsne"
        except Exception:
            pass

    from sklearn.decomposition import PCA  # type: ignore

    k = min(2, n - 1, X.shape[1])
    pca = PCA(n_components=k, random_state=random_state)
    Y = np.asarray(pca.fit_transform(X), dtype=np.float64)
    if k == 1:
        Y = np.column_stack([Y[:, 0], np.zeros(n, dtype=np.float64)])
    return Y, "pca"


def build_similarity_graph(
    units: list[dict[str, Any]],
    embeddings: dict[str, list[float]],
    *,
    thresholds: dict[str, float] | None = None,
    max_edges: int = 8000,
    top_k_per_node: int = 16,
    max_nodes: int = 600,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    基于余弦相似度（归一化向量点积）在 unit 之间建边。
    返回 (nodes, edges)，edges 含 similarity、threshold_used。
    """
    nodes: list[dict[str, Any]] = []
    keys: list[str] = []
    rows: list[list[float]] = []
    for u in units:
        if not isinstance(u, dict):
            continue
        uk = str(u.get("unit_key") or "").strip()
        if not uk:
            continue
        emb = embeddings.get(uk)
        if not isinstance(emb, list) or len(emb) < 2:
            continue
        try:
            vec = np.asarray([float(x) for x in emb], dtype=np.float32)
        except Exception:
            continue
        norm = float(np.linalg.norm(vec))
        if norm < 1e-8:
            continue
        vec = vec / norm
        keys.append(uk)
        rows.append(vec.tolist())
        nodes.append(
            {
                "unit_key": uk,
                "unit_type": str(u.get("unit_type") or "other"),
                "content": str(u.get("content") or ""),
                "page_leaf": _parse_kv(str(u.get("content") or "")).get("page_leaf") or "",
            }
        )

    n = len(keys)
    if n < 2:
        for node in nodes:
            node["x"] = 0.5
            node["y"] = 0.5
        return nodes, []

    # --- 限流：节点过多会导致 KNN 也变慢；优先保留（稳定采样） ---
    if max_nodes and n > int(max_nodes):
        # 稳定采样：按 unit_key 排序截断，避免每次刷新抖动
        order = sorted(range(n), key=lambda i: str(keys[i]))
        order = order[: int(max_nodes)]
        nodes = [nodes[i] for i in order]
        keys = [keys[i] for i in order]
        rows = [rows[i] for i in order]
        n = len(keys)

    edges: list[dict[str, Any]] = []
    type_by_key = {nodes[i]["unit_key"]: nodes[i]["unit_type"] for i in range(len(nodes))}
    node_by_key = {nodes[i]["unit_key"]: nodes[i] for i in range(len(nodes))}
    best_sim_by_key: dict[str, float] = {}

    # --- KNN 近邻建边：避免 O(n^2) 全矩阵 ---
    mat = np.asarray(rows, dtype=np.float32)
    try:
        from sklearn.neighbors import NearestNeighbors  # type: ignore

        k = max(2, min(int(top_k_per_node) + 1, n))
        nn = NearestNeighbors(n_neighbors=k, metric="cosine", algorithm="auto")
        nn.fit(mat)
        dists, idxs = nn.kneighbors(mat, n_neighbors=k, return_distance=True)
    except Exception:
        # fallback：小规模时用点积矩阵
        sim = mat @ mat.T
        dists = None
        idxs = None

    seen_pairs: set[tuple[int, int]] = set()
    if idxs is not None and dists is not None:
        for i in range(n):
            ut_i = type_by_key.get(keys[i], "")
            th_i = threshold_for_unit_type(ut_i, thresholds)
            best_sim_i: float | None = None
            for rank in range(1, min(k, len(idxs[i]))):
                j = int(idxs[i][rank])
                if j == i or j < 0 or j >= n:
                    continue
                a, b = (i, j) if i < j else (j, i)
                if (a, b) in seen_pairs:
                    continue
                seen_pairs.add((a, b))
                raw_s = float(1.0 - float(dists[i][rank]))
                s = _weighted_similarity(node_by_key[keys[a]], node_by_key[keys[b]], raw_s)
                if best_sim_i is None or s > best_sim_i:
                    best_sim_i = s
                ut_j = type_by_key.get(keys[j], "")
                th_j = threshold_for_unit_type(ut_j, thresholds)
                th = max(th_i, th_j)
                if s >= th:
                    edges.append(
                        {
                            "from_unit_key": keys[a],
                            "to_unit_key": keys[b],
                            "similarity": s,
                            "raw_similarity": raw_s,
                            "threshold_used": th,
                            "relation_type": "semantic_similarity",
                        }
                    )
                if len(edges) >= max_edges:
                    break
            if len(edges) >= max_edges:
                break
            if best_sim_i is not None:
                best_sim_by_key[keys[i]] = float(best_sim_i)
    else:
        # fallback matrix
        sim = mat @ mat.T
        for i in range(n):
            ut_i = type_by_key.get(keys[i], "")
            th_i = threshold_for_unit_type(ut_i, thresholds)
            best_sim_i: float | None = None
            for j in range(i + 1, n):
                raw_s = float(sim[i, j])
                s = _weighted_similarity(node_by_key[keys[i]], node_by_key[keys[j]], raw_s)
                if best_sim_i is None or s > best_sim_i:
                    best_sim_i = s
                ut_j = type_by_key.get(keys[j], "")
                th_j = threshold_for_unit_type(ut_j, thresholds)
                th = max(th_i, th_j)
                if s >= th:
                    edges.append(
                        {
                            "from_unit_key": keys[i],
                            "to_unit_key": keys[j],
                            "similarity": s,
                            "raw_similarity": raw_s,
                            "threshold_used": th,
                            "relation_type": "semantic_similarity",
                        }
                    )
                if len(edges) >= max_edges:
                    break
            if len(edges) >= max_edges:
                break
            if best_sim_i is not None:
                best_sim_by_key[keys[i]] = float(best_sim_i)

    edges.sort(key=lambda e: -float(e.get("similarity") or 0))

    # 前端绘图：用向量前两维做归一化平面布局（与「嵌入分布」不同，此处仅作语义网布局）
    emb_coords: list[list[float]] = []
    for nk in keys:
        ev = embeddings.get(nk)
        if isinstance(ev, list) and len(ev) >= 2:
            emb_coords.append([float(ev[0]), float(ev[1])])
        else:
            emb_coords.append([0.0, 0.0])
    ec = np.asarray(emb_coords, dtype=np.float64)
    lo = np.min(ec, axis=0)
    hi = np.max(ec, axis=0)
    span = np.maximum(hi - lo, 1e-9)
    z = (ec - lo) / span
    margin = 0.06
    for i, node in enumerate(nodes):
        node["x"] = float(margin + z[i, 0] * (1.0 - 2.0 * margin))
        node["y"] = float(margin + (1.0 - z[i, 1]) * (1.0 - 2.0 * margin))
        uk = str(node.get("unit_key") or "").strip()
        if uk and uk in best_sim_by_key:
            node["best_similarity"] = float(best_sim_by_key[uk])

    return nodes, edges


def compute_best_similarity_by_key(
    *,
    embeddings: dict[str, list[float]],
    keys: list[str],
) -> dict[str, float]:
    """
    为给定 keys 计算“best_similarity”（与任一其它节点的最大余弦相似度）。
    主要用于前端详情弹窗展示；当节点来自 network graph / graph-all（非 similarity-graph）时补齐该字段。
    """
    out: dict[str, float] = {}
    uniq = [str(k or "").strip() for k in keys if str(k or "").strip()]
    if len(uniq) < 2:
        return out

    rows: list[list[float]] = []
    kept: list[str] = []
    for k in uniq:
        emb = embeddings.get(k)
        if not isinstance(emb, list) or len(emb) < 2:
            continue
        try:
            v = np.asarray([float(x) for x in emb], dtype=np.float32)
        except Exception:
            continue
        n = float(np.linalg.norm(v))
        if n < 1e-8:
            continue
        rows.append((v / n).tolist())
        kept.append(k)

    n = len(kept)
    if n < 2:
        return out

    # 这里直接用点积矩阵（mat 已归一化），稳定且避免 KNN/self-neighbor 的实现差异。
    # n 默认 <= 800（graph-all 的 limit_units），该复杂度可接受。
    mat = np.asarray(rows, dtype=np.float32)
    sim = mat @ mat.T
    # 排除自身
    np.fill_diagonal(sim, -1.0)
    best = np.max(sim, axis=1)
    for i in range(n):
        out[kept[i]] = float(best[i])
    return out


def normalize_xy_for_svg(xy: np.ndarray, margin: float = 0.06) -> np.ndarray:
    """映射到 [margin, 1-margin] 便于前端 SVG。"""
    if xy.size == 0:
        return xy
    lo = np.min(xy, axis=0)
    hi = np.max(xy, axis=0)
    span = np.maximum(hi - lo, 1e-9)
    z = (xy - lo) / span
    return margin + z * (1.0 - 2.0 * margin)
