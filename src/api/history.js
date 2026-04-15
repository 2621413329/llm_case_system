import { postJson } from './http';

export async function listHistory(params = {}) {
  const data = await postJson('/api/history/list', params);
  return Array.isArray(data) ? data : [];
}

export async function getHistoryDetail(id) {
  return postJson('/api/history/detail', { id: Number(id) });
}

export async function createHistory(payload) {
  return postJson('/api/history/create', payload || {});
}

export async function updateHistory(id, payload) {
  return postJson('/api/history/update', { id: Number(id), ...(payload || {}) });
}

export async function deleteHistory(id) {
  return postJson('/api/history/delete', { id: Number(id) });
}
