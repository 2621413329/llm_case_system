import { postJson } from './http';

export async function buildRequirementNetwork(payload) {
  return postJson('/api/requirement/network/build', payload || {});
}

export async function analyzeRequirementVector(historyId, systemId = null) {
  const body = { history_id: Number(historyId) };
  if (systemId != null && systemId !== '') {
    body.system_id = Number(systemId);
  }
  return postJson('/api/requirement/vector/analyze', body);
}

export async function previewRequirementNetworkBuild(historyId, systemId = null) {
  const body = { history_id: Number(historyId) };
  if (systemId != null && systemId !== '') {
    body.system_id = Number(systemId);
  }
  return postJson('/api/requirement/network/preview', body);
}

export async function searchRequirementNetwork(payload) {
  return postJson('/api/requirement/network/search', payload || {});
}

/** 需求网络图：节点（含 embedding）与边，用于向量图页可视化 */
export async function fetchRequirementNetworkGraph(historyId, systemId = null) {
  const body = { history_id: Number(historyId) };
  if (systemId != null && systemId !== '') {
    body.system_id = Number(systemId);
  }
  return postJson('/api/requirement/network/graph', body);
}

/** 需求网络图：全量聚合（跨多个 history） */
export async function fetchRequirementNetworkGraphAll(payload) {
  return postJson('/api/requirement/network/graph-all', payload || {});
}

/** 2D 降维散点（t-SNE/UMAP/PCA） */
export async function fetchEmbeddings2d(payload) {
  return postJson('/api/requirement/viz/embeddings-2d', payload);
}

/** 余弦相似度语义网络 */
export async function fetchSimilarityGraph(payload) {
  return postJson('/api/requirement/viz/similarity-graph', payload);
}

/** 记录级相似度（多 history 聚合） */
export async function fetchRecordSimilarity(payload) {
  return postJson('/api/requirement/viz/record-similarity', payload || {});
}

/** 检索调试：query → topK */
export async function debugVectorQuery(payload) {
  return postJson('/api/requirement/debug/vector-query', payload);
}

/** 向量库对账：列出已写入网络的 history_id 统计 */
export async function fetchRequirementNetworkCounts(payload) {
  return postJson('/api/requirement/network/counts', payload || {});
}
