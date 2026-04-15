<template>
  <div class="upload-screenshot page">
    <div class="page-header">
      <h1>上传系统样式需求</h1>
      <p>上传系统样式需求，系统将自动解析菜单结构</p>
    </div>
    
    <el-card class="app-card" shadow="never">
      <template #header>
        <div style="font-weight: 800;">上传</div>
      </template>
      <div class="upload-area" @click="triggerFileInput">
        <div class="upload-icon">📁</div>
        <p>点击或拖拽文件到此处上传</p>
        <small>支持单张图片（.png/.jpg/.webp）或 ZIP 压缩包（内含上述格式图片，将批量入库），单文件最大 100MB</small>
        <input 
          type="file" 
          style="display: none;" 
          ref="fileInput" 
          accept=".png,.jpg,.jpeg,.webp,.zip"
          @change="handleFileChange"
        >
      </div>
      
      <el-progress v-if="showProgress" :percentage="progress" :stroke-width="10" style="margin-top: 14px;" />
      
      <div class="image-preview" v-if="imageUrl">
        <el-image :src="imageUrl" fit="contain" style="width: 100%; max-height: 420px;" />
      </div>
      
      <el-form label-position="top" style="margin-top: 12px;">
        <el-form-item label="文件名解析提示">
          <el-tag type="info">{{ fileNameHint }}</el-tag>
        </el-form-item>
      
        <el-form-item v-if="menuStructure" label="解析的菜单结构">
          <el-card shadow="never" style="background: rgba(17, 24, 39, 0.02);">
            <div style="font-weight: 800;">{{ systemName }} 菜单结构</div>
            <el-timeline style="margin-top: 10px;">
              <el-timeline-item v-for="(item, index) in menuItems" :key="index">
                {{ getLevelText(item.level) }}：{{ item.name }}
              </el-timeline-item>
            </el-timeline>
          </el-card>
        </el-form-item>
      
        <el-form-item v-if="lastSavedRecord" label="系统记录">
          <el-tag type="success">已保存：{{ lastSavedRecord.system_name }}（ID: {{ lastSavedRecord.id }}）</el-tag>
        </el-form-item>
      </el-form>
      
      <div style="display: flex; gap: 12px; margin-top: 24px;">
        <el-button v-if="canUpload" type="primary" :loading="isUploading" @click="uploadFile">上传</el-button>
        <el-button @click="clearForm">清空</el-button>
        <el-button v-if="showNext" type="primary" @click="goToNext">下一步</el-button>
      </div>
    </el-card>
    
    <el-card class="app-card" shadow="never">
      <template #header>
        <div style="font-weight: 800;">历史记录</div>
      </template>
      <el-table :data="historyRecords" stripe style="width: 100%;">
        <el-table-column label="时间" width="200">
          <template #default="{ row }">{{ row.created_at || row.operation_time }}</template>
        </el-table-column>
        <el-table-column prop="file_name" label="文件名" min-width="240" />
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-space wrap>
              <el-button @click="viewRecord(row)">查看</el-button>
              <el-button @click="startEdit(row)">编辑</el-button>
              <el-button v-if="canDeleteHistory" type="danger" @click="deleteRecord(row.id)">删除</el-button>
            </el-space>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无历史记录" />
        </template>
      </el-table>
    </el-card>

    <el-card v-if="editingRecord" class="app-card" shadow="never">
      <template #header>
        <div style="font-weight: 800;">编辑系统记录</div>
      </template>
      <el-form label-position="top">
        <el-form-item label="文件名（会联动菜单层级）">
          <el-input v-model="editForm.file_name" placeholder="例如：一级标题_二级标题_三级标题_按钮.png" />
        </el-form-item>

        <el-form-item label="菜单结构（按层级）">
          <div style="display: grid; gap: 10px; width: 100%;">
            <div v-for="(item, index) in editForm.menu_structure" :key="index" style="display:flex; gap:10px; align-items:center;">
              <el-tag type="info" effect="light" style="min-width: 96px;">{{ getLevelText(item.level) }}</el-tag>
              <el-input v-model="item.name" placeholder="菜单名称" style="flex:1;" />
              <el-button type="danger" @click="removeMenuItem(index)">移除</el-button>
            </div>
          </div>
          <div style="margin-top: 10px;">
            <el-button @click="addMenuItem">新增层级</el-button>
          </div>
        </el-form-item>
      </el-form>

      <el-space wrap>
        <el-button type="primary" :loading="isSavingEdit" @click="saveEdit">保存</el-button>
        <el-button @click="reparseMenuFromFileName">按文件名重新解析</el-button>
        <el-button @click="cancelEdit">取消</el-button>
      </el-space>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useSystemStore } from '../stores/system';
