<template>
  <div class="upload-screenshot">
    <div class="page-header">
      <h1>上传系统样式截图</h1>
      <p>上传系统样式截图，系统将自动解析菜单结构</p>
    </div>
    
    <div class="card">
      <h2>拖拽上传</h2>
      <div class="upload-area" @click="triggerFileInput">
        <div class="upload-icon">📁</div>
        <p>点击或拖拽文件到此处上传</p>
        <small>支持 .png/.jpg/.webp 格式，单文件最大 10MB</small>
        <input 
          type="file" 
          style="display: none;" 
          ref="fileInput" 
          accept=".png,.jpg,.webp"
          @change="handleFileChange"
        >
      </div>
      
      <div class="progress-bar" v-if="showProgress">
        <div class="progress" :style="{ width: progress + '%' }"></div>
      </div>
      
      <div class="image-preview" v-if="imageUrl">
        <img :src="imageUrl" alt="预览图片">
      </div>
      
      <div class="form-group">
        <label>文件名解析提示</label>
        <p class="tag tag-info">{{ fileNameHint }}</p>
      </div>
      
      <div class="form-group" v-if="menuStructure">
        <label>解析的菜单结构</label>
        <div class="menu-structure" style="border: 1px solid #e8e8e8; border-radius: 4px; padding: 16px; background-color: #fafafa;">
          <h4>{{ systemName }} 菜单结构</h4>
          <ul style="list-style: none; margin-top: 8px;">
            <li v-for="(item, index) in menuItems" :key="index" style="padding: 8px; border-bottom: 1px solid #e8e8e8;">
              {{ getLevelText(item.level) }}: {{ item.name }}
            </li>
          </ul>
        </div>
      </div>
      
      <div class="form-group" v-if="lastSavedRecord">
        <label>系统记录</label>
        <p class="tag tag-success">
          已保存：{{ lastSavedRecord.system_name }}（ID: {{ lastSavedRecord.id }}）
        </p>
      </div>
      
      <div style="display: flex; gap: 12px; margin-top: 24px;">
        <button class="btn btn-primary" @click="uploadFile" :disabled="isUploading">上传</button>
        <button class="btn btn-default" @click="clearForm">清空</button>
        <button class="btn btn-primary" v-if="showNext" @click="goToNext">下一步</button>
      </div>
    </div>
    
    <div class="card">
      <h2>历史记录</h2>
      <table class="table">
        <thead>
          <tr>
            <th>时间</th>
            <th>文件名</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="record in historyRecords" :key="record.id">
            <td>{{ record.created_at || record.operation_time }}</td>
            <td>{{ record.file_name }}</td>
            <td>
              <button class="btn btn-default" @click="viewRecord(record)">查看</button>
              <button class="btn btn-default" @click="startEdit(record)">编辑</button>
              <button class="btn btn-danger" @click="deleteRecord(record.id)">删除</button>
            </td>
          </tr>
          <tr v-if="historyRecords.length === 0">
            <td colspan="3" style="text-align: center; color: #999;">暂无历史记录</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="card" v-if="editingRecord">
      <h2>编辑系统记录</h2>
      <div class="form-group">
        <label>文件名（会联动菜单层级）</label>
        <input class="input" v-model="editForm.file_name" placeholder="例如：一级标题_二级标题_三级标题_按钮.png" />
      </div>

      <div class="form-group">
        <label>菜单结构（按层级）</label>
        <div style="display: grid; gap: 8px;">
          <div v-for="(item, index) in editForm.menu_structure" :key="index" style="display:flex; gap:8px; align-items:center;">
            <span style="min-width: 80px; color:#666;">{{ getLevelText(item.level) }}</span>
            <input class="input" v-model="item.name" placeholder="菜单名称" style="flex:1;" />
            <button class="btn btn-danger" @click="removeMenuItem(index)">移除</button>
          </div>
        </div>
        <div style="margin-top: 8px;">
          <button class="btn btn-default" @click="addMenuItem">新增层级</button>
        </div>
      </div>

      <div style="display:flex; gap:12px;">
        <button class="btn btn-primary" @click="saveEdit" :disabled="isSavingEdit">保存</button>
        <button class="btn btn-default" @click="reparseMenuFromFileName">按文件名重新解析</button>
        <button class="btn btn-default" @click="cancelEdit">取消</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useUiDialog } from '../composables/useUiDialog';

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
    
    // 显示预览
    const reader = new FileReader();
    reader.onload = function(e) {
      imageUrl.value = e.target.result;
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
    // 创建FormData对象
    const formData = new FormData();
    formData.append('file', fileInput.value.files[0]);
    
    // 发送上传请求
    const response = await fetch('/api/upload', {
      method: 'POST',
      body: formData
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      if (response.status === 409) {
        throw new Error(errorData.error || '文件名已存在，请修改文件名后再上传');
      }
      throw new Error(errorData.error || `上传失败: ${response.status} ${response.statusText}`);
    }
    
    const data = await response.json();
    
    // 更新进度
    progress.value = 100;
    clearInterval(interval);
    
    // 解析返回的菜单结构
    systemName.value = data.system_name;
    menuItems.value = data.menu_structure.map(item => ({
      level: item.level,
      name: item.name
    }));
    menuStructure.value = true;
    
    // 记录保存结果（用于后续 LLM 用例生成）
    lastSavedRecord.value = data;
    
    // 刷新历史记录
    await fetchHistory();
    window.dispatchEvent(new Event('history-updated'));
    
    // 显示下一步按钮
    showNext.value = true;
    
    await alertDialog('上传成功，系统记录已保存');
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
    const response = await fetch('/api/history');
    if (!response.ok) {
      throw new Error('获取历史记录失败');
    }
    const data = await response.json();
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
      const response = await fetch(`/api/history/${historyId}`, {
        method: 'DELETE'
      });
      
      if (!response.ok) {
        throw new Error('删除失败');
      }
      
      // 刷新历史记录
      await fetchHistory();
      window.dispatchEvent(new Event('history-updated'));
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
  // 此处可以通过emit事件通知父组件切换到LLM分析页面
  // 暂时使用window.location模拟
  window.location.href = '#llm-analysis';
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
    const response = await fetch(`/api/history/${editingRecord.value.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.error || '保存失败');
    }
    const updated = await response.json();
    lastSavedRecord.value = updated;
    await fetchHistory();
    window.dispatchEvent(new Event('history-updated'));
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
  window.addEventListener('history-updated', fetchHistory);
});
</script>

<style scoped>
.upload-screenshot {
  min-height: 100vh;
}
</style>
