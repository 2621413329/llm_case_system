<template>
  <div class="gallery page">
    <div class="page-header">
      <h1>需求预览</h1>
      <p>按文件名解析的分级菜单分类展示需求</p>
    </div>

    <div class="zt-layout">
      <el-card class="zt-side app-card" shadow="never">
        <template #header>
          <div style="font-weight: 800;">分类</div>
        </template>
        <el-form label-position="top">
          <el-form-item v-if="systems.length > 1" label="系统">
            <el-select v-model="selectedSystem" placeholder="全部" style="width: 100%;">
              <el-option value="" label="全部" />
              <el-option v-for="s in systems" :key="s" :value="s" :label="s" />
            </el-select>
          </el-form-item>

          <el-form-item label="菜单层级（点击筛选）">
            <el-input
              v-model="treeKeyword"
              clearable
              placeholder="输入菜单关键词快速筛选"
              style="margin-bottom: 8px;"
            />
            <div class="zt-tree">
            <template v-for="node in treeRootsFiltered" :key="node.key">
              <TreeNode
                :node="node"
                :active-path="selectedPath"
                @toggle="toggleNode"
                @select="selectPath"
              />
            </template>
            <div v-if="treeRootsFiltered.length === 0" style="color:#999;">暂无分类（请先上传需求）</div>
          </div>
          </el-form-item>

          <div class="selected-path-tip">
            已选中：{{ selectedPath.length ? selectedPath.join(' / ') : '全部菜单' }}
          </div>

          <el-space wrap>
            <el-button @click="clearFilters">清空筛选</el-button>
            <el-button @click="fetchHistory">刷新</el-button>
          </el-space>
        </el-form>
      </el-card>

      <section class="zt-main">
        <el-card class="app-card" shadow="never">
          <div style="display:flex; justify-content: space-between; align-items:center; gap:12px;">
            <div class="zt-title">预览</div>
            <div class="app-muted">共 {{ filteredRecords.length }} 张</div>
          </div>

          <div class="grid" v-if="filteredRecords.length > 0">
            <el-card class="tile" v-for="r in filteredRecords" :key="r.id" shadow="hover" :body-style="{ padding: '12px' }">
              <div class="thumb" @click="openModal(r)">
                <el-image
                  :src="r.file_url"
                  :alt="r.file_name"
                  fit="contain"
                  style="width: 100%; height: 160px;"
                  @error="onImgError(r)"
                />
              </div>
              <div class="meta">
                <div class="title" :title="r.file_name">{{ r.file_name }}</div>
                <div class="sub">
                  <el-tag size="small" type="info" effect="light">{{ r.system_name || '默认系统' }}</el-tag>
                  <span class="time">{{ r.created_at }}</span>
                </div>
                <div class="crumb" v-if="Array.isArray(r.menu_structure) && r.menu_structure.length">
                  {{ breadcrumb(r.menu_structure) }}
                </div>
                <el-space wrap style="margin-top: 10px;">
                  <el-button @click="openModal(r)">查看</el-button>
                  <el-button v-if="canDeleteHistory" type="danger" @click="deleteRecord(r)">删除</el-button>
                </el-space>
              </div>
            </el-card>
          </div>
          <el-empty v-else description="暂无需求可预览" />
        </el-card>
      </section>
    </div>

    <el-dialog v-model="modalOpen" :title="modalRecord?.file_name || '详情'" width="1100px" align-center>
      <template #default>
        <div v-if="modalRecord" class="modal-body">
          <el-image class="modal-img" :src="modalRecord.file_url" :alt="modalRecord.file_name" fit="contain" />
          <div class="modal-side">
            <el-descriptions :column="1" border>
              <el-descriptions-item label="系统">{{ modalRecord.system_name || '默认系统' }}</el-descriptions-item>
              <el-descriptions-item label="时间">{{ modalRecord.created_at }}</el-descriptions-item>
              <el-descriptions-item label="ID">{{ modalRecord.id }}</el-descriptions-item>
              <el-descriptions-item label="菜单结构">
                <div v-if="Array.isArray(modalRecord.menu_structure) && modalRecord.menu_structure.length">
                  <div v-for="(m, idx) in modalRecord.menu_structure" :key="idx">
                    第 {{ m.level }} 级：{{ m.name }}
                  </div>
                </div>
                <span v-else class="app-muted">无</span>
              </el-descriptions-item>
              <el-descriptions-item label="分析（已保存）">
                <div v-if="displayAnalysisText(modalRecord)" class="analysis-saved-box">
                  {{ displayAnalysisText(modalRecord) }}
                </div>
                <div v-else class="app-muted">暂无（可在「系统需求分析库」中生成并保存）</div>
              </el-descriptions-item>
            </el-descriptions>
          </div>
        </div>
      </template>
      <template #footer>
        <el-space>
          <el-button v-if="canDeleteHistory" type="danger" @click="deleteRecord(modalRecord)">删除</el-button>
          <el-button @click="closeModal">关闭</el-button>
        </el-space>
      </template>
    </el-dialog>

  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { useSystemStore } from '../stores/system';
