import { postJson } from './http';

export async function listCases(params = {}) {
  const data = await postJson('/api/cases/list', params);
  return Array.isArray(data) ? data : [];
}

export async function getCaseDetail(id) {
  return postJson('/api/cases/detail', { id: Number(id) });
}

export async function createCase(payload) {
  return postJson('/api/cases/create', payload || {});
}

export async function updateCase(id, payload) {
  return postJson('/api/cases/update', { id: Number(id), ...(payload || {}) });
}

export async function deleteCaseById(id) {
  return postJson('/api/cases/delete', { id: Number(id) });
}
