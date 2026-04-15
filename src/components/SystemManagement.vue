<template>
  <div class="system-management page">
    <div class="page-header">
      <h1>系统管理</h1>
      <p>管理被测系统，所有分析和用例数据按系统隔离</p>
    </div>

    <el-card class="app-card" shadow="never">
      <template #header>
        <div style="display:flex; align-items:center; justify-content: space-between; gap: 12px;">
          <div style="font-weight: 800;">系统列表</div>
          <el-button v-if="canManageSystems" type="primary" @click="openCreateDialog">新建系统</el-button>
        </div>
      </template>

      <el-skeleton v-if="loading" :rows="6" animated />

      <el-alert v-else-if="errorText" type="error" :closable="false" show-icon title="加载系统失败">
        <template #default>
          <div style="white-space: pre-wrap; word-break: break-word;">{{ errorText }}</div>
        </template>
      </el-alert>

      <el-table v-else :data="systems" stripe style="width: 100%;">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column label="系统名称" min-width="180">
          <template #default="{ row }">
            <span class="system-name">{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="220">
          <template #default="{ row }">{{ row.description || '-' }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">{{ row.created_at || '-' }}</template>
        </el-table-column>
        <el-table-column prop="updated_at" label="更新时间" width="180">
          <template #default="{ row }">{{ row.updated_at || '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-space wrap>
              <el-button type="primary" size="small" @click="selectSystem(row)">
                {{ selectedSystemId === row.id ? '已选中' : '选择' }}
              </el-button>
              <el-button v-if="canManageSystems" size="small" @click="openEditDialog(row)">编辑</el-button>
              <el-button v-if="canManageSystems" type="danger" size="small" @click="confirmDelete(row)">删除</el-button>
            </el-space>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty :description="canManageSystems ? '暂无系统，请点击“新建系统”添加' : '暂无系统，请联系管理员创建后再使用。'" />
        </template>
      </el-table>
    </el-card>

    <el-card v-if="selectedSystem" class="app-card" shadow="never">
      <template #header>
        <div style="font-weight: 800;">当前选中系统</div>
      </template>
      <el-descriptions :column="1" border>
        <el-descriptions-item label="系统名称">
          <span style="font-weight:800;">{{ selectedSystem.name }}</span>
        </el-descriptions-item>
        <el-descriptions-item v-if="selectedSystem.description" label="描述">
          {{ selectedSystem.description }}
        </el-descriptions-item>
      </el-descriptions>
      <div style="margin-top: 12px; color: var(--app-muted); font-size: 13px; line-height: 1.6;">
        选中后，分析系统、系统预览、用例管理等模块将在此系统范围内操作。
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="isEditing ? '编辑系统' : '新建系统'" width="520px" align-center>
      <el-form label-position="top">
        <el-form-item label="系统名称">
          <el-input v-model="form.name" maxlength="100" show-word-limit placeholder="请输入系统名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="请输入系统描述（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-space>
          <el-button @click="closeDialog">取消</el-button>
          <el-button type="primary" :loading="submitting" @click="submitForm">
            {{ submitting ? '提交中...' : '确定' }}
          </el-button>
        </el-space>
      </template>
    </el-dialog>

    <el-dialog v-model="deleteConfirmVisible" title="确认删除" width="520px" align-center>
      <div style="line-height: 1.7;">
        <div>确定要删除系统 <b>{{ pendingDeleteSystem?.name }}</b> 吗？</div>
        <el-alert
          style="margin-top: 12px;"
          type="warning"
          :closable="false"
          show-icon
          title="删除后，该系统下的所有需求记录、分析结果、需求网络和测试用例将被一并删除，此操作不可恢复。"
        />
      </div>
      <template #footer>
        <el-space>
          <el-button @click="cancelDelete">取消</el-button>
          <el-button type="danger" :loading="submitting" @click="doDelete">
            {{ submitting ? '删除中...' : '确认删除' }}
          </el-button>
        </el-space>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue';
import { useRouter } from 'vue-router';
import { useSystemStore } from '../stores/system';
import { useAuthStore } from '../stores/auth';
import { listSystems, createSystem, updateSystem, deleteSystem } from '../api/systems';
import { ElMessage } from 'element-plus';

const router = useRouter();
const systemStore = useSystemStore();
const authStore = useAuthStore();

const selectedSystemId = computed(() => systemStore.systemId);
const selectedSystem = computed(() => systemStore.selectedSystem);
// 仅当同时拥有“系统管理能力”和“系统列表能力”时，才允许编辑/删除
// 普通用户可选择系统（menu.system 或 menu.system.list 其一即可），但不能新建/编辑/删除。
const canManageSystems = computed(() => authStore.can('menu.system') && authStore.can('menu.system.list'));

const systems = ref([]);
const loading = ref(false);
const errorText = ref('');
const dialogVisible = ref(false);
const deleteConfirmVisible = ref(false);
const isEditing = ref(false);
const submitting = ref(false);
const editingId = ref(null);
const pendingDeleteSystem = ref(null);

const form = ref({ name: '', description: '' });

async function fetchSystems() {
  loading.value = true;
  errorText.value = '';
  try {
    systems.value = await listSystems();
  } catch (e) {
    console.error('加载系统列表失败:', e);
    errorText.value = e?.message || String(e);
  } finally {
    loading.value = false;
  }
}

function selectSystem(sys) {
  systemStore.selectSystem(sys);
  router.push('/upload');
}

function openCreateDialog() {
  if (!canManageSystems.value) return;
  isEditing.value = false;
  editingId.value = null;
  form.value = { name: '', description: '' };
  dialogVisible.value = true;
}

function openEditDialog(sys) {
  if (!canManageSystems.value) return;
  isEditing.value = true;
  editingId.value = sys.id;
  form.value = { name: sys.name, description: sys.description || '' };
  dialogVisible.value = true;
}

function closeDialog() {
  dialogVisible.value = false;
}

async function submitForm() {
  if (!canManageSystems.value) return;
  if (!form.value.name.trim()) {
    ElMessage.warning('请输入系统名称');
    return;
  }
  submitting.value = true;
  try {
    if (isEditing.value) {
      await updateSystem(editingId.value, {
        name: form.value.name.trim(),
        description: form.value.description.trim(),
      });
    } else {
      await createSystem({
        name: form.value.name.trim(),
        description: form.value.description.trim(),
      });
    }
    closeDialog();
    await fetchSystems();
  } catch (e) {
    ElMessage.error(e.message || '操作失败');
  } finally {
    submitting.value = false;
  }
}

function confirmDelete(sys) {
  if (!canManageSystems.value) return;
  pendingDeleteSystem.value = sys;
  deleteConfirmVisible.value = true;
}

function cancelDelete() {
  deleteConfirmVisible.value = false;
  pendingDeleteSystem.value = null;
}

async function doDelete() {
  if (!canManageSystems.value) return;
  if (!pendingDeleteSystem.value) return;
  submitting.value = true;
  try {
    await deleteSystem(pendingDeleteSystem.value.id);
    if (systemStore.systemId === pendingDeleteSystem.value.id) {
      systemStore.clearSystem();
    }
    cancelDelete();
    await fetchSystems();
  } catch (e) {
    ElMessage.error(e.message || '删除失败');
  } finally {
    submitting.value = false;
  }
}

onMounted(() => {
  fetchSystems();
});
</script>

<style scoped>
.system-management {
  max-width: 1200px;
}

.system-name {
  font-weight: 500;
  color: var(--el-color-primary);
}
</style>