import { useAuthStore } from '../stores/auth';
import { useUiDialog } from '../composables/useUiDialog';
import TreeNode from './TreeNode.vue';
import { deleteHistory, listHistory } from '../api/history';
import { listSystems } from '../api/systems';
import { emitHistoryUpdated, subscribeHistoryUpdated } from '../composables/useHistorySync';
import {
  historySystemKey,
  buildSystemLabelMap,
  rowBelongsToSystemId,
} from '../utils/systemMenuTree.js';

const systemStore = useSystemStore();
const authStore = useAuthStore();
const canDeleteHistory = computed(() => authStore.can('action.history.delete'));

const records = ref([]);
const registrySystems = ref([]);
const selectedSystem = ref('');
const selectedPath = ref([]); // menu names prefix
const treeKeyword = ref('');
const modalRecord = ref(null);
const modalOpen = computed({
  get: () => !!modalRecord.value,
  set: (v) => {
    if (!v) modalRecord.value = null;
  },
});
const { alertDialog, confirmDialog } = useUiDialog();
const collapsedKeys = ref(new Set());

const fetchHistory = async () => {
  const params = {};
  if (systemStore.systemId != null && systemStore.systemId !== '') params.system_id = systemStore.systemId;
  const data = await listHistory(params);
  // Normalize fields used by UI
  records.value = (Array.isArray(data) ? data : []).map((r) => ({
    ...r,
    created_at: r.created_at || r.operation_time || '',
    file_url: r.file_url || (r.file_name ? `/uploads/${r.file_name}` : ''),
    analysis: r.analysis || ''
  }));
};

const baseRecords = computed(() => {
  const list = Array.isArray(records.value) ? records.value : [];
  const raw = systemStore.systemId;
  if (raw == null || raw === '') return list;
  const sid = Number(raw);
  if (Number.isNaN(sid)) return list;
  return list.filter((r) => rowBelongsToSystemId(r, sid));
});

const systems = computed(() => {
  const set = new Set();
  for (const r of baseRecords.value) {
    if (r.system_name) set.add(r.system_name);
  }
  return Array.from(set).sort((a, b) => a.localeCompare(b));
});

const filteredBySystem = computed(() => {
  if (!selectedSystem.value) return baseRecords.value;
  return baseRecords.value.filter((r) => r.system_name === selectedSystem.value);
});

