<template>
  <div class="case-mgmt">
    <div class="page-header">
      <h1>{{ onlyExecution ? '执行用例' : '用例管理' }}</h1>
      <p v-if="onlyExecution">独立记录执行结果（用例管理层级下）</p>
      <p v-else>参考禅道：执行预览 / 用例生成 / 用例新增 / 用例库</p>
    </div>

    <div class="card zt-tabs">
      <div class="zt-tabbar">
        <button class="zt-tab" :class="{ active: activeTab === 'preview' }" @click="activeTab = 'preview'">
          {{ onlyExecution ? '执行用例记录' : '执行预览' }}
        </button>
        <button v-if="!onlyExecution" class="zt-tab" :class="{ active: activeTab === 'generate' }" @click="activeTab = 'generate'">用例生成</button>
        <button v-if="!onlyExecution" class="zt-tab" :class="{ active: activeTab === 'create' }" @click="activeTab = 'create'">用例新增</button>
        <button v-if="!onlyExecution" class="zt-tab" :class="{ active: activeTab === 'library' }" @click="activeTab = 'library'">用例库</button>
        <div style="flex:1;"></div>
        <button class="btn btn-default" @click="refreshAll" :disabled="isPageBusy">{{ isPageBusy ? '刷新中...' : '刷新' }}</button>
      </div>
    </div>

    <div class="zt-layout">
      <aside class="zt-side card">
        <div style="font-weight:700;">被测子菜单</div>
        <div class="form-group" style="margin-top:10px;">
          <label>树状筛选</label>
          <div class="zt-tree">
            <template v-for="node in treeRootsAll" :key="node.key">
              <TreeNode :node="node" :active-path="selectedPath" @toggle="toggleNode" @select="selectPath" />
            </template>
            <div v-if="treeRootsAll.length === 0" style="color:#999;">暂无截图记录</div>
          </div>
        </div>
        <div class="selected-path-tip">
          已选中：{{ selectedPath.length ? selectedPath.join(' / ') : '全部子菜单' }}
        </div>
        <div style="display:flex; gap:8px; flex-wrap:wrap;">
          <button class="btn btn-default" @click="clearPath" :disabled="isPageBusy">清空筛选</button>
        </div>
        <div style="margin-top:10px; color:#999; font-size:12px;">
          当前筛选：{{ selectedPath.length ? selectedPath.join(' / ') : '全部' }}
        </div>
      </aside>

      <section class="zt-main">
        <!-- 标签 1：执行预览 -->
        <div class="card" v-if="activeTab === 'preview'">
          <div class="zt-title">执行预览</div>

          <div class="zt-metrics">
            <div class="zt-metric">
              <div class="k">总用例</div>
              <div class="v">{{ filteredCasesByMenu.length }}</div>
            </div>
            <div class="zt-metric">
              <div class="k">通过</div>
              <div class="v">{{ filteredCasesByMenu.filter(c=>c.status==='pass').length }}</div>
            </div>
            <div class="zt-metric">
              <div class="k">失败</div>
              <div class="v">{{ filteredCasesByMenu.filter(c=>c.status==='fail').length }}</div>
            </div>
            <div class="zt-metric">
              <div class="k">阻塞</div>
              <div class="v">{{ filteredCasesByMenu.filter(c=>c.status==='blocked').length }}</div>
            </div>
            <div class="zt-metric">
              <div class="k">未执行</div>
              <div class="v">{{ filteredCasesByMenu.filter(c=>c.status==='draft').length }}</div>
            </div>
          </div>

          <div class="zt-filterbar">
            <select class="input" v-model="filterStatus" style="max-width:200px;">
              <option value="">全部状态</option>
              <option value="draft">未执行(draft)</option>
              <option value="pass">通过(pass)</option>
              <option value="fail">失败(fail)</option>
              <option value="blocked">阻塞(blocked)</option>
            </select>
            <input class="input" v-model="keyword" placeholder="按标题搜索" style="max-width:360px;" />
          </div>

          <div class="zt-tablewrap">
            <table class="table">
              <thead>
                <tr>
                  <th style="width:90px;">ID</th>
                  <th>标题</th>
                  <th style="width:120px;">状态</th>
                  <th style="width:180px;">最近执行</th>
                  <th style="width:260px;">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="c in previewList" :key="c.id">
                  <td>{{ c.id }}</td>
                  <td>
                    <div style="font-weight:600;">{{ c.title }}</div>
                    <div style="color:#666; font-size:12px; margin-top:4px;">截图ID：{{ c.history_id || '-' }}</div>
                  </td>
                  <td><span class="tag" :class="statusTagClass(c.status)">{{ c.status }}</span></td>
                  <td>{{ c.last_run_at || '-' }}</td>
                  <td>
                    <div style="display:flex; gap:8px; flex-wrap:wrap;">
                      <button class="btn btn-default" @click="openEdit(c)" :disabled="isPageBusy">编辑</button>
                      <button class="btn btn-default" @click="openExecute(c)" :disabled="isPageBusy">执行</button>
                      <button class="btn btn-danger" @click="deleteCase(c)" :disabled="isPageBusy">删除</button>
                    </div>
                  </td>
                </tr>
                <tr v-if="previewList.length === 0">
                  <td colspan="5" style="text-align:center; color:#999;">暂无数据</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- 标签 2：用例生成（智能） -->
        <div class="card" v-else-if="activeTab === 'generate'">
          <div class="zt-title">用例生成（LLM/智能）</div>
          <div style="color:#666; font-size:13px; margin-top:6px;">仅展示“补录完成”的截图（按钮或字段），避免生成拦截。</div>

          <div style="display:grid; grid-template-columns: 1fr 360px; gap:16px; margin-top: 12px;">
            <div class="zt-panel">
              <div style="display:flex; justify-content:space-between; gap:12px; align-items:center;">
                <div style="font-weight:700;">可生成用例模块</div>
                <div style="color:#999;">{{ filteredHistoryCandidates.length }} 条</div>
              </div>
              <div class="zt-scroll" style="margin-top:10px;">
                <div v-if="filteredHistoryCandidates.length === 0" style="color:#999;">暂无（请先在“手动补录/OCR补录”完成按钮或字段）</div>
                <div
                  v-for="h in filteredHistoryCandidates"
                  :key="h.id"
                  class="zt-item"
                  :class="{ active: selectedHistoryId === String(h.id) }"
                  @click="selectedHistoryId = String(h.id)"
                >
                  <div class="t">{{ h.file_name }}</div>
                  <div class="s">{{ breadcrumb(h.menu_structure) || '无' }}</div>
                </div>
              </div>
            </div>

            <div class="zt-panel">
              <div style="font-weight:700;">操作</div>
              <div style="margin-top:6px; color:#666; font-size:12px;">
                已生成用例：<b>{{ selectedHistoryCases.length }}</b> 条
              </div>
              <div style="margin-top:10px; display:flex; gap:12px; flex-wrap:wrap;">
                <button class="btn btn-primary" @click="generateCases" :disabled="!selectedHistoryId || isPageBusy">
                  {{ isGenerating ? '生成中...' : '生成用例' }}
                </button>
              </div>
              <div style="margin-top:10px; color:#999; font-size:12px;">
                生成后可在下方用例列表直接编辑/执行。
              </div>
              <div style="margin-top: 16px; font-weight:700;">该截图用例</div>
              <div class="zt-scroll" style="margin-top:10px;">
                <div v-if="selectedHistoryCases.length === 0" style="color:#999;">暂无用例</div>
                <div v-for="c in selectedHistoryCases" :key="c.id" class="zt-item">
                  <div class="t">{{ c.title }}</div>
                  <div class="s">
                    <span class="tag" :class="statusTagClass(c.status)">{{ c.status }}</span>
                    <span style="margin-left:8px; color:#999;">{{ c.last_run_at || '-' }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 标签 3：用例新增 -->
        <div class="card" v-else-if="activeTab === 'create'">
          <div class="zt-title">用例新增（手工）</div>
          <div style="display:flex; gap:12px; flex-wrap:wrap; margin-top:12px;">
            <select class="input" v-model="selectedHistoryId" style="max-width: 520px;">
              <option value="">请选择被测子菜单对应截图</option>
              <option v-for="h in filteredHistoriesAll" :key="h.id" :value="String(h.id)">
                {{ h.created_at }} - {{ h.file_name }}
              </option>
            </select>
            <button class="btn btn-primary" @click="openCreateForSelected" :disabled="!selectedHistoryId || isPageBusy">新建用例</button>
          </div>
          <div style="margin-top:10px; color:#999; font-size:12px;">
            建议先选择左侧树状子菜单（会自动筛选下拉列表），再新增用例。
          </div>
        </div>

        <!-- 标签 4：用例库 -->
        <div class="card" v-else>
          <div class="zt-title">用例库</div>
          <div class="zt-filterbar">
            <select class="input" v-model="filterStatus" style="max-width:200px;">
              <option value="">全部状态</option>
              <option value="draft">draft</option>
              <option value="pass">pass</option>
              <option value="fail">fail</option>
              <option value="blocked">blocked</option>
            </select>
            <input class="input" v-model="keyword" placeholder="按标题搜索" style="max-width:360px;" />
          </div>
          <div class="zt-tablewrap">
            <table class="table">
              <thead>
                <tr>
                  <th style="width:90px;">ID</th>
                  <th>标题</th>
                  <th style="width:120px;">状态</th>
                  <th style="width:180px;">最近执行</th>
                  <th style="width:260px;">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="c in libraryList" :key="c.id">
                  <td>{{ c.id }}</td>
                  <td>
                    <div style="font-weight:600;">{{ c.title }}</div>
                    <div style="color:#666; font-size:12px; margin-top:4px;">截图ID：{{ c.history_id || '-' }}</div>
                  </td>
                  <td><span class="tag" :class="statusTagClass(c.status)">{{ c.status }}</span></td>
                  <td>{{ c.last_run_at || '-' }}</td>
                  <td>
                    <div style="display:flex; gap:8px; flex-wrap:wrap;">
                      <button class="btn btn-default" @click="openEdit(c)" :disabled="isPageBusy">编辑</button>
                      <button class="btn btn-default" @click="openExecute(c)" :disabled="isPageBusy">执行</button>
                      <button class="btn btn-danger" @click="deleteCase(c)" :disabled="isPageBusy">删除</button>
                    </div>
                  </td>
                </tr>
                <tr v-if="libraryList.length === 0">
                  <td colspan="5" style="text-align:center; color:#999;">暂无数据</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </div>

    <!-- 编辑/新建 -->
    <div class="modal-mask" v-if="editorOpen" @click.self="closeEditor">
      <div class="modal card">
        <div style="display:flex; justify-content: space-between; align-items:center; gap:12px;">
          <div style="font-weight:700;">{{ editForm.id ? '编辑用例' : '新建用例' }}</div>
          <button class="btn btn-default" @click="closeEditor" :disabled="isPageBusy">关闭</button>
        </div>

        <div style="margin-top: 12px;">
          <div class="form-group">
            <label>标题</label>
            <input class="input" v-model="editForm.title" />
          </div>
          <div class="form-group">
            <label>前置条件</label>
            <textarea v-model="editForm.preconditions" placeholder="例如：已登录且有权限"></textarea>
          </div>
          <div class="form-group">
            <label>步骤（每行一步）</label>
            <textarea v-model="stepsText" placeholder="1. ...&#10;2. ..."></textarea>
          </div>
          <div class="form-group">
            <label>预期结果</label>
            <textarea v-model="editForm.expected"></textarea>
          </div>
          <div class="form-group">
            <label>关联截图ID（可空）</label>
            <input class="input" v-model="editForm.history_id" placeholder="例如：1" :disabled="lockHistoryId" />
          </div>
        </div>

        <div style="display:flex; gap:12px;">
          <button class="btn btn-primary" @click="saveCase" :disabled="isPageBusy">{{ isSaving ? '保存中...' : '保存' }}</button>
          <button class="btn btn-default" @click="closeEditor" :disabled="isPageBusy">取消</button>
        </div>
      </div>
    </div>

    <!-- 执行 -->
    <div class="modal-mask" v-if="executeOpen" @click.self="closeExecute">
      <div class="modal card execute-modal">
        <div class="execute-head" style="display:flex; justify-content: space-between; align-items:center; gap:12px;">
          <div style="font-weight:700;">执行用例</div>
          <button class="btn btn-default" @click="closeExecute" :disabled="isRunning">关闭</button>
        </div>
        <div class="execute-body" style="margin-top: 12px;">
          <div class="execute-title" style="font-weight: 600;">标题：{{ executing?.title || '-' }}</div>
          <div style="margin-top:8px; color:#444;">
            <b>前置条件：</b>{{ executing?.preconditions || '无' }}
          </div>

          <div class="zt-tablewrap" style="margin-top:12px; max-height: 42vh;">
            <table class="table execute-table">
              <thead>
                <tr>
                  <th style="width:70px;">#</th>
                  <th>步骤</th>
                  <th>预期结果</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in executeStepRows" :key="row.idx">
                  <td>{{ row.idx }}</td>
                  <td>{{ row.step }}</td>
                  <td>{{ row.expected }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="execute-conclusion">
            <div style="font-weight:700;">执行结论</div>
            <div class="form-group" style="margin-top: 10px;">
              <label>测试结果</label>
              <select class="input" v-model="runStatus">
                <option value="pass">通过(pass)</option>
                <option value="fail">失败(fail)</option>
                <option value="blocked">阻塞(blocked)</option>
                <option value="draft">未执行(draft)</option>
              </select>
            </div>
            <div class="form-group">
              <label>实际情况</label>
              <textarea v-model="runNotes" placeholder="例如：失败原因/截图/环境信息" rows="6"></textarea>
            </div>
          </div>
        </div>
        <div class="execute-foot" style="display:flex; gap:12px;">
          <button class="btn btn-primary" @click="submitRun" :disabled="isRunning">{{ isRunning ? '提交中...' : '保存' }}</button>
          <button class="btn btn-default" @click="closeExecute" :disabled="isRunning">取消</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import TreeNode from './TreeNode.vue';
import { useUiDialog } from '../composables/useUiDialog';

const props = defineProps({
  initialTab: { type: String, default: 'preview' },
  onlyExecution: { type: Boolean, default: false },
});

const history = ref([]);
const cases = ref([]);

const allowedTabs = ['preview', 'generate', 'create', 'library'];
const initial = allowedTabs.includes(props.initialTab) ? props.initialTab : 'preview';
const activeTab = ref(props.onlyExecution ? 'preview' : initial); // preview | generate | create | library
const onlyExecution = computed(() => !!props.onlyExecution);

const collapsedKeys = ref(new Set());
const selectedPath = ref([]);

const selectedHistoryId = ref('');
const isGenerating = ref(false);
const isPageBusy = computed(() => isGenerating.value || isSaving.value);

const filterStatus = ref('');
const keyword = ref('');

const editorOpen = ref(false);
const executeOpen = ref(false);
const executing = ref(null);
const lockHistoryId = ref(false);

const editForm = ref({ id: null, title: '', preconditions: '', steps: [], expected: '', history_id: '' });
const stepsText = ref('');
const isSaving = ref(false);

const isRunning = ref(false);
const runStatus = ref('pass');
const runNotes = ref('');
const { alertDialog, confirmDialog } = useUiDialog();
const executeStepRows = computed(() => {
  const steps = Array.isArray(executing.value?.steps) ? executing.value.steps : [];
  const expected = String(executing.value?.expected || '-');
  if (!steps.length) return [{ idx: 1, step: '-', expected }];
  return steps.map((s, i) => ({ idx: i + 1, step: String(s || '-'), expected }));
});

const fetchHistory = async () => {
  const resp = await fetch('/api/history');
  if (!resp.ok) throw new Error('获取截图记录失败');
  const data = await resp.json();
  history.value = (Array.isArray(data) ? data : []).map((r) => ({
    ...r,
    created_at: r.created_at || r.operation_time || '',
  }));
};

const fetchCases = async () => {
  const resp = await fetch('/api/cases');
  if (!resp.ok) throw new Error('获取用例失败');
  const data = await resp.json();
  cases.value = Array.isArray(data) ? data : [];
};

const refreshAll = async () => {
  await Promise.all([fetchHistory(), fetchCases()]);
};

const breadcrumb = (menuStructure) => {
  return (Array.isArray(menuStructure) ? menuStructure : []).map((x) => x.name).filter(Boolean).join(' / ');
};

const isManualComplete = (m) => {
  const buttons = Array.isArray(m?.buttons) ? m.buttons : [];
  const fields = Array.isArray(m?.fields) ? m.fields : [];
  return buttons.length > 0 || fields.length > 0;
};

const completedHistories = computed(() => (Array.isArray(history.value) ? history.value : []).filter((h) => isManualComplete(h.manual)));

const treeRootsAll = computed(() => {
  const base = Array.isArray(history.value) ? history.value : [];
  const rootMap = new Map();
  const nodeMap = new Map();
  const historyMap = new Map();
  for (const h of base) historyMap.set(Number(h.id), h);

  // 统计“每个菜单路径节点”对应的用例总数（含其子节点）
  const caseCountMap = new Map();
  const caseList = Array.isArray(cases.value) ? cases.value : [];
  for (const c of caseList) {
    const hid = Number(c?.history_id || 0);
    if (!hid) continue;
    const h = historyMap.get(hid);
    if (!h) continue;
    const ms = Array.isArray(h.menu_structure) ? h.menu_structure : [];
    const names = ms.map((x) => x?.name).filter(Boolean);
    let p = [];
    for (const name of names) {
      p = [...p, name];
      const key = p.join('>>');
      caseCountMap.set(key, (caseCountMap.get(key) || 0) + 1);
    }
  }

  const ensureNode = (pathParts) => {
    const key = pathParts.join('>>');
    if (nodeMap.has(key)) return nodeMap.get(key);
    const node = {
      key,
      label: pathParts[pathParts.length - 1],
      depth: pathParts.length - 1,
      path: pathParts,
      count: caseCountMap.get(key) || 0,
      children: [],
      collapsed: collapsedKeys.value.has(key),
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
      node.collapsed = collapsedKeys.value.has(node.key);
      if (path.length === 1) rootMap.set(node.key, node);
      else {
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
function clearPath() {
  selectedPath.value = [];
  collapsedKeys.value = new Set();
}

const historyById = computed(() => {
  const m = new Map();
  for (const h of history.value) m.set(Number(h.id), h);
  return m;
});

const matchesSelectedPath = (h) => {
  if (!selectedPath.value.length) return true;
  const ms = Array.isArray(h?.menu_structure) ? h.menu_structure : [];
  const names = ms.map((x) => x.name);
  for (let i = 0; i < selectedPath.value.length; i++) if (names[i] !== selectedPath.value[i]) return false;
  return true;
};

const filteredHistoriesAll = computed(() => (Array.isArray(history.value) ? history.value : []).filter(matchesSelectedPath));
const filteredHistoryCandidates = computed(() => completedHistories.value.filter(matchesSelectedPath));

const filteredCasesByMenu = computed(() => {
  // Filter cases by selected menu path using history_id->history.menu_structure
  const list = Array.isArray(cases.value) ? cases.value : [];
  return list.filter((c) => {
    const hid = c.history_id;
    if (!hid) return !selectedPath.value.length; // only show unbound cases when no menu filter
    const h = historyById.value.get(Number(hid));
    if (!h) return false;
    return matchesSelectedPath(h);
  });
});

const applySearchFilter = (list) => {
  let out = list.slice();
  if (filterStatus.value) out = out.filter((c) => c.status === filterStatus.value);
  if (keyword.value.trim()) {
    const k = keyword.value.trim().toLowerCase();
    out = out.filter((c) => String(c.title || '').toLowerCase().includes(k));
  }
  return out;
};

const previewList = computed(() => applySearchFilter(filteredCasesByMenu.value));
const libraryList = computed(() => applySearchFilter(Array.isArray(cases.value) ? cases.value : []));

const selectedHistoryCases = computed(() => {
  const hid = Number(selectedHistoryId.value || 0);
  if (!hid) return [];
  return (Array.isArray(cases.value) ? cases.value : []).filter((c) => Number(c.history_id || 0) === hid);
});

const beep = () => {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const o = ctx.createOscillator();
    const g = ctx.createGain();
    o.type = 'sine';
    o.frequency.value = 880;
    g.gain.value = 0.05;
    o.connect(g);
    g.connect(ctx.destination);
    o.start();
    setTimeout(() => { o.stop(); ctx.close(); }, 120);
  } catch (_) {}
};

const generateCases = async () => {
  if (!selectedHistoryId.value) return;
  isGenerating.value = true;
  try {
    let resp = await fetch(`/api/cases/generate?history_id=${selectedHistoryId.value}`, { method: 'POST' });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      if (resp.status === 409) {
        beep();
        if (await confirmDialog(err.error || '已生成过，是否删除并重新生成？', { title: '请确认操作' })) {
          resp = await fetch(`/api/cases/generate?history_id=${selectedHistoryId.value}&force=1`, { method: 'POST' });
          if (!resp.ok) {
            const err2 = await resp.json().catch(() => ({}));
            throw new Error(err2.error || '重新生成失败');
          }
        } else return;
      } else {
        throw new Error(err.error || '生成失败');
      }
    }
    await Promise.all([fetchCases(), fetchHistory()]);
    // 生成完成后清理筛选并切到用例库，便于立即查询
    filterStatus.value = '';
    keyword.value = '';
    if (!onlyExecution.value) activeTab.value = 'library';
    await alertDialog('已生成用例（已切换到用例库）');
  } catch (e) {
    console.error(e);
    await alertDialog(`生成失败: ${e.message}`);
  } finally {
    isGenerating.value = false;
  }
};

const statusTagClass = (s) => {
  if (s === 'pass') return 'tag-success';
  if (s === 'fail') return 'tag-danger';
  if (s === 'blocked') return 'tag-warning';
  return 'tag-info';
};

const openCreateForSelected = () => {
  if (!selectedHistoryId.value) return;
  editorOpen.value = true;
  lockHistoryId.value = true;
  editForm.value = { id: null, title: '', preconditions: '', steps: [], expected: '', history_id: String(selectedHistoryId.value) };
  stepsText.value = '';
};

const openEdit = (c) => {
  editorOpen.value = true;
  lockHistoryId.value = false;
  editForm.value = {
    id: c.id,
    title: c.title || '',
    preconditions: c.preconditions || '',
    steps: Array.isArray(c.steps) ? c.steps : [],
    expected: c.expected || '',
    history_id: c.history_id ? String(c.history_id) : '',
  };
  stepsText.value = (Array.isArray(editForm.value.steps) ? editForm.value.steps : []).join('\n');
};

const closeEditor = () => { editorOpen.value = false; };

const saveCase = async () => {
  isSaving.value = true;
  try {
    const steps = stepsText.value.split('\n').map((s) => s.trim()).filter(Boolean);
    const payload = {
      title: editForm.value.title,
      preconditions: editForm.value.preconditions,
      steps,
      expected: editForm.value.expected,
      history_id: editForm.value.history_id ? Number(editForm.value.history_id) : null,
    };

    let resp;
    if (editForm.value.id) {
      resp = await fetch(`/api/cases/${editForm.value.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    } else {
      resp = await fetch('/api/cases', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    }
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.error || '保存失败');
    }
    await fetchCases();
    closeEditor();
    await alertDialog('保存成功');
  } catch (e) {
    console.error(e);
    await alertDialog(`保存失败: ${e.message}`);
  } finally {
    isSaving.value = false;
  }
};

const deleteCase = async (c) => {
  if (
    !(await confirmDialog('确定删除该用例吗？\n删除后无法恢复。', {
      title: '请确认操作',
      confirmText: '删除',
      cancelText: '取消',
    }))
  )
    return;
  const resp = await fetch(`/api/cases/${c.id}`, { method: 'DELETE' });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    await alertDialog(err.error || '删除失败');
    return;
  }
  await fetchCases();
};

const openExecute = (c) => {
  executing.value = c;
  runStatus.value = c.status || 'pass';
  runNotes.value = c.run_notes || '';
  executeOpen.value = true;
};
const closeExecute = () => {
  executeOpen.value = false;
  executing.value = null;
  runNotes.value = '';
};

const submitRun = async () => {
  if (!executing.value) return;
  isRunning.value = true;
  try {
    const now = new Date().toLocaleString();
    const payload = { status: runStatus.value, run_notes: runNotes.value, last_run_at: now };
    const resp = await fetch(`/api/cases/${executing.value.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.error || '提交失败');
    }
    await fetchCases();
    closeExecute();
    await alertDialog('已记录执行结果');
  } catch (e) {
    console.error(e);
    await alertDialog(`提交失败: ${e.message}`);
  } finally {
    isRunning.value = false;
  }
};

onMounted(async () => {
  try { await refreshAll(); } catch (e) { console.error(e); }
});
</script>

<style scoped>
.case-mgmt { min-height: 100vh; }

.zt-tabs { padding: 10px 12px; }
.zt-tabbar { display:flex; gap: 8px; align-items:center; flex-wrap:wrap; }
.zt-tab { padding: 8px 12px; border-radius: 8px; border: 1px solid #e6e6e6; background:#fff; cursor:pointer; }
.zt-tab.active { background: #1677ff; border-color: #1677ff; color:#fff; }

.zt-layout { display:grid; grid-template-columns: 320px 1fr; gap: 16px; margin-top: 12px; }
.zt-side { position: sticky; top: 12px; align-self: start; z-index: 2; }
.zt-tree { max-height: 520px; overflow:auto; border: 1px solid #eee; border-radius: 8px; padding: 8px; background: #fafafa; margin-top: 8px; }
.selected-path-tip { margin-top: 6px; margin-bottom: 10px; padding: 8px 10px; border-radius: 8px; background: #f0f7ff; color:#1677ff; font-size:12px; border: 1px solid #d6e9ff; }

.zt-main { min-width: 0; }
.zt-title { font-weight: 800; font-size: 16px; }
.zt-metrics { display:grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; margin-top: 12px; }
.zt-metric { border:1px solid #eee; border-radius: 10px; padding: 10px; background:#fafafa; }
.zt-metric .k { color:#666; font-size: 12px; }
.zt-metric .v { font-weight: 800; font-size: 18px; margin-top: 6px; }

.zt-filterbar { display:flex; gap: 8px; flex-wrap:wrap; margin-top: 12px; }
.zt-tablewrap { margin-top: 12px; max-height: 62vh; overflow:auto; border: 1px solid #eee; border-radius: 10px; background:#fff; }

.zt-panel { border:1px solid #eee; border-radius: 10px; padding: 12px; background:#fff; }
.zt-scroll { max-height: 56vh; overflow:auto; border: 1px solid #eee; border-radius: 10px; padding: 8px; background:#fafafa; }
.zt-item { border:1px solid #eee; border-radius: 10px; padding: 10px; background:#fff; margin-top: 8px; cursor:pointer; }
.zt-item.active { border-color:#1677ff; box-shadow: 0 0 0 2px rgba(22,119,255,0.15); }
.zt-item .t { font-weight: 700; }
.zt-item .s { color:#666; font-size: 12px; margin-top: 6px; }

:deep(.tree-node) {
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:8px;
  padding:8px 10px;
  border-radius:8px;
  cursor:pointer;
  margin-top:4px;
  border:1px solid transparent;
}
:deep(.tree-node:hover) { background:#f5faff; border-color:#e6f2ff; }
:deep(.tree-node.active) {
  background:#e6f4ff;
  color:#1677ff;
  border-color:#91caff;
  box-shadow: 0 0 0 2px rgba(22,119,255,0.12);
}
:deep(.tree-node.prefixActive) {
  background:#f7fbff;
  border-color:#d6e9ff;
}
:deep(.tree-label) { display:flex; align-items:center; gap:6px; min-width:0; }
:deep(.tree-count) { color:#999; font-size:12px; }

.modal-mask { position: fixed; inset: 0; background: rgba(0,0,0,0.45); display:flex; align-items: center; justify-content: center; padding: 24px; z-index: 60; }
.modal { width: min(1000px, 100%); max-height: 80vh; overflow:auto; }
.execute-modal { max-height: 88vh; overflow: hidden; display:flex; flex-direction:column; }
.execute-head { flex: 0 0 auto; }
.execute-body { flex: 1 1 auto; overflow: auto; min-height: 0; padding-right: 2px; }
.execute-foot { flex: 0 0 auto; margin-top: 12px; padding-top: 8px; border-top: 1px solid #f0f0f0; }
.execute-title { white-space: normal; word-break: break-all; line-height: 1.5; }
.execute-conclusion { margin-top: 12px; border: 1px solid #eee; border-radius: 8px; background:#fafafa; padding: 12px; }
.execute-table td { vertical-align: top; line-height: 1.5; }

@media (max-width: 980px) {
  .zt-layout { grid-template-columns: 1fr; }
  .zt-side { position: static; }
  .zt-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
