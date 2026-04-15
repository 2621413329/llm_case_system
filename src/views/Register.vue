<template>
  <div class="auth-page">
    <div class="auth-card">
      <div class="auth-brand">LLM 用例生成系统</div>
      <h1 class="auth-title">注册账号</h1>
      <p class="auth-sub">注册后将自动登录，默认权限为「操作员」角色。</p>

      <div v-if="closedMsg" class="auth-err auth-err--block">{{ closedMsg }}</div>

      <form v-else @submit.prevent="onSubmit">
        <div class="auth-field">
          <label class="auth-label" for="reg-user">用户名</label>
          <div class="auth-input-wrap">
            <input
              id="reg-user"
              v-model="username"
              class="auth-input"
              type="text"
              autocomplete="username"
              placeholder="字母开头，字母数字下划线"
            />
          </div>
        </div>
        <p class="auth-hint">3–64 个字符，以英文字母开头，仅含字母、数字、下划线。</p>

        <div class="auth-field">
          <label class="auth-label" for="reg-name">姓名</label>
          <div class="auth-input-wrap">
            <input
              id="reg-name"
              v-model="displayName"
              class="auth-input"
              type="text"
              autocomplete="name"
              placeholder="真实姓名或显示名称"
            />
          </div>
        </div>
        <p class="auth-hint">1–40 个字符，不可为空，支持中文。</p>

        <div class="auth-field">
          <label class="auth-label" for="reg-pass">密码</label>
          <div class="auth-input-wrap">
            <input
              id="reg-pass"
              v-model="password"
              class="auth-input"
              type="password"
              autocomplete="new-password"
              placeholder="8–128 位"
            />
          </div>
        </div>
        <p class="auth-hint">须同时包含至少一个字母和一个数字。</p>

        <div class="auth-field">
          <label class="auth-label" for="reg-pass2">确认密码</label>
          <div class="auth-input-wrap">
            <input
              id="reg-pass2"
              v-model="password2"
              class="auth-input"
              type="password"
              autocomplete="new-password"
              placeholder="再次输入密码"
            />
          </div>
        </div>

        <p v-if="errorMsg" class="auth-err auth-err--block">{{ errorMsg }}</p>

        <button type="submit" class="auth-btn-primary" :disabled="submitting">
          {{ submitting ? '提交中…' : '注册' }}
        </button>
      </form>

      <div class="auth-footer">
        <span>已有账号？</span>
        <router-link to="/login" class="auth-link">去登录</router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '../stores/auth';
import './auth-shared.css';

const USERNAME_RE = /^[a-zA-Z][a-zA-Z0-9_]{2,63}$/;

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

const username = ref('');
const displayName = ref('');
const password = ref('');
const password2 = ref('');
const errorMsg = ref('');
const submitting = ref(false);

function resolveAuthorizedHome() {
  if (auth.can('menu.system.list')) return '/systems';
  if (auth.can('menu.case.execution')) return '/case-execution';
  if (auth.can('menu.case.management')) return '/case-management';
  return '/login';
}

const closedMsg = computed(() => {
  if (!auth.authEnabled) return '当前未启用数据库认证，无需注册。';
  if (!auth.allowRegister) return '管理员已关闭自助注册，请联系管理员开通账号。';
  return '';
});

function validateClient() {
  const u = username.value.trim();
  if (!USERNAME_RE.test(u)) {
    return '用户名格式不正确：须 3–64 位，英文字母开头，仅含字母、数字、下划线。';
  }
  const name = displayName.value.trim();
  if (name.length < 1 || name.length > 40) {
    return '姓名须为 1–40 个字符。';
  }
  const p = password.value;
  if (p.length < 8 || p.length > 128) {
    return '密码长度须为 8–128 位。';
  }
  if (!/[A-Za-z]/.test(p) || !/\d/.test(p)) {
    return '密码须同时包含至少一个字母和一个数字。';
  }
  if (p !== password2.value) {
    return '两次输入的密码不一致。';
  }
  return '';
}

async function onSubmit() {
  errorMsg.value = '';
  const v = validateClient();
  if (v) {
    errorMsg.value = v;
    return;
  }
  submitting.value = true;
  try {
    await auth.register({
      username: username.value.trim(),
      password: password.value,
      display_name: displayName.value.trim(),
    });
    const raw = route.query.redirect;
    const redir = Array.isArray(raw) ? raw[0] : raw;
    const path = typeof redir === 'string' && redir.startsWith('/') ? redir : resolveAuthorizedHome();
    await router.replace(path);
  } catch (e) {
    errorMsg.value = e?.message || '注册失败';
  } finally {
    submitting.value = false;
  }
}
</script>