const filteredRecords = computed(() => {
  const base = filteredBySystem.value;
  const path = selectedPath.value;
  if (!path.length) return base;
  const skSet = new Set(base.map((r) => historySystemKey(r)));
  const layered = skSet.size > 1;
  const labelMap = buildSystemLabelMap(base, registrySystems.value);
  return base.filter((r) => {
    const ms = Array.isArray(r.menu_structure) ? r.menu_structure : [];
    const names = ms.map((x) => x?.name).filter(Boolean);
    if (layered) {
      const lab = labelMap.get(historySystemKey(r));
      if (path[0] !== lab) return false;
      const rest = path.slice(1);
      if (!rest.length) return true;
      for (let i = 0; i < rest.length; i++) if (names[i] !== rest[i]) return false;
      return true;
    }
    for (let i = 0; i < path.length; i++) if (names[i] !== path[i]) return false;
    return true;
  });
});

function breadcrumb(menuStructure) {
  return menuStructure.map((x) => x.name).filter(Boolean).join(' / ');
}

function displayAnalysisText(r) {
  if (!r || typeof r !== 'object') return '';
  const a = String(r.analysis || '').trim();
  if (a) return a;
  const c = String(r.analysis_content || '').trim();
  return c;
}

function openModal(r) {
  modalRecord.value = r;
}
function closeModal() {
  modalRecord.value = null;
}

function clearFilters() {
  selectedSystem.value = '';
  selectedPath.value = [];
  treeKeyword.value = '';
  collapsedKeys.value = new Set();
}

function onImgError(r) {
  // fallback to avoid broken images breaking layout
  if (r && r.file_name) r.file_url = `/uploads/${encodeURIComponent(r.file_name)}`;
}

const treeRoots = computed(() => {
  const base = filteredBySystem.value;
  const recordCountMap = new Map();
  for (const r of base) {
    const sk = historySystemKey(r);
    const ms = Array.isArray(r.menu_structure) ? r.menu_structure : [];
    const names = ms.map((x) => x?.name).filter(Boolean);
    let p = [];
    for (const name of names) {
      p = [...p, name];
      const k = `${sk}::${p.join('>>')}`;
      recordCountMap.set(k, (recordCountMap.get(k) || 0) + 1);
    }
  }

  const skSet = new Set(base.map((r) => historySystemKey(r)));
  const showLayer = skSet.size > 1;
  const labelMap = buildSystemLabelMap(base, registrySystems.value);
  const collapsed = collapsedKeys.value;
  const rootMap = new Map();

  const sortRec = (nodes) => {
    nodes.sort((a, b) => a.label.localeCompare(b.label));
    for (const n of nodes) sortRec(n.children);
  };

  if (!base.length) return [];

  if (showLayer) {
    const systemNodes = new Map();
    const menuNodeMap = new Map();
    for (const sk of skSet) {
      const lab = labelMap.get(sk);
      const sysKey = `sys:${sk}`;
      let total = 0;
      for (const r of base) {
        if (historySystemKey(r) === sk) total += 1;
      }
      const node = {
        key: sysKey,
        label: lab,
        path: [lab],
        depth: 0,
        count: total,
        children: [],
        collapsed: collapsed.has(sysKey),
      };
      systemNodes.set(sk, node);
      rootMap.set(sysKey, node);
    }
    for (const r of base) {
      const sk = historySystemKey(r);
      const sysNode = systemNodes.get(sk);
      const ms = Array.isArray(r.menu_structure) ? r.menu_structure : [];
      const names = ms.map((x) => x.name).filter(Boolean);
      let path = [];
      let parent = sysNode;
      for (const name of names) {
        path = [...path, name];
        const mk = `${sk}::${path.join('>>')}`;
        let node = menuNodeMap.get(mk);
        if (!node) {
          const lab = labelMap.get(sk);
          node = {
            key: mk,
            label: name,
            path: [lab, ...path],
            depth: path.length,
            count: recordCountMap.get(mk) || 0,
            children: [],
            collapsed: collapsed.has(mk),
          };
          menuNodeMap.set(mk, node);
          if (!parent.children.find((c) => c.key === node.key)) parent.children.push(node);
        }
        parent = node;
      }
    }
    const roots = Array.from(rootMap.values());
    sortRec(roots);
    return roots;
  }

  const onlySk = [...skSet][0];
  const nodeMap = new Map();
  const ensureNode = (pathParts) => {
    const key = `${onlySk}::${pathParts.join('>>')}`;
    if (nodeMap.has(key)) return nodeMap.get(key);
    const node = {
      key,
      label: pathParts[pathParts.length - 1],
      depth: pathParts.length - 1,
      path: pathParts,
      count: recordCountMap.get(key) || 0,
      children: [],
      collapsed: collapsed.has(key),
    };
    nodeMap.set(key, node);
    return node;
  };

  for (const r of base) {
    const ms = Array.isArray(r.menu_structure) ? r.menu_structure : [];
    const names = ms.map((x) => x.name).filter(Boolean);
    let path = [];
    for (const name of names) {
      path = [...path, name];
      const node = ensureNode(path);
      node.collapsed = collapsed.has(node.key);
      if (path.length === 1) {
        rootMap.set(node.key, node);
      } else {
        const parent = ensureNode(path.slice(0, -1));
        if (!parent.children.find((c) => c.key === node.key)) parent.children.push(node);
      }
    }
  }

  const roots = Array.from(rootMap.values());
  sortRec(roots);
  return roots;
});

