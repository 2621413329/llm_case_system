import { postJson, getJson } from './http';

export async function listSystems() {
  const data = await postJson('/api/systems/list', {});
  return Array.isArray(data) ? data : [];
}

export async function getSystemDetail(id) {
  return postJson('/api/systems/detail', { id: Number(id) });
}

export async function createSystem(payload) {
  return postJson('/api/systems/create', payload || {});
}

export async function updateSystem(id, payload) {
  return postJson('/api/systems/update', { id: Number(id), ...(payload || {}) });
}

export async function deleteSystem(id) {
  return postJson('/api/systems/delete', { id: Number(id) });
}
