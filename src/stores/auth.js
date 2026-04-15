import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { getJson, postJson, getStoredToken, setStoredToken } from '../api/http';

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null);
  const permissions = ref([]);
  const token = ref(getStoredToken());
  const authEnabled = ref(false);
  const requireLogin = ref(false);
  const allowRegister = ref(true);
  const bootstrapped = ref(false);

  /** 仅写入会话 token；用户与权限一律由服务端根据 token 在 refreshMe 中返回，不在本地单独持久化权限。 */
  function setSessionTokenFromResponse(data) {
    const tok = data?.token;
    if (tok) {
      setStoredToken(tok);
      token.value = tok;
    }
  }

  const displayName = computed(() => {
    const u = user.value;
    if (!u) return '';
    return String(u.display_name || u.username || '').trim() || u.username || '';
  });

  function can(code) {
    if (!authEnabled.value) return true;
    if (!code) return true;
    if (!user.value) return false;
    const p = permissions.value;
    if (Array.isArray(p) && p.includes('*')) return true;
    return Array.isArray(p) && p.includes(code);
  }

  async function loadConfig() {
    try {
      const c = await getJson('/api/auth/config');
      authEnabled.value = !!c.enabled;
      requireLogin.value = !!c.require_login;
      allowRegister.value = c.allow_register !== false;
    } catch {
      authEnabled.value = false;
      requireLogin.value = false;
      allowRegister.value = false;
    }
  }

  async function refreshMe() {
    const t = getStoredToken();
    token.value = t;
    if (!authEnabled.value) {
      user.value = null;
      permissions.value = [];
      return;
    }
    if (!t) {
      user.value = null;
      permissions.value = [];
      return;
    }
    try {
      const data = await getJson('/api/auth/me');
      user.value = data.user || null;
      permissions.value = Array.isArray(data.permissions) ? data.permissions : [];
      if (!data.user && t) {
        setStoredToken('');
        token.value = '';
      }
    } catch {
      user.value = null;
      permissions.value = [];
      setStoredToken('');
      token.value = '';
    }
  }

  async function ensureBootstrapped() {
    if (bootstrapped.value) return;
    await loadConfig();
    await refreshMe();
    bootstrapped.value = true;
  }

  async function login(username, password) {
    const data = await postJson('/api/auth/login', { username, password });
    setSessionTokenFromResponse(data);
    await refreshMe();
  }

  async function register(payload) {
    const data = await postJson('/api/auth/register', payload || {});
    setSessionTokenFromResponse(data);
    await refreshMe();
    return data;
  }

  /** 清空本地会话（不请求登出接口），用于 401 等场景 */
  function clearSession() {
    setStoredToken('');
    token.value = '';
    user.value = null;
    permissions.value = [];
  }

  async function logout() {
    try {
      await postJson('/api/auth/logout', {});
    } catch {
      // ignore
    }
    clearSession();
  }

  return {
    user,
    permissions,
    token,
    authEnabled,
    requireLogin,
    allowRegister,
    bootstrapped,
    displayName,
    can,
    loadConfig,
    refreshMe,
    ensureBootstrapped,
    login,
    register,
    logout,
    clearSession,
  };
});