const filterTreeNodes = (nodes, kw) => {
  if (!kw) return nodes;
  const out = [];
  for (const node of nodes) {
    const children = filterTreeNodes(Array.isArray(node.children) ? node.children : [], kw);
    const labelHit = String(node.label || '').toLowerCase().includes(kw);
    const pathHit = Array.isArray(node.path) && node.path.join(' / ').toLowerCase().includes(kw);
    if (labelHit || pathHit || children.length > 0) {
      out.push({ ...node, children });
    }
  }
  return out;
};

const treeRootsFiltered = computed(() => {
  const kw = String(treeKeyword.value || '').trim().toLowerCase();
  return filterTreeNodes(treeRoots.value, kw);
});

function toggleNode(key) {
  const s = new Set(collapsedKeys.value);
  if (s.has(key)) s.delete(key);
  else s.add(key);
  collapsedKeys.value = s;
}
function selectPath(path) {
  selectedPath.value = path;
}

watch(
  () => selectedSystem.value,
  () => {
    selectedPath.value = [];
    collapsedKeys.value = new Set();
  },
);

watch(
  () => systemStore.systemId,
  () => {
    selectedPath.value = [];
    collapsedKeys.value = new Set();
  },
);

onMounted(async () => {
  try {
    try {
      registrySystems.value = await listSystems();
    } catch {
      registrySystems.value = [];
    }
    await fetchHistory();
  } catch (e) {
    console.error(e);
  }
});

// 联动：上传/编辑/删除后自动刷新
onMounted(() => {
  const unsubscribe = subscribeHistoryUpdated(() => {
    fetchHistory().catch(() => {});
  });
  onUnmounted(() => unsubscribe());
});

async function deleteRecord(r) {
  if (!r?.id) return;
  if (
    !(await confirmDialog('确定要删除这条需求记录吗？\n删除后无法恢复。', {
      title: '请确认操作',
      confirmText: '删除',
      cancelText: '取消',
    }))
  )
    return;
  try {
    await deleteHistory(r.id);
  } catch (e) {
    await alertDialog(e.message || '删除失败');
    return;
  }
  if (modalRecord.value?.id === r.id) modalRecord.value = null;
  emitHistoryUpdated();
}

</script>