import { useAuthStore } from '../stores/auth';
import { useUiDialog } from '../composables/useUiDialog';
import { deleteHistory, listHistory, updateHistory } from '../api/history';
import { uploadScreenshot } from '../api/upload';
import { emitHistoryUpdated, subscribeHistoryUpdated } from '../composables/useHistorySync';

const router = useRouter();
const systemStore = useSystemStore();
const authStore = useAuthStore();
const canUpload = computed(() => authStore.can('action.upload'));
const canDeleteHistory = computed(() => authStore.can('action.history.delete'));

const fileInput = ref(null);
const imageUrl = ref('');
const fileName = ref('');
const showProgress = ref(false);
const progress = ref(0);
const menuStructure = ref(null);
const systemName = ref('');
const menuItems = ref([]);
const lastSavedRecord = ref(null);
const showNext = ref(false);
const historyRecords = ref([]);
const isUploading = ref(false);
const editingRecord = ref(null);
const editForm = ref({ file_name: '', menu_structure: [] });
const isSavingEdit = ref(false);
const { alertDialog, confirmDialog } = useUiDialog();

const fileNameHint = computed(() => {
  return fileName.value ? `文件名: ${fileName.value}` : '将按文件名解析菜单结构';
});

const triggerFileInput = () => {
  fileInput.value.click();
};

const handleFileChange = (e) => {
  if (e.target.files.length > 0) {
    const file = e.target.files[0];
    fileName.value = file.name;
    
    if (/\.zip$/i.test(file.name)) {
      imageUrl.value = '';
      return;
    }
    // 显示预览（图片）
    const reader = new FileReader();
    reader.onload = function(ev) {
      imageUrl.value = ev.target.result;
    };
    reader.readAsDataURL(file);
  }
};

const uploadFile = async () => {
  if (!fileName.value) {
    await alertDialog('请选择文件');
    return;
  }
  
  isUploading.value = true;
  showProgress.value = true;
  progress.value = 0;
  
  // 模拟上传进度
  const interval = setInterval(() => {
    if (progress.value < 90) {
      progress.value += 10;
    }
  }, 200);
  
  try {
    const file = fileInput.value?.files?.[0];
    if (!file) throw new Error('请选择文件');
    const data = await uploadScreenshot(file, { systemId: systemStore.systemId });
    
    // 更新进度
    progress.value = 100;
    clearInterval(interval);
    
    // 解析返回的菜单结构
    systemName.value = data.system_name;
    menuItems.value = (data.menu_structure || []).map(item => ({
      level: item.level,
      name: item.name
    }));
    menuStructure.value = true;
    
    // 记录保存结果（用于后续 LLM 用例生成）
    lastSavedRecord.value = data;
    
    // 刷新历史记录
    await fetchHistory();
    emitHistoryUpdated();
    
    // 显示下一步按钮
    showNext.value = true;
    
    const n = Number(data.batch_count || 0);
    if (data.batch && n > 0) {
      await alertDialog(
        n > 1
          ? `上传成功：已从压缩包入库 ${n} 条需求记录（以下为其中第一条的菜单解析预览）`
          : '上传成功：已从压缩包入库 1 条需求记录'
      );
    } else {
      await alertDialog('上传成功，系统记录已保存');
    }
  } catch (error) {
    console.error('上传失败:', error);
    await alertDialog(`上传失败: ${error.message}\n请检查后端服务器是否运行`);
  } finally {
    isUploading.value = false;
    clearInterval(interval);
  }
};

const fetchHistory = async () => {
  try {
    const params = {};
    if (systemStore.systemId) params.system_id = systemStore.systemId;
    const data = await listHistory(params);
    historyRecords.value = data;
  } catch (error) {
    console.error('获取历史记录失败:', error);
  }
};

const deleteRecord = async (historyId) => {
  if (
    await confirmDialog('确定要删除这条记录吗？\n删除后无法恢复。', {
      title: '请确认操作',
      confirmText: '删除',
      cancelText: '取消',
    })
  ) {
    try {
      await deleteHistory(historyId);
      
      // 刷新历史记录
      await fetchHistory();
      emitHistoryUpdated();
      await alertDialog('删除成功');
    } catch (error) {
      console.error('删除失败:', error);
      await alertDialog('删除失败，请重试');
    }
  }
};

