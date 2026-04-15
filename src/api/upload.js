import { authFetch } from './http';

export async function uploadScreenshot(file, { systemId } = {}) {
  const formData = new FormData();
  formData.append('file', file);
  let url = '/api/upload';
  if (systemId) url += `?system_id=${systemId}`;
  const response = await authFetch(url, {
    method: 'POST',
    body: formData,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const msg = (data && (data.error || data.message)) || `上传失败: ${response.status}`;
    throw new Error(String(msg));
  }
  return data;
}

export async function uploadAsset(file) {
  const formData = new FormData();
  formData.append('file', file);
  const response = await authFetch('/api/upload/asset', {
    method: 'POST',
    body: formData,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const msg = (data && (data.error || data.message)) || `上传失败: ${response.status}`;
    throw new Error(String(msg));
  }
  return data;
}