<style scoped>
.gallery { min-height: 100vh; }
.zt-layout { display: grid; grid-template-columns: 320px 1fr; gap: 16px; margin-top: 12px; }
.zt-side { position: sticky; top: 12px; align-self: start; z-index: 2; background: #fff; }
.zt-main { min-width: 0; }
.zt-title { font-weight: 800; font-size: 16px; }
.zt-tree {
  width: 100%;
  max-height: 520px;
  overflow: auto;
  border: 1px solid #eee;
  border-radius: 8px;
  padding: 10px;
  background: #fafafa;
  margin-top: 8px;
  font-size: 15px;

  /* Firefox */
  scrollbar-width: thin;
  scrollbar-color: rgba(17, 24, 39, 0.28) transparent;
}
.zt-tree::-webkit-scrollbar {
  width: 10px;
  height: 10px;
}
.zt-tree::-webkit-scrollbar-track {
  background: transparent;
}
.zt-tree::-webkit-scrollbar-thumb {
  background: rgba(17, 24, 39, 0.20);
  border-radius: 999px;
  border: 3px solid transparent;
  background-clip: content-box;
}
.zt-tree::-webkit-scrollbar-thumb:hover {
  background: rgba(17, 24, 39, 0.30);
  border: 3px solid transparent;
  background-clip: content-box;
}
.selected-path-tip { margin-top: 6px; margin-bottom: 10px; padding: 8px 10px; border-radius: 8px; background: #f0f7ff; color:#1677ff; font-size:12px; border: 1px solid #d6e9ff; }

/* 树筛选：与用例管理一致的 TreeNode 视觉 */
:deep(.tree-node) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
  margin-top: 4px;
  border: 1px solid transparent;
  font-size: inherit;
}
:deep(.tree-node:hover) { background: #f5faff; border-color: #e6f2ff; }
:deep(.tree-node.active) {
  background: #e6f4ff;
  color: #1677ff;
  border-color: #91caff;
  box-shadow: 0 0 0 2px rgba(22, 119, 255, 0.12);
}
:deep(.tree-node.prefixActive) {
  background: #f7fbff;
  border-color: #d6e9ff;
}
:deep(.tree-label) { display: flex; align-items: center; gap: 6px; min-width: 0; }
:deep(.tree-count) { color: #999; font-size: 13px; }
.grid { margin-top: 12px; display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px; }
.tile { border: 1px solid #eee; border-radius: 10px; overflow: hidden; cursor: pointer; background: #fff; }
.thumb { height: 160px; background: #f6f6f6; display:flex; align-items:center; justify-content:center; }
.thumb img { max-width: 100%; max-height: 100%; object-fit: contain; }
.meta { padding: 10px; }
.title { font-weight: 700; overflow:hidden; text-overflow: ellipsis; white-space: nowrap; }
.sub { margin-top: 6px; display:flex; justify-content: space-between; gap: 8px; align-items:center; color:#666; font-size: 12px; }
.tag { background: #f0f7ff; color:#1677ff; padding: 2px 8px; border-radius: 999px; }
.crumb { margin-top: 6px; color:#666; font-size: 12px; overflow:hidden; text-overflow: ellipsis; white-space: nowrap; }

.modal-mask { position: fixed; inset: 0; background: rgba(0,0,0,0.45); display:flex; align-items: center; justify-content: center; padding: 24px; z-index: 50; }
.modal { width: min(1100px, 100%); }
.modal-body { display: grid; grid-template-columns: 1fr 320px; gap: 16px; margin-top: 12px; }
.modal-img { width: 100%; max-height: 70vh; object-fit: contain; background: #f6f6f6; border-radius: 8px; }
.modal-side { border-left: 1px solid #eee; padding-left: 12px; }
.analysis-saved-box {
  white-space: pre-wrap;
  font-size: 13px;
  color: #333;
  border: 1px solid #eee;
  padding: 10px;
  border-radius: 8px;
  background: #fafafa;
  max-height: min(42vh, 420px);
  overflow: auto;
  line-height: 1.6;
  word-break: break-word;
}

@media (max-width: 980px) {
  .zt-layout { grid-template-columns: 1fr; }
  .zt-side { position: static; }
  .modal-body { grid-template-columns: 1fr; }
  .modal-side { border-left: 0; padding-left: 0; border-top: 1px solid #eee; padding-top: 12px; }
}
</style>
