<template>
  <div class="app-root">
    <router-view v-if="isLoginRoute" />
    <el-container v-else class="app-shell">
      <el-header class="app-header">
        <div class="header-left">
          <el-button text class="collapse-btn" @click="collapsed = !collapsed">
            <el-icon><Fold v-if="!collapsed" /><Expand v-else /></el-icon>
          </el-button>
          <div class="brand" @click="$router.push('/')">LLM 用例生成系统</div>
          <el-tag v-if="systemStore.selectedSystem" type="info" effect="light" class="sys-tag">
            当前系统：<b>{{ systemStore.systemName }}</b>
          </el-tag>
        </div>

        <div class="header-right" v-if="authStore.authEnabled && authStore.user">
          <el-dropdown trigger="click">
            <span class="user-trigger">
              <el-avatar :size="28">{{ (authStore.displayName || 'U').slice(0, 1) }}</el-avatar>
              <span class="user-name">{{ authStore.displayName || '—' }}</span>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="onLogout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-container class="app-body">
        <el-aside :width="collapsed ? '72px' : '248px'" class="app-aside">
          <el-scrollbar class="aside-scroll">
            <div v-if="systemStore.selectedSystem && activeGroup !== 'system' && nav.showSystemList" class="sys-switch">
              <el-button
                type="primary"
                plain
                size="small"
                style="width: 100%; justify-content: flex-start;"
                @click="$router.push('/systems')"
              >
                <el-icon><Setting /></el-icon>
                <span v-if="!collapsed" class="sys-switch-text">{{ systemStore.systemName }}</span>
                <span v-if="!collapsed" class="sys-switch-action">切换</span>
              </el-button>
            </div>

            <el-menu
              :default-active="String(route.name || '')"
              :collapse="collapsed"
              :collapse-transition="false"
              class="app-menu"
            >
              <el-sub-menu v-if="nav.systemGroup" index="grp-system">
                <template #title>
                  <el-icon><Setting /></el-icon>
                  <span>系统管理</span>
                </template>
                <el-menu-item v-if="nav.showSystemList" index="systems" @click="$router.push('/systems')">
                  <el-icon><Document /></el-icon>
                  <span>系统列表</span>
                </el-menu-item>
              </el-sub-menu>

              <el-sub-menu v-if="nav.analysisGroup" index="grp-analysis" :disabled="!systemStore.selectedSystem">
                <template #title>
                  <el-icon><Search /></el-icon>
                  <span>分析系统</span>
                </template>
                <el-menu-item v-if="nav.upload" index="upload" @click="$router.push('/upload')">
                  <el-icon><Upload /></el-icon>
                  <span>上传系统样式需求</span>
                </el-menu-item>
                <el-menu-item v-if="nav.requirementLib" index="requirement-library" @click="$router.push('/requirement-library')">
                  <el-icon><Collection /></el-icon>
                  <span>系统需求分析库</span>
                </el-menu-item>
                <el-menu-item v-if="nav.vectorGraph" index="requirement-vector-graph" @click="$router.push('/requirement-vector-graph')">
                  <el-icon><Share /></el-icon>
                  <span>需求向量图</span>
                </el-menu-item>
              </el-sub-menu>

              <el-sub-menu v-if="nav.previewGroup" index="grp-preview" :disabled="!systemStore.selectedSystem">
                <template #title>
                  <el-icon><View /></el-icon>
                  <span>系统预览</span>
                </template>
                <el-menu-item v-if="nav.gallery" index="screenshot-gallery" @click="$router.push('/screenshot-gallery')">
                  <el-icon><Picture /></el-icon>
                  <span>需求预览</span>
                </el-menu-item>
              </el-sub-menu>

              <el-sub-menu v-if="nav.caseGroup" index="grp-case" :disabled="caseMenuDisabled">
                <template #title>
                  <el-icon><Tickets /></el-icon>
                  <span>用例管理</span>
                </template>
                <el-menu-item v-if="nav.caseMgmt" index="case-management" @click="$router.push('/case-management')">
                  <el-icon><Management /></el-icon>
                  <span>用例管理</span>
                </el-menu-item>
                <el-menu-item v-if="nav.caseExec" index="case-execution" @click="$router.push('/case-execution')">
                  <el-icon><VideoPlay /></el-icon>
                  <span>执行用例</span>
                </el-menu-item>
              </el-sub-menu>
            </el-menu>
          </el-scrollbar>
        </el-aside>

        <el-main class="app-main">
          <div v-if="!systemStore.selectedSystem && currentRouteMeta.requiresSystem" class="no-system">
            <el-card shadow="never" class="no-system-card">
              <el-empty description="请先选择一个系统">
                <template #description>
                  <div style="font-weight: 700; font-size: 16px;">请先选择一个系统</div>
                  <div class="no-system-desc">所有分析操作、需求管理、用例生成均需在指定系统下进行，以确保数据隔离。</div>
                </template>
                <el-button type="primary" @click="$router.push('/systems')">前往系统管理</el-button>
              </el-empty>
            </el-card>
          </div>
          <router-view v-else />
        </el-main>
      </el-container>
    </el-container>

    <DialogHost />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useSystemStore } from './stores/system';
