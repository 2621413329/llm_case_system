import { createRouter, createWebHashHistory } from 'vue-router';
import { getStoredToken } from '../api/http';
import { useAuthStore } from '../stores/auth';

/** 无需 token 即可访问，其余路由在认证启用时均须已登录且本地有 token。 */
const PUBLIC_ROUTE_NAMES = new Set(['login', 'register']);

function resolveAuthorizedHome(auth) {
  if (auth.can('menu.system.list')) return '/systems';
  if (auth.can('menu.case.execution')) return '/case-execution';
  if (auth.can('menu.case.management')) return '/case-management';
  return '/login';
}

const routes = [
  {
    path: '/',
    redirect: '/systems',
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/Login.vue'),
    meta: { requiresSystem: false },
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('../views/Register.vue'),
    meta: { requiresSystem: false },
  },
  {
    path: '/systems',
    name: 'systems',
    component: () => import('../components/SystemManagement.vue'),
    // 系统管理页的“是否允许编辑/删除”在前端/后端分别做更细粒度控制
    // 这里放宽路由级 permission，避免普通用户仅有部分系统权限时被守卫挡住。
    meta: { group: 'system', requiresSystem: false },
  },
  {
    path: '/upload',
    name: 'upload',
    component: () => import('../components/UploadScreenshot.vue'),
    meta: { group: 'analysis', requiresSystem: true, permission: 'menu.analysis.upload' },
  },
  {
    path: '/requirement-library',
    name: 'requirement-library',
    component: () => import('../components/RequirementAnalysisLibrary.vue'),
    props: { mode: 'replica' },
    meta: { group: 'analysis', requiresSystem: true, permission: 'menu.analysis.requirement_library' },
  },
  {
    path: '/requirement-vector-graph',
    name: 'requirement-vector-graph',
    component: () => import('../components/RequirementVectorGraph.vue'),
    meta: { group: 'analysis', requiresSystem: true, permission: 'menu.analysis.requirement_library' },
  },
  {
    path: '/requirement-library-replica',
    redirect: '/requirement-library',
  },
  {
    path: '/screenshot-gallery',
    name: 'screenshot-gallery',
    component: () => import('../components/ScreenshotGallery.vue'),
    meta: { group: 'preview', requiresSystem: true, permission: 'menu.preview.gallery' },
  },
  {
    path: '/case-management',
    name: 'case-management',
    component: () => import('../components/CaseManagement.vue'),
    props: { initialTab: 'generate' },
    meta: { group: 'case', requiresSystem: true, permission: 'menu.case.management' },
  },
  {
    path: '/case-execution',
    name: 'case-execution',
    component: () => import('../components/CaseManagement.vue'),
    props: { initialTab: 'preview', onlyExecution: true },
    meta: { group: 'case', requiresSystem: false, permission: 'menu.case.execution' },
  },
];

const router = createRouter({
  history: createWebHashHistory(),
  routes,
});

router.beforeEach(async (to, from, next) => {
  const auth = useAuthStore();
  await auth.ensureBootstrapped();
  const isPublic = to.name != null && PUBLIC_ROUTE_NAMES.has(String(to.name));
  const requiresAuthenticatedSession = !isPublic && auth.authEnabled;

  if (isPublic) {
    if (auth.authEnabled && auth.user && getStoredToken()) {
      next({ path: resolveAuthorizedHome(auth) });
      return;
    }
    next();
    return;
  }

  if (requiresAuthenticatedSession) {
    const t = getStoredToken();
    if (!t || !auth.user) {
      try {
        sessionStorage.setItem('llm_auth_flash', '请登录');
      } catch {
        // ignore
      }
      next({ name: 'login', query: { redirect: to.fullPath } });
      return;
    }
  }

  const perm = to.meta?.permission;
  if (perm && !auth.can(perm)) {
    next({ path: resolveAuthorizedHome(auth) });
    return;
  }
  next();
});

export default router;
