<template>
  <div class="auth-page">
    <div class="auth-card">
      <div class="auth-brand">LLM 用例生成系统</div>
      <h1 class="auth-title">登录</h1>
      <p class="auth-sub">请输入用户名与密码。默认管理员在数据库首次初始化后可用。</p>

      <form @submit.prevent="onSubmit">
        <div class="auth-field">
          <label class="auth-label" for="login-user">用户名</label>
          <div class="auth-input-wrap">
            <input
              id="login-user"
              v-model="username"
              class="auth-input"
              type="text"
              autocomplete="username"
              placeholder="字母开头，3–64 位"
              required
            />
          </div>
        </div>
        <div class="auth-field">
          <label class="auth-label" for="login-pass">密码</label>
          <div class="auth-input-wrap">
            <input
              id="login-pass"
              v-model="password"
              class="auth-input"
              type="password"
              autocomplete="current-password"
              placeholder="请输入密码"
              required
            />
          </div>
        </div>

        <p v-if="errorMsg" class="auth-err auth-err--block">{{ errorMsg }}</p>

        <button type="submit" class="auth-btn-primary" :disabled="submitting">
          {{ submitting ? '登录中…' : '登录' }}
        </button>
      </form>

      <div class="auth-footer">
        <span v-if="auth.allowRegister">没有账号？</span>
        <router-link v-if="auth.allowRegister" to="/register" class="auth-link">注册</router-link>
        <span v-else class="auth-sub" style="margin:0;">自助注册已关闭，请联系管理员</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '../stores/auth';
import './auth-shared.css';

const AUTH_FLASH_KEY = 'llm_auth_flash';

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

const username = ref('');
const password = ref('');
const errorMsg = ref('');
const submitting = ref(false);

function resolveAuthorizedHome() {
  if (auth.can('menu.system.list')) return '/systems';
  if (auth.can('menu.case.execution')) return '/case-execution';
  if (auth.can('menu.case.management')) return '/case-management';
  return '/login';
}

onMounted(() => {
  try {
    const flash = sessionStorage.getItem(AUTH_FLASH_KEY);
    if (flash) {
      errorMsg.value = flash;
      sessionStorage.removeItem(AUTH_FLASH_KEY);
    }
  } catch {
    // ignore
  }
  const q = route.query.msg;
  const msg = Array.isArray(q) ? q[0] : q;
  if (typeof msg === 'string' && msg.trim() && !errorMsg.value) {
    errorMsg.value = decodeURIComponent(msg.trim());
  }
});

async function onSubmit() {
  errorMsg.value = '';
  submitting.value = true;
  try {
    await auth.login(username.value.trim(), password.value);
    const raw = route.query.redirect;
    const redir = Array.isArray(raw) ? raw[0] : raw;
    const path = typeof redir === 'string' && redir.startsWith('/') ? redir : resolveAuthorizedHome();
    await router.replace(path);
  } catch (e) {
    errorMsg.value = e?.message || '登录失败';
  } finally {
    submitting.value = false;
  }
}
</script>