import { useAuthStore } from './stores/auth';
import DialogHost from './components/DialogHost.vue';
import {
  ArrowDown,
  Collection,
  Document,
  Expand,
  Fold,
  Management,
  Picture,
  Search,
  Setting,
  Share,
  Tickets,
  Upload,
  VideoPlay,
  View,
} from '@element-plus/icons-vue';

const route = useRoute();
const router = useRouter();
const systemStore = useSystemStore();
const authStore = useAuthStore();

const isLoginRoute = computed(() => route.name === 'login' || route.name === 'register');

const nav = computed(() => ({
  // 系统管理页“标签页展示”允许普通用户基于系统列表或管理权限进入；
  // 新建/编辑/删除能力仍在 `SystemManagement.vue` 中更严格控制。
  systemGroup:
    authStore.can('menu.system')
    || authStore.can('menu.system.list')
    || authStore.can('menu.case')
    || authStore.can('menu.analysis')
    || authStore.can('menu.preview'),
  showSystemList:
    authStore.can('menu.system.list')
    || authStore.can('menu.case')
    || authStore.can('menu.analysis')
    || authStore.can('menu.preview'),
  analysisGroup:
    authStore.can('menu.analysis')
    && (authStore.can('menu.analysis.upload') || authStore.can('menu.analysis.requirement_library')),
  upload: authStore.can('menu.analysis.upload'),
  requirementLib: authStore.can('menu.analysis.requirement_library'),
  vectorGraph: authStore.can('menu.analysis.requirement_library'),
  previewGroup: authStore.can('menu.preview') && authStore.can('menu.preview.gallery'),
  gallery: authStore.can('menu.preview.gallery'),
  caseGroup:
    authStore.can('menu.case')
    && (authStore.can('menu.case.management') || authStore.can('menu.case.execution')),
  caseMgmt: authStore.can('menu.case.management'),
  caseExec: authStore.can('menu.case.execution'),
}));

const routeName = computed(() => route.name || '');
const currentRouteMeta = computed(() => route.meta || {});
const activeGroup = computed(() => route.meta?.group || '');
const caseMenuDisabled = computed(() => nav.value.caseMgmt && !systemStore.selectedSystem);

const collapsed = ref(false);

async function onLogout() {
  await authStore.logout();
  if (authStore.authEnabled) {
    await router.push({ name: 'login' });
  }
}
</script>

<style scoped>
.app-root {
  min-height: 100vh;
}

.app-shell {
  min-height: 100vh;
}

.app-header {
  height: var(--app-header-h);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  background: rgba(255, 255, 255, 0.78);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--app-border);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.collapse-btn {
  padding: 6px 8px;
}

.brand {
  font-weight: 800;
  letter-spacing: 0.02em;
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
}

.sys-tag {
  margin-left: 6px;
  max-width: 520px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.header-right {
  display: flex;
  align-items: center;
}

.user-trigger {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid var(--app-border);
  background: rgba(255, 255, 255, 0.8);
}

.user-name {
  font-size: 13px;
  font-weight: 600;
  color: #111827;
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.app-body {
  min-height: calc(100vh - var(--app-header-h));
}

.app-aside {
  border-right: 1px solid var(--app-border);
  background: rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(8px);
}

.aside-scroll {
  height: calc(100vh - var(--app-header-h));
}

.sys-switch {
  padding: 12px 12px 0;
}
.sys-switch-text {
  margin-left: 6px;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sys-switch-action {
  margin-left: auto;
  opacity: 0.75;
}

.app-menu {
  border-right: 0;
  background: transparent;
  padding: 6px 6px 10px;
}

.app-main {
  padding: var(--app-padding);
}

.no-system-card {
  border-radius: var(--app-radius);
}
.no-system-desc {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--app-muted);
}
</style>
