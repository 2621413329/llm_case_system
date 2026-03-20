<template>
  <div class="system-preview">
    <div class="page-header">
      <h1>系统预览</h1>
      <p>预览生成的系统菜单和页面</p>
    </div>
    
    <!-- 指定修改 -->
    <div v-if="type === 'specific-modification'">
      <div class="card">
        <h2>指定修改</h2>
        <div class="form-group">
          <label>历史快照</label>
          <div class="card-grid">
            <div class="element-card" v-for="(snapshot, index) in snapshots" :key="index">
              <h3>版本 {{ snapshot.version }}</h3>
              <p>{{ snapshot.description }}</p>
              <p>{{ snapshot.time }}</p>
              <button class="btn btn-default" style="width: 100%; margin-top: 8px;" @click="rollback(snapshot)">回滚</button>
            </div>
          </div>
        </div>
        
        <div style="display: flex; gap: 12px; margin-top: 16px;">
          <button class="btn btn-primary" @click="exportHtml">导出 HTML/CSS</button>
          <button class="btn btn-default" @click="saveSnapshot">保存快照</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { useUiDialog } from '../composables/useUiDialog';

const props = defineProps({
  type: {
    type: String,
    required: true
  }
});

// 快照数据
const snapshots = ref([
  {
    version: '1.0',
    description: '初始版本',
    time: '2026-03-17 10:00'
  }
]);
const { alertDialog } = useUiDialog();

const rollback = async (snapshot) => {
  await alertDialog(`回滚到版本 ${snapshot.version}`);
};

const exportHtml = async () => {
  await alertDialog('导出 HTML/CSS 文件');
};

const saveSnapshot = async () => {
  const newSnapshot = {
    version: (snapshots.value.length + 1).toFixed(1),
    description: '手动保存的快照',
    time: new Date().toLocaleString()
  };
  snapshots.value.unshift(newSnapshot);
  await alertDialog('快照保存成功');
};
</script>

<style scoped>
.system-preview {
  min-height: 100vh;
}

.preview-container {
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  padding: 16px;
  min-height: 400px;
}

.preview-container.desktop {
  max-width: 100%;
}

.preview-container.tablet {
  max-width: 768px;
  margin: 0 auto;
}

.preview-container.mobile {
  max-width: 375px;
  margin: 0 auto;
}

.preview-header {
  background-color: #f8f9fa;
  padding: 12px;
  border-radius: 4px;
  margin-bottom: 16px;
}

.preview-body {
  display: flex;
  gap: 16px;
}

.preview-sidebar {
  width: 200px;
  background-color: #f8f9fa;
  padding: 12px;
  border-radius: 4px;
}

.preview-content {
  flex: 1;
  background-color: #f8f9fa;
  padding: 12px;
  border-radius: 4px;
}

@media (max-width: 768px) {
  .preview-body {
    flex-direction: column;
  }
  
  .preview-sidebar {
    width: 100%;
  }
}
</style>