const getLevelText = (level) => {
  switch(level) {
    case 1:
      return '一级标题';
    case 2:
      return '二级标题';
    case 3:
      return '三级标题';
    case 4:
      return '按钮';
    default:
      return `层级 ${level}`;
  }
};

const parseMenuStructureFromFileName = (fileNameValue) => {
  if (!fileNameValue) return [];
  const base = fileNameValue.replace(/\.[^/.]+$/, ''); // strip extension
  const parts = base.split('_').filter(Boolean);
  return parts.map((name, idx) => ({ level: idx + 1, name }));
};

const clearForm = () => {
  fileInput.value.value = '';
  imageUrl.value = '';
  fileName.value = '';
  showProgress.value = false;
  progress.value = 0;
  menuStructure.value = null;
  systemName.value = '';
  menuItems.value = [];
  lastSavedRecord.value = null;
  showNext.value = false;
};

const goToNext = () => {
  router.push('/requirement-library');
};

const viewRecord = (record) => {
  // 将记录回填到页面预览区域
  systemName.value = record.system_name || '';
  menuItems.value = Array.isArray(record.menu_structure) ? record.menu_structure : [];
  menuStructure.value = true;
  if (record.file_url) {
    imageUrl.value = record.file_url;
    fileName.value = record.file_name || '';
  }
};

const startEdit = (record) => {
  editingRecord.value = record;
  editForm.value = {
    file_name: record.file_name || '',
    menu_structure: (Array.isArray(record.menu_structure) ? record.menu_structure : []).map((x) => ({
      level: x.level,
      name: x.name
    }))
  };
};

const cancelEdit = () => {
  editingRecord.value = null;
  editForm.value = { file_name: '', menu_structure: [] };
};

const reparseMenuFromFileName = () => {
  editForm.value.menu_structure = parseMenuStructureFromFileName(editForm.value.file_name);
};

watch(
  () => editForm.value.file_name,
  (v) => {
    editForm.value.menu_structure = parseMenuStructureFromFileName(v);
  }
);

const addMenuItem = () => {
  const current = editForm.value.menu_structure || [];
  const nextLevel = current.length > 0 ? Math.max(...current.map((x) => x.level || 0)) + 1 : 1;
  current.push({ level: nextLevel, name: '' });
  editForm.value.menu_structure = current;
};

const removeMenuItem = (index) => {
  const current = editForm.value.menu_structure || [];
  current.splice(index, 1);
  editForm.value.menu_structure = current;
};

const saveEdit = async () => {
  if (!editingRecord.value) return;
  isSavingEdit.value = true;
  try {
    const payload = {
      file_name: editForm.value.file_name,
      menu_structure: editForm.value.menu_structure
    };
    const updated = await updateHistory(editingRecord.value.id, payload);
    lastSavedRecord.value = updated;
    await fetchHistory();
    emitHistoryUpdated();
    cancelEdit();
    await alertDialog('保存成功');
  } catch (e) {
    console.error('保存失败:', e);
    await alertDialog(`保存失败: ${e.message}`);
  } finally {
    isSavingEdit.value = false;
  }
};

// 组件挂载时获取历史记录
onMounted(() => {
  fetchHistory();
  const unsubscribe = subscribeHistoryUpdated(fetchHistory);
  onUnmounted(() => unsubscribe());
});
</script>

<style scoped>
.upload-screenshot {
  min-height: 100vh;
}

.upload-area {
  border: 2px dashed rgba(17, 24, 39, 0.18);
  border-radius: 14px;
  padding: 42px 22px;
  text-align: center;
  cursor: pointer;
  background: rgba(255, 255, 255, 0.86);
  transition: border-color 0.18s ease, background 0.18s ease, box-shadow 0.18s ease;
}
.upload-area:hover {
  border-color: var(--el-color-primary);
  background: rgba(59, 130, 246, 0.04);
  box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.08);
}
.upload-icon {
  font-size: 34px;
  line-height: 1;
  margin-bottom: 10px;
  color: rgba(17, 24, 39, 0.55);
}
.upload-area p {
  font-size: 13px;
  color: rgba(17, 24, 39, 0.82);
}
.upload-area small {
  display: block;
  margin-top: 6px;
  font-size: 12px;
  color: rgba(107, 114, 128, 0.95);
}
.image-preview {
  margin-top: 14px;
  border: 1px solid rgba(17, 24, 39, 0.08);
  border-radius: 14px;
  padding: 12px;
  background: rgba(17, 24, 39, 0.02);
}
</style>
