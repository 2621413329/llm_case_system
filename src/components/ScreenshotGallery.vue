<template>
  <div class="gallery">
    <div class="page-header">
      <h1>截图预览</h1>
      <p>按文件名解析的分级菜单分类展示截图</p>
    </div>

    <div class="gallery-layout">
      <div class="card sidebar">
        <h2>分类</h2>
        <div class="form-group" v-if="systems.length > 1">
          <label>系统</label>
          <select class="input" v-model="selectedSystem">
            <option value="">全部</option>
            <option v-for="s in systems" :key="s" :value="s">{{ s }}</option>
          </select>
        </div>

        <div class="form-group">
          <label>菜单层级（点击筛选）</label>
          <div class="tree">
            <template v-for="node in treeRoots" :key="node.key">
              <TreeNode
                :node="node"
                :active-path="selectedPath"
                @toggle="toggleNode"
                @select="selectPath"
              />
            </template>
            <div v-if="treeRoots.length === 0" style="color:#999;">暂无分类（请先上传截图）</div>
          </div>
        </div>

        <div style="display:flex; gap:8px;">
          <button class="btn btn-default" @click="clearFilters">清空筛选</button>
          <button class="btn btn-default" @click="fetchHistory">刷新</button>
        </div>
      </div>

      <div class="card content">
        <div style="display:flex; justify-content: space-between; align-items:center; gap:12px;">
          <h2 style="margin:0;">预览</h2>
          <div style="color:#666;">共 {{ filteredRecords.length }} 张</div>
        </div>

        <div class="grid" v-if="filteredRecords.length > 0">
          <div class="tile" v-for="r in filteredRecords" :key="r.id">
            <div class="thumb">
              <img :src="r.file_url" :alt="r.file_name" @error="onImgError(r)" @click="openModal(r)" />
            </div>
            <div class="meta">
              <div class="title" :title="r.file_name">{{ r.file_name }}</div>
              <div class="sub">
                <span class="tag">默认系统</span>
                <span class="time">{{ r.created_at }}</span>
              </div>
              <div class="crumb" v-if="Array.isArray(r.menu_structure) && r.menu_structure.length">
                {{ breadcrumb(r.menu_structure) }}
              </div>
              <div style="display:flex; gap:8px; margin-top: 10px;">
                <button class="btn btn-default" @click="openModal(r)">查看</button>
                <button class="btn btn-danger" @click="deleteRecord(r)">删除</button>
              </div>
            </div>
          </div>
        </div>
        <div v-else style="padding: 16px; color:#999;">暂无截图可预览</div>
      </div>
    </div>

    <div class="modal-mask" v-if="modalRecord" @click.self="closeModal">
      <div class="modal card">
        <div style="display:flex; justify-content: space-between; align-items:center; gap:12px;">
          <div>
            <div style="font-weight: 700;">{{ modalRecord.file_name }}</div>
            <div style="color:#666; margin-top: 4px;">
              默认系统 · {{ modalRecord.created_at }}
            </div>
          </div>
          <div style="display:flex; gap:8px;">
            <button class="btn btn-danger" @click="deleteRecord(modalRecord)">删除</button>
            <button class="btn btn-default" @click="closeModal">关闭</button>
          </div>
        </div>

        <div class="modal-body">
          <img class="modal-img" :src="modalRecord.file_url" :alt="modalRecord.file_name" />
          <div class="modal-side">
            <div class="form-group">
              <label>菜单结构</label>
              <div v-if="Array.isArray(modalRecord.menu_structure) && modalRecord.menu_structure.length">
                <div v-for="(m, idx) in modalRecord.menu_structure" :key="idx" style="padding: 6px 0; border-bottom: 1px solid #eee;">
                  第 {{ m.level }} 级：{{ m.name }}
                </div>
              </div>
              <div v-else style="color:#999;">无</div>
            </div>
            <div class="form-group">
              <label>ID</label>
              <div>{{ modalRecord.id }}</div>
            </div>
            <div class="form-group">
              <label>分析（已保存）</label>
              <div v-if="modalRecord.analysis" style="white-space: pre-wrap; font-size: 13px; color:#333; border:1px solid #eee; padding:10px; border-radius:8px; background:#fafafa;">
                {{ modalRecord.analysis }}
              </div>
              <div v-else style="color:#999;">暂无（可在“LLM分析系统交互”生成并保存）</div>
            </div>
          </div>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { useUiDialog } from '../composables/useUiDialog';
import TreeNode from './TreeNode.vue';

const records = ref([]);
const selectedSystem = ref('');
const selectedPath = ref([]); // menu names prefix
const modalRecord = ref(null);
const { alertDialog, confirmDialog } = useUiDialog();
const collapsedKeys = ref(new Set());

