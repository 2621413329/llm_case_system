const TOKEN_KEY = 'llm_session_token';

/**
 * 将相对路径 /api、/uploads 指到后端。
 * - 开发/预览：通常由 Vite proxy 转发，无需设置。
 * - 无代理时（例如静态站直连后端）：在项目根建 `.env.local` 写一行：
 *   VITE_API_ORIGIN=http://127.0.0.1:5000
 */
function resolveApiUrl(url) {
  const u = String(url || '');
  if (!u || /^https?:\/\//i.test(u)) return u;
  let origin = '';
  try {
    origin =
      typeof import.meta !== 'undefined' && import.meta.env?.VITE_API_ORIGIN
        ? String(import.meta.env.VITE_API_ORIGIN).replace(/\/$/, '')
        : '';
  } catch {
    origin = '';
  }
  if (!origin) return u;
  if (u.startsWith('/api') || u.startsWith('/uploads')) {
    return `${origin}${u}`;
  }
  return u;
}

async function parseJsonSafe(resp) {
  return resp.json().catch(() => ({}));
}

function mapStatusToMessage(status, fallback) {
  if (status === 400) return '请求参数不正确';
  if (status === 401) return '请登录';
  if (status === 403) return '没有操作权限';
  if (status === 404) return '请求的资源不存在';
  if (status === 409) return '数据冲突，请刷新后重试';
  if (status === 422) return '提交数据校验失败';
  if (status === 429) return '请求过于频繁，请稍后重试';
  if (status >= 500) return '服务暂时不可用，请稍后重试';
  return fallback || `HTTP ${status}`;
}

function buildError(status, data, fallback) {
  const backendMsg = data && typeof data === 'object' ? (data.error || data.message) : '';
  const msg = backendMsg || mapStatusToMessage(status, fallback);
  return new Error(String(msg));
}

export function getStoredToken() {
  try {
    return localStorage.getItem(TOKEN_KEY) || '';
  } catch {
    return '';
  }
}

export function setStoredToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // ignore
  }
}

const AUTH_FLASH_KEY = 'llm_auth_flash';

let unauthorizedHandler = null;

/** 在 pinia 就绪后注册，用于 401 时同步清空 store */
export function setUnauthorizedHandler(fn) {
  unauthorizedHandler = typeof fn === 'function' ? fn : null;
}

function shouldAttachAuth(url) {
  const u = String(url || '');
  if (u.includes('/api/auth/login') || u.includes('/api/auth/register')) return false;
  return true;
}

export async function authFetch(url, options = {}) {
  const resolved = resolveApiUrl(url);
  const headers = new Headers(options.headers || {});
  if (shouldAttachAuth(url)) {
    const t = getStoredToken();
    if (t) headers.set('Authorization', `Bearer ${t}`);
  }
  const resp = await fetch(resolved, { ...options, headers });
  const u = String(url || '');
  const skip401Redirect =
    u.includes('/api/auth/login')
    || u.includes('/api/auth/register')
    || u.includes('/api/auth/config');
  if (resp.status === 401 && !skip401Redirect && typeof window !== 'undefined') {
    setStoredToken('');
    try {
      sessionStorage.setItem(AUTH_FLASH_KEY, '请登录');
    } catch {
      // ignore
    }
    try {
      if (unauthorizedHandler) unauthorizedHandler();
    } catch {
      // ignore
    }
    const h = window.location.hash || '';
    if (!h.includes('login') && !h.includes('register')) {
      window.location.hash = '#/login';
    }
  }
  return resp;
}

/** SSE 无法设置 Header，认证开启时用 query 传递 token */
export function sseUrlWithAuth(baseUrl) {
  const resolved = resolveApiUrl(baseUrl);
  const t = getStoredToken();
  if (!t) return resolved;
  const sep = resolved.includes('?') ? '&' : '?';
  return `${resolved}${sep}token=${encodeURIComponent(t)}`;
}

/**
 * 使用 fetch 消费 text/event-stream（可带 Authorization，避免 EventSource 无法设头导致 401/403 只能报「连接异常」）。
 * @param {string} url 同源相对路径即可
 * @param {Record<string, (data: object) => void>} handlers 按 event 名回调，如 { phase, log, done, error }
 * @param {{ signal?: AbortSignal }} [options]
 */
export async function streamSse(url, handlers, options = {}) {
  const resp = await authFetch(url, { signal: options.signal });
  if (!resp.ok) {
    const data = await parseJsonSafe(resp);
    throw buildError(resp.status, data, 'SSE 请求失败');
  }
  const ct = (resp.headers.get('content-type') || '').toLowerCase();
  if (!ct.includes('text/event-stream')) {
    const text = await resp.text().catch(() => '');
    throw new Error(text.slice(0, 240) || '服务端未返回事件流（text/event-stream）');
  }
  const reader = resp.body?.getReader();
  if (!reader) {
    throw new Error('浏览器不支持流式读取响应');
  }
  const decoder = new TextDecoder('utf-8', { fatal: false });
  let buf = '';
  let currentEvent = 'message';
  const dataLines = [];
  /** 服务端若 keep-alive 且不关连接，ReadableStream 不会结束；收到 terminal 事件后主动结束，避免 UI 永远卡在「执行中」 */
  const terminalEvents = new Set(
    Array.isArray(options.endOnEvents) && options.endOnEvents.length
      ? options.endOnEvents
      : ['done'],
  );
  let sawTerminal = false;

  const flushEvent = () => {
    if (dataLines.length === 0) return;
    const raw = dataLines.join('\n');
    dataLines.length = 0;
    const evt = currentEvent;
    currentEvent = 'message';
    let payload = {};
    if (raw) {
      try {
        payload = JSON.parse(raw);
      } catch {
        payload = { _raw: raw };
      }
    }
    const fn = handlers[evt];
    if (typeof fn === 'function') fn(payload);
    if (terminalEvents.has(evt)) sawTerminal = true;
  };

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        flushEvent();
        break;
      }
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split(/\r?\n/);
      buf = lines.pop() ?? '';
      for (const line of lines) {
        if (line === '') {
          flushEvent();
          if (sawTerminal) return;
          continue;
        }
        if (line.startsWith('event:')) {
          currentEvent = line.slice(6).trim() || 'message';
        } else if (line.startsWith('data:')) {
          dataLines.push(line.slice(5).trimStart());
        }
      }
      if (sawTerminal) return;
    }
  } finally {
    try {
      await reader.cancel();
    } catch {
      // ignore
    }
  }
}

export async function postJson(url, payload = {}) {
  const resp = await authFetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload ?? {}),
  });
  const data = await parseJsonSafe(resp);
  if (!resp.ok) throw buildError(resp.status, data, '请求失败');
  return data;
}

export async function getJson(url, fallback = '请求失败') {
  const resp = await authFetch(url);
  const data = await parseJsonSafe(resp);
  if (!resp.ok) throw buildError(resp.status, data, fallback);
  return data;
}
