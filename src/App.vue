<template>
  <div class="app">
    <!-- 顶部导航栏 -->
    <header class="header">
      <div class="logo">LLM 用例生成系统</div>
      <div class="user-info">
        <span>管理员</span>
        <button>设置</button>
        <button>退出</button>
      </div>
    </header>
    
    <!-- 主容器 -->
    <div class="main-container">
      <!-- 左侧导航 -->
      <aside class="sidebar">
        <!-- 一级菜单：分析系统 -->
        <div class="menu-item" :class="{ active: isActiveGroup('analysis') }" @click="toggleMenu('analysis')">
          <span class="menu-icon">🔍</span>
          <span class="menu-text">分析系统</span>
          <span class="menu-arrow" :class="{ collapsed: !menuOpen.analysis }">{{ menuOpen.analysis ? '▼' : '▶' }}</span>
        </div>
        <div class="sub-menu" :class="{ expanded: menuOpen.analysis }">
          <div class="menu-item" :class="{ active: currentPage === 'upload' }" @click="navigateTo('upload')">
            <span class="menu-icon">📷</span>
            <span class="menu-text">上传系统样式截图</span>
          </div>
          <div class="menu-item" :class="{ active: currentPage === 'llm-analysis' }" @click="navigateTo('llm-analysis')">
            <span class="menu-icon">🤖</span>
            <span class="menu-text">LLM分析系统交互</span>
          </div>
          <div class="menu-item" :class="{ active: currentPage === 'requirement-library' }" @click="navigateTo('requirement-library')">
            <span class="menu-icon">📚</span>
            <span class="menu-text">系统需求分析库</span>
          </div>
          <div class="menu-item" :class="{ active: isActiveGroup('manual') }" @click="toggleMenu('manual')">
            <span class="menu-icon">✏️</span>
            <span class="menu-text">手动补录</span>
            <span class="menu-arrow" :class="{ collapsed: !menuOpen.manual }">{{ menuOpen.manual ? '▼' : '▶' }}</span>
          </div>
          <div class="sub-menu" :class="{ expanded: menuOpen.manual }">
            <div class="menu-item" :class="{ active: currentPage === 'page-elements-input' }" @click="navigateTo('page-elements-input')">
              <span class="menu-icon">🧩</span>
              <span class="menu-text">页面元素补充</span>
            </div>
          </div>
        </div>
        
        <!-- 二级菜单：系统预览 -->
        <div class="menu-item" :class="{ active: isActiveGroup('preview') }" @click="toggleMenu('preview')">
          <span class="menu-icon">👁️</span>
          <span class="menu-text">系统预览</span>
          <span class="menu-arrow" :class="{ collapsed: !menuOpen.preview }">{{ menuOpen.preview ? '▼' : '▶' }}</span>
        </div>
        <div class="sub-menu" :class="{ expanded: menuOpen.preview }">
          <div class="menu-item" :class="{ active: currentPage === 'screenshot-gallery' }" @click="navigateTo('screenshot-gallery')">
            <span class="menu-icon">🖼️</span>
            <span class="menu-text">截图预览</span>
          </div>
        </div>

        <!-- 一级菜单：用例管理 -->
        <div class="menu-item" :class="{ active: isActiveGroup('case') }" @click="toggleMenu('case')">
          <span class="menu-icon">🧾</span>
          <span class="menu-text">用例管理</span>
          <span class="menu-arrow" :class="{ collapsed: !menuOpen.case }">{{ menuOpen.case ? '▼' : '▶' }}</span>
        </div>
        <div class="sub-menu" :class="{ expanded: menuOpen.case }">
          <div class="menu-item" :class="{ active: currentPage === 'case-management' }" @click="navigateTo('case-management')">
            <span class="menu-icon">📚</span>
            <span class="menu-text">用例管理</span>
          </div>
          <div class="menu-item" :class="{ active: currentPage === 'case-execution' }" @click="navigateTo('case-execution')">
            <span class="menu-icon">▶️</span>
            <span class="menu-text">执行用例</span>
          </div>
        </div>
      </aside>
      
      <!-- 右侧内容区 -->
      <main class="content">
        <!-- 上传系统样式截图模块 -->
        <UploadScreenshot v-if="currentPage === 'upload'" />
        
        <!-- LLM 分析系统交互模块 -->
        <LLMAnalysis v-else-if="currentPage === 'llm-analysis'" />

        <!-- 系统需求分析库模块 -->
        <RequirementAnalysisLibrary v-else-if="currentPage === 'requirement-library'" />
        
        <!-- 手动补录模块 -->
        <ManualInput v-else-if="currentPage === 'page-elements-input'" type="page-elements-input" />
        
        <!-- 截图预览模块 -->
        <ScreenshotGallery v-else-if="currentPage === 'screenshot-gallery'" />

        <!-- 用例管理模块 -->
        <CaseManagement v-else-if="currentPage === 'case-management'" initial-tab="generate" />
        <CaseManagement v-else-if="currentPage === 'case-execution'" initial-tab="preview" :only-execution="true" />
      </main>
    </div>
    <DialogHost />
  </div>
</template>

<script setup>
import { ref } from 'vue';
import UploadScreenshot from './components/UploadScreenshot.vue';
import LLMAnalysis from './components/LLMAnalysis.vue';
import RequirementAnalysisLibrary from './components/RequirementAnalysisLibrary.vue';
import ManualInput from './components/ManualInput.vue';
import ScreenshotGallery from './components/ScreenshotGallery.vue';
import CaseManagement from './components/CaseManagement.vue';
import DialogHost from './components/DialogHost.vue';

const currentPage = ref('upload');
const menuOpen = ref({
  analysis: true,
  manual: false,
  preview: false,
  case: true,
});

const toggleMenu = (menu) => {
  menuOpen.value[menu] = !menuOpen.value[menu];
};

const navigateTo = (page) => {
  currentPage.value = page;
};

const isActiveGroup = (group) => {
  if (group === 'analysis') return ['upload', 'llm-analysis', 'requirement-library'].includes(currentPage.value);
  if (group === 'manual') return ['page-elements-input'].includes(currentPage.value);
  if (group === 'preview') return ['screenshot-gallery'].includes(currentPage.value);
  if (group === 'case') return ['case-management', 'case-execution'].includes(currentPage.value);
  return false;
};
</script>

<style scoped>
.app {
  min-height: 100vh;
}
</style>