const fetchHistory = async () => {
  const response = await fetch('/api/history');
  if (!response.ok) throw new Error('获取历史记录失败');
  const data = await response.json();
  // Normalize fields used by UI
  records.value = (Array.isArray(data) ? data : []).map((r) => ({
    ...r,
    created_at: r.created_at || r.operation_time || '',
    file_url: r.file_url || (r.file_name ? `/uploads/${r.file_name}` : ''),
    analysis: r.analysis || ''
  }));
};

const systems = computed(() => {
  const set = new Set();
  for (const r of records.value) {
    if (r.system_name) set.add(r.system_name);
  }
  return Array.from(set).sort((a, b) => a.localeCompare(b));
});

const filteredBySystem = computed(() => {
  if (!selectedSystem.value) return records.value;
  return records.value.filter((r) => r.system_name === selectedSystem.value);
});

const filteredRecords = computed(() => {
  const base = filteredBySystem.value;
  if (!selectedPath.value.length) return base;
  return base.filter((r) => {
    const ms = Array.isArray(r.menu_structure) ? r.menu_structure : [];
    const names = ms.map((x) => x.name);
    // prefix match
    for (let i = 0; i < selectedPath.value.length; i++) {
      if (names[i] !== selectedPath.value[i]) return false;
    }
    return true;
  });
});

function breadcrumb(menuStructure) {
  return menuStructure.map((x) => x.name).filter(Boolean).join(' / ');
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
}

function onImgError(r) {
  // fallback to avoid broken images breaking layout
  if (r && r.file_name) r.file_url = `/uploads/${encodeURIComponent(r.file_name)}`;
}

const treeRoots = computed(() => {
  const base = filteredBySystem.value;
  const rootMap = new Map();
  const nodeMap = new Map();

  const ensureNode = (pathParts) => {
    const key = pathParts.join('>>');
    if (nodeMap.has(key)) return nodeMap.get(key);
    const node = {
      key,
      label: pathParts[pathParts.length - 1],
      depth: pathParts.length - 1,
      path: pathParts,
      count: 0,
      children: [],
      collapsed: collapsedKeys.value.has(key)
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
      node.count += 1;
      node.collapsed = collapsedKeys.value.has(node.key);
      if (path.length === 1) {
        rootMap.set(node.key, node);
      } else {
        const parent = ensureNode(path.slice(0, -1));
        if (!parent.children.find((c) => c.key === node.key)) parent.children.push(node);
      }
    }
  }

  const sortRec = (nodes) => {
    nodes.sort((a, b) => a.label.localeCompare(b.label));
    for (const n of nodes) sortRec(n.children);
  };

  const roots = Array.from(rootMap.values());
  sortRec(roots);
  return roots;
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

onMounted(async () => {
  try {
    await fetchHistory();
  } catch (e) {
    console.error(e);
  }
});

// 联动：上传/编辑/删除后自动刷新
window.addEventListener('history-updated', () => {
  fetchHistory().catch(() => {});
});

async function deleteRecord(r) {
  if (!r?.id) return;
  if (
    !(await confirmDialog('确定要删除这张截图记录吗？\n删除后无法恢复。', {
      title: '请确认操作',
      confirmText: '删除',
      cancelText: '取消',
    }))
  )
    return;
  const resp = await fetch(`/api/history/${r.id}`, { method: 'DELETE' });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    await alertDialog(err.error || '删除失败');
    return;
  }
  if (modalRecord.value?.id === r.id) modalRecord.value = null;
  window.dispatchEvent(new Event('history-updated'));
}

</script>

<style scoped>
.gallery { min-height: 100vh; }
.gallery-layout { display: grid; grid-template-columns: 320px 1fr; gap: 16px; }
.sidebar { position: sticky; top: 12px; align-self: start; z-index: 2; background: #fff; }
.content { position: relative; z-index: 1; }
.tree { max-height: 520px; overflow: auto; border: 1px solid #eee; border-radius: 8px; padding: 8px; background: #fafafa; }
.tree-node { display:flex; justify-content: space-between; gap: 8px; padding: 8px 10px; border-radius: 6px; cursor: pointer; user-select: none; }
.tree-node:hover { background: #f0f7ff; }
.tree-node.active { background: #e6f7ff; color: #1677ff; }
.tree-node.prefixActive { background: #f5faff; }
.tree-label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tree-count { color:#999; }
.tree-toggle { display:inline-block; width: 18px; color:#666; margin-right: 6px; }
.tree-toggle-placeholder { display:inline-block; width: 18px; margin-right: 6px; }
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

@media (max-width: 980px) {
  .gallery-layout { grid-template-columns: 1fr; }
  .sidebar { position: static; }
  .modal-body { grid-template-columns: 1fr; }
  .modal-side { border-left: 0; padding-left: 0; border-top: 1px solid #eee; padding-top: 12px; }
}
</style>

