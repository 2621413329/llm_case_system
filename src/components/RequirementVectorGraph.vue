<template>
  <div class="vec-graph">
    <div class="page-header">
      <h1>需求向量库可视化</h1>
      <p>
        面向「需求网络 + MySQL 向量库」的可观测与调试：嵌入分布（降维）、语义相似度网络、检索 query 解释、以及业务结构边。请先完成「产生向量库」并启用 MySQL。
      </p>
    </div>

    <div class="card toolbar">
      <div class="toolbar-row">
        <div class="form-group grow">
          <label>需求记录</label>
          <select v-model="selectedId" class="input" :disabled="historyLoading" @change="onRecordChange">
            <option value="">请选择</option>
            <option v-for="r in records" :key="`vg-${r.id}`" :value="String(r.id)">
              #{{ r.id }} {{ r.created_at }} — {{ displayTitle(r.file_name) }}
            </option>
          </select>
        </div>
        <button type="button" class="btn btn-default" :disabled="historyLoading" @click="loadHistory">刷新列表</button>
      </div>

      <div class="tabs">
        <button
          v-for="t in tabDefs"
          :key="t.id"
          type="button"
          class="tab"
          :class="{ active: activeTab === t.id }"
          :disabled="!selectedId && t.id !== 'debug'"
          @click="activeTab = t.id"
        >
          {{ t.label }}
        </button>
      </div>
    </div>

    <!-- 嵌入分布 -->
    <div v-show="activeTab === 'embed'" class="card panel">
      <div class="panel-head">
        <h2>嵌入分布（2D）</h2>
        <div class="panel-actions">
          <select v-model="embedMethod" class="input input-sm">
            <option value="tsne">t-SNE</option>
            <option value="umap">UMAP（需安装 umap-learn）</option>
            <option value="pca">PCA</option>
          </select>
          <button type="button" class="btn btn-primary" :disabled="!selectedId || embedLoading" @click="loadEmbed">
            {{ embedLoading ? '计算中…' : '加载散点' }}
          </button>
        </div>
      </div>
      <p class="hint">将每条 unit 的向量降至二维；颜色表示 unit_type，悬停查看原文。用于观察类内聚集与类间分离。</p>
      <div v-if="embedError" class="err">{{ embedError }}</div>
      <div v-if="embedLoading" class="state-muted">正在降维…</div>
      <div v-else-if="embedPoints.length" class="svg-wrap">
        <svg class="network-svg" viewBox="0 0 1000 620" xmlns="http://www.w3.org/2000/svg">
          <rect width="1000" height="620" fill="#f8fafc" rx="8" />
          <g v-for="(p, i) in embedPoints" :key="`ep-${i}-${p.unit_key}`">
            <circle
              :cx="p.x * 1000"
              :cy="p.y * 620"
              r="9"
              :fill="colorForType(p.unit_type)"
              :stroke="isSemanticAnomaly(p) ? '#ff4d4f' : '#fff'"
              :stroke-width="isSemanticAnomaly(p) ? 3 : 2"
              @mouseenter="hoverEmbed = p"
              @mouseleave="hoverEmbed = null"
              @click="openEmbedDetail(p)"
              style="cursor:pointer;"
            />
          </g>
        </svg>
        <div v-if="hoverEmbed" class="tooltip card">
          <div class="tt-block">
            <div class="tt-row"><span class="tt-k">【语义】</span><span class="tt-v">{{ hoverEmbed.short_text || hoverEmbed.content }}</span></div>
            <div class="tt-row"><span class="tt-k">【类型】</span><span class="tt-v">{{ hoverEmbed.unit_type }}</span></div>
            <div class="tt-row"><span class="tt-k">【相似】</span><span class="tt-v">{{ formatTop3(hoverEmbed.top3_similar) }}</span></div>
            <div v-if="isSemanticAnomaly(hoverEmbed)" class="tt-warn">⚠ 语义异常点（similarity &lt; 0.5）</div>
          </div>
        </div>
      </div>
      <div v-else-if="selectedId && !embedLoading" class="state-muted">点击「加载散点」或暂无足够向量。</div>
      <div v-if="embedMeta.method" class="meta-line">方法：{{ embedMeta.method }} · {{ embedMeta.model || '—' }}</div>
    </div>

    <!-- 嵌入散点：详情弹窗 -->
    <div class="modal-mask" v-if="embedDetailOpen && embedDetail" @click.self="closeEmbedDetail">
      <div class="modal card">
        <div style="display:flex; justify-content: space-between; align-items:center; gap:12px;">
          <div style="font-weight:700;">详情</div>
          <button class="btn btn-default" type="button" @click="closeEmbedDetail">关闭</button>
        </div>
        <div style="margin-top:8px; color:#999; font-size:12px;">
          <span>类型：{{ embedDetail.unit_type }}</span>
          <span style="margin-left:10px;">unit_key：{{ embedDetail.unit_key }}</span>
          <span v-if="embedDetailBestSim != null" style="margin-left:10px;">best similarity：{{ embedDetailBestSim.toFixed?.(4) ?? embedDetailBestSim }}</span>
        </div>

        <div class="detail-section">
          <div class="detail-title">原始文本</div>
          <pre class="detail-pre">{{ embedDetail.extracted_text || embedDetail.normalized_text || embedDetail.short_text || embedDetail.content }}</pre>
        </div>
        <div class="detail-section">
          <div class="detail-title">完整上下文</div>
          <pre class="detail-pre">{{ embedDetail.content }}</pre>
        </div>
        <div class="detail-section">
          <div class="detail-title">来源路径</div>
          <div class="detail-kv">
            <div class="kv"><span class="k">system</span><span class="v">{{ sourceCtx(embedDetail).system || '—' }}</span></div>
            <div class="kv"><span class="k">menu</span><span class="v">{{ sourceCtx(embedDetail).menu || '—' }}</span></div>
            <div class="kv"><span class="k">file</span><span class="v">{{ sourceCtx(embedDetail).file || '—' }}</span></div>
          </div>
        </div>
      </div>
    </div>

    <!-- 相似度网络 -->
    <div v-show="activeTab === 'sim'" class="card panel">
      <div class="panel-head">
        <h2>相似度语义网络</h2>
        <button type="button" class="btn btn-primary" :disabled="!selectedId || simLoading" @click="loadSim">
          {{ simLoading ? '构建中…' : '加载语义边' }}
        </button>
      </div>
      <p class="hint">在同一 history 下，若两节点余弦相似度同时高于各自类型阈值则连边；边宽表示相似度。</p>
      <div v-if="simError" class="err">{{ simError }}</div>
      <div v-if="simLoading" class="state-muted">计算中…</div>
      <div v-else-if="simNodes.length" class="svg-wrap">
        <svg class="network-svg" viewBox="0 0 1000 620" xmlns="http://www.w3.org/2000/svg" @mouseleave="hoverSim = null">
          <rect width="1000" height="620" fill="#f8fafc" rx="8" />
          <g v-for="(e, ei) in simEdges" :key="`se-${ei}`">
            <line
              :x1="(nodeByKey(e.from_unit_key)?.x ?? 0.5) * 1000"
              :y1="(nodeByKey(e.from_unit_key)?.y ?? 0.5) * 620"
              :x2="(nodeByKey(e.to_unit_key)?.x ?? 0.5) * 1000"
              :y2="(nodeByKey(e.to_unit_key)?.y ?? 0.5) * 620"
              :stroke-width="1 + (e.similarity || 0) * 4"
              stroke="#94a3b8"
              opacity="0.85"
            />
          </g>
          <g v-for="n in simNodes" :key="`sn-${n.unit_key}`">
            <circle
              :cx="(n.x ?? 0.5) * 1000"
              :cy="(n.y ?? 0.5) * 620"
              :r="hoverSim?.unit_key === n.unit_key ? 12 : 8"
              :fill="colorForType(n.unit_type)"
              stroke="#fff"
              stroke-width="2"
              @mouseenter="hoverSim = n"
              @click="openEmbedDetail(n)"
              style="cursor:pointer;"
            />
          </g>
        </svg>
        <div v-if="hoverSim" class="tooltip card">
          <div class="tt-type">{{ hoverSim.unit_type }}</div>
          <div class="tt-content">{{ displayUnitText(hoverSim) }}</div>
        </div>
      </div>
      <div v-else-if="selectedId && !simLoading" class="state-muted">点击「加载语义边」。</div>
    </div>

    <!-- 检索调试 -->
    <div v-show="activeTab === 'debug'" class="card panel">
      <div class="panel-head">
        <h2>检索调试（query → topK）</h2>
      </div>
      <div class="detail-section" style="margin-top:10px;">
        <div class="detail-title">记录相似度（选几个记录对比）</div>
        <div class="debug-row" style="align-items:flex-start; gap:10px;">
          <textarea
            v-model="recordIdsText"
            class="textarea"
            rows="2"
            placeholder="输入多个 history_id，用英文逗号分隔，例如：12,15,18"
            style="flex:1;"
          />
          <button type="button" class="btn btn-default" :disabled="recordSimLoading" @click="runRecordSimilarity">
            {{ recordSimLoading ? '计算中…' : '计算相似度' }}
          </button>
        </div>
        <div v-if="recordSimError" class="err">{{ recordSimError }}</div>
        <div v-if="recordSimPairs.length" class="table-wrap" style="margin-top:8px;">
          <table class="data-table">
            <thead>
              <tr>
                <th>#</th>
                <th>A(history_id)</th>
                <th>B(history_id)</th>
                <th>相似度</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, idx) in recordSimPairs" :key="`rsp-${idx}`">
                <td>{{ idx + 1 }}</td>
                <td>{{ row.a }}</td>
                <td>{{ row.b }}</td>
                <td>{{ Number(row.similarity || 0).toFixed?.(4) ?? row.similarity }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="recordSimMeta.length" class="meta-line" style="margin-top:6px;">
          参与计算：{{ recordSimKept.join(', ') || '—' }}（无向量的记录会被跳过）
        </div>
      </div>
      <div class="debug-form">
        <textarea v-model="debugQuery" class="textarea" rows="3" placeholder="输入要调试的自然语言 query" />
        <div class="debug-row">
          <label>topK</label>
          <input v-model.number="debugTopK" type="number" min="1" max="50" class="input input-sm w80" />
          <label>低分阈值（标红）</label>
          <input v-model.number="debugLowTh" type="number" min="0" max="1" step="0.05" class="input input-sm w80" />
          <button type="button" class="btn btn-primary" :disabled="debugLoading || !debugQuery.trim()" @click="runDebug">
            {{ debugLoading ? '检索中…' : '执行调试' }}
          </button>
        </div>
        <p class="hint">对当前系统下已建库向量做检索；可限定 history（选上方记录时自动带上）。低于阈值的命中标记为异常。</p>
      </div>
      <div v-if="debugError" class="err">{{ debugError }}</div>
      <div v-if="debugRows.length" class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>#</th>
              <th>相似度</th>
              <th>类型</th>
              <th>异常</th>
              <th>内容摘要</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, idx) in debugRows" :key="`dr-${idx}`" :class="{ warn: row.anomaly_low_score }">
              <td>{{ idx + 1 }}</td>
              <td>{{ row.similarity?.toFixed?.(4) ?? row.similarity }}</td>
              <td>{{ row.unit_type }}</td>
              <td>{{ row.anomaly_low_score ? '是' : '否' }}</td>
              <td class="cell-content">{{ row.content }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="debugNote" class="meta-line">{{ debugNote }}</div>
    </div>

    <!-- 结构关系（业务边） -->
    <div v-show="activeTab === 'struct'" class="card panel">
      <div class="panel-head">
        <h2>结构关系（业务边）</h2>
        <button type="button" class="btn btn-primary" :disabled="!selectedId || structLoading" @click="loadStruct">
          {{ structLoading ? '加载中…' : '加载结构图' }}
        </button>
      </div>
      <p class="hint">展示 requirement_edges 中的业务关系（非纯语义相似边）。节点位置仍用向量前两维映射。</p>
      <div v-if="structError" class="err">{{ structError }}</div>
      <div v-if="structLoading" class="state-muted">加载中…</div>
      <div v-else-if="structUnits.length" class="svg-wrap">
        <svg class="network-svg" viewBox="0 0 1000 620" xmlns="http://www.w3.org/2000/svg" @mouseleave="hoverStruct = null">
          <rect width="1000" height="620" fill="#f8fafc" rx="8" />
          <g v-for="(e, ei) in structEdges" :key="`st-${ei}`">
            <line
              :x1="layoutXY(e.from_unit_key).x * 1000"
              :y1="layoutXY(e.from_unit_key).y * 620"
              :x2="layoutXY(e.to_unit_key).x * 1000"
              :y2="layoutXY(e.to_unit_key).y * 620"
              stroke="#cbd5e1"
              stroke-width="1.2"
            />
          </g>
          <g v-for="u in structUnits" :key="`su-${u.unit_key}`">
            <circle
              :cx="layoutXY(u.unit_key).x * 1000"
              :cy="layoutXY(u.unit_key).y * 620"
              :r="hoverStruct?.unit_key === u.unit_key ? 11 : 8"
              :fill="colorForType(u.unit_type)"
              stroke="#fff"
              stroke-width="2"
              @mouseenter="hoverStruct = u"
              @click="openEmbedDetail(u)"
              style="cursor:pointer;"
            />
          </g>
        </svg>
        <div v-if="hoverStruct" class="tooltip card">
          <div class="tt-type">{{ hoverStruct.unit_type }}</div>
          <div class="tt-content">{{ displayUnitText(hoverStruct) }}</div>
        </div>
      </div>
      <div v-else-if="selectedId && !structLoading" class="state-muted">点击「加载结构图」。</div>
    </div>

    <!-- 全量网络图（跨多个 history 聚合） -->
    <div v-show="activeTab === 'all'" class="card panel">
      <div class="panel-head">
        <h2>全量需求网络图（聚合）</h2>
        <button type="button" class="btn btn-primary" :disabled="allLoading" @click="loadAllGraph">
          {{ allLoading ? '加载中…' : '加载全量网络' }}
        </button>
      </div>
      <p class="hint">
        聚合当前库中已建库的需求单元与业务边（默认取最近写入的部分节点以避免卡顿）。建议先选择 system 再加载。
      </p>
      <div v-if="allError" class="err">{{ allError }}</div>
      <div v-if="allLoading" class="state-muted">加载中…</div>
      <div v-else-if="allUnits.length" class="svg-wrap">
        <svg class="network-svg" viewBox="0 0 1000 620" xmlns="http://www.w3.org/2000/svg" @mouseleave="hoverAll = null">
          <rect width="1000" height="620" fill="#f8fafc" rx="8" />
          <g v-for="(e, ei) in allEdges" :key="`ae-${ei}`">
            <line
              :x1="layoutAllXY(allEdgeFromKey(e)).x * 1000"
              :y1="layoutAllXY(allEdgeFromKey(e)).y * 620"
              :x2="layoutAllXY(allEdgeToKey(e)).x * 1000"
              :y2="layoutAllXY(allEdgeToKey(e)).y * 620"
              stroke="#cbd5e1"
              stroke-width="1"
              opacity="0.7"
            />
          </g>
          <g v-for="u in allUnits" :key="`au-${allNodeKey(u)}`">
            <circle
              :cx="layoutAllXY(allNodeKey(u)).x * 1000"
              :cy="layoutAllXY(allNodeKey(u)).y * 620"
              :r="(hoverAll && allNodeKey(hoverAll) === allNodeKey(u)) ? 10 : 7"
              :fill="colorForType(u.unit_type)"
              stroke="#fff"
              stroke-width="2"
              @mouseenter="hoverAll = u"
              @click="openEmbedDetail(u)"
              style="cursor:pointer;"
            />
          </g>
        </svg>
        <div v-if="hoverAll" class="tooltip card">
          <div class="tt-type">{{ hoverAll.unit_type }}</div>
          <div class="tt-content">{{ displayUnitText(hoverAll) }}</div>
        </div>
      </div>
      <div v-else-if="!allLoading" class="state-muted">点击「加载全量网络」。</div>
      <div v-if="allUnits.length" class="meta-line">
        节点：{{ allUnits.length }} · 边：{{ allEdges.length }}
      </div>
    </div>

    <!-- 库对账（定位写入的 history_id） -->
    <div v-show="activeTab === 'counts'" class="card panel">
      <div class="panel-head">
        <h2>库对账（MySQL）</h2>
        <button type="button" class="btn btn-primary" :disabled="countsLoading" @click="loadCounts">
          {{ countsLoading ? '加载中…' : '刷新统计' }}
        </button>
      </div>
      <p class="hint">用于排查「我已建库但当前记录查不到」：这里列出数据库里实际写入了网络数据的 history_id 及数量。</p>
      <div v-if="countsError" class="err">{{ countsError }}</div>
      <div v-else-if="countsLoading" class="state-muted">正在读取统计…</div>
      <div v-else-if="countsRows.length" class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>history_id</th>
              <th>units</th>
              <th>embeddings</th>
              <th>edges</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in countsRows" :key="`cr-${row.history_id}`">
              <td>#{{ row.history_id }}</td>
              <td>{{ row.units_total }}</td>
              <td>{{ row.embeddings_total }}</td>
              <td>{{ row.edges_total }}</td>
              <td>
                <button type="button" class="btn btn-default" @click="selectedId = String(row.history_id); activeTab = 'embed'">
                  切换到该记录
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { useSystemStore } from '../stores/system';
import { useUiDialog } from '../composables/useUiDialog';
import { listHistory } from '../api/history';
import {
  fetchRequirementNetworkGraph,
  fetchRequirementNetworkGraphAll,
  fetchEmbeddings2d,
  fetchSimilarityGraph,
  fetchRecordSimilarity,
  debugVectorQuery,
  fetchRequirementNetworkCounts,
} from '../api/requirement';

const systemStore = useSystemStore();
const route = useRoute();
const { alertDialog } = useUiDialog();

const tabDefs = [
  { id: 'embed', label: '嵌入分布' },
  { id: 'sim', label: '相似度网络' },
  { id: 'debug', label: '检索调试' },
  { id: 'struct', label: '结构关系' },
  { id: 'all', label: '全量网络图' },
  { id: 'counts', label: '库对账' },
];

const records = ref([]);
const selectedId = ref('');
const historyLoading = ref(false);
const activeTab = ref('embed');

function syncTabFromQuery() {
  const tab = String(route.query.tab || '').trim();
  if (['embed', 'sim', 'debug', 'struct'].includes(tab)) activeTab.value = tab;
}

syncTabFromQuery();
watch(() => route.query.tab, syncTabFromQuery);

const embedMethod = ref('tsne');
const embedLoading = ref(false);
const embedError = ref('');
const embedPoints = ref([]);
const embedMeta = ref({ method: '', model: '' });
const hoverEmbed = ref(null);
const embedDetailOpen = ref(false);
const embedDetail = ref(null);
const embedDetailBestSim = computed(() => bestSimilarity(embedDetail.value));

const simLoading = ref(false);
const simError = ref('');
const simNodes = ref([]);
const simEdges = ref([]);
const hoverSim = ref(null);

const debugQuery = ref('');
const debugTopK = ref(12);
const debugLowTh = ref(0.5);
const debugLoading = ref(false);
const debugError = ref('');
const debugRows = ref([]);
const debugNote = ref('');

const recordIdsText = ref('');
const recordSimLoading = ref(false);
const recordSimError = ref('');
const recordSimPairs = ref([]);
const recordSimMeta = ref([]);
const recordSimKept = computed(() => {
  const arr = Array.isArray(recordSimMeta.value) ? recordSimMeta.value : [];
  return arr.filter((x) => String(x?.note || '').trim() === '').map((x) => Number(x.history_id));
});

const structLoading = ref(false);
const structError = ref('');
const structUnits = ref([]);
const structEdges = ref([]);
const hoverStruct = ref(null);
const structLayout = ref({});

const allLoading = ref(false);
const allError = ref('');
const allUnits = ref([]);
const allEdges = ref([]);
const hoverAll = ref(null);
const allLayout = ref({});

const countsLoading = ref(false);
const countsError = ref('');
const countsRows = ref([]);

function displayTitle(name) {
  return String(name || '').replace(/\.(png|jpg|jpeg|webp)$/i, '') || '—';
}

function colorForType(t) {
  const key = String(t || 'other');
  let h = 0;
  for (let i = 0; i < key.length; i += 1) {
    h = (h * 31 + key.charCodeAt(i)) % 360;
  }
  return `hsl(${h}, 58%, 46%)`;
}

function formatTop3(list) {
  const arr = Array.isArray(list) ? list : [];
  if (!arr.length) return '—';
  return arr
    .slice(0, 3)
    .map((x) => {
      const s = String(x?.short_text || x?.normalized_text || x?.extracted_text || x?.content || '').trim();
      return s || '—';
    })
    .filter(Boolean)
    .join('；');
}

function stripBaseContextFromContent(content) {
  const s = String(content || '').trim();
  if (!s || !s.includes(';') || !s.toLowerCase().includes('system=')) return s;
  const parts = s.split(';').map((x) => x.trim()).filter(Boolean);
  const dropKeys = ['system=', 'menu=', 'page=', 'file=', 'source=', 'label=', 'part_index='];
  const kept = [];
  for (const p of parts) {
    const lp = p.toLowerCase();
    if (dropKeys.some((k) => lp.startsWith(k))) continue;
    kept.push(p);
  }
  return (kept.join('; ').trim() || s);
}

function displayUnitText(u) {
  if (!u) return '';
  const best = String(u.extracted_text || u.normalized_text || u.short_text || '').trim();
  if (best) return best;
  return stripBaseContextFromContent(u.content);
}

function bestSimilarity(p) {
  if (!p) return null;
  if (p.best_similarity != null && p.best_similarity !== '') {
    const n = Number(p.best_similarity);
    if (Number.isFinite(n)) return n;
  }
  const arr = Array.isArray(p.top3_similar) ? p.top3_similar : [];
  if (arr.length && arr[0]?.score != null) {
    const n = Number(arr[0].score);
    if (Number.isFinite(n)) return n;
  }
  return null;
}

function parseSourceFromContent(content) {
  const s = String(content || '').trim();
  const out = { system: '', menu: '', file: '', page: '' };
  if (!s || !s.includes(';')) return out;
  const parts = s.split(';').map((x) => x.trim()).filter(Boolean);
  for (const p of parts) {
    const i = p.indexOf('=');
    if (i <= 0) continue;
    const k = p.slice(0, i).trim().toLowerCase();
    const v = p.slice(i + 1).trim();
    if (k in out && !out[k] && v) out[k] = v;
  }
  return out;
}

function sourceCtx(p) {
  const fromApi = p?.source_context || {};
  const ok = (k) => typeof fromApi?.[k] === 'string' && String(fromApi[k]).trim();
  if (ok('system') || ok('menu') || ok('file')) {
    return {
      system: String(fromApi.system || '').trim(),
      menu: String(fromApi.menu || '').trim(),
      file: String(fromApi.file || '').trim(),
      page: String(fromApi.page || '').trim(),
    };
  }
  return parseSourceFromContent(p?.content);
}

function isSemanticAnomaly(p) {
  const s = bestSimilarity(p);
  return s != null && s < 0.5;
}

function openEmbedDetail(p) {
  embedDetail.value = p || null;
  embedDetailOpen.value = true;
}
function closeEmbedDetail() {
  embedDetailOpen.value = false;
  embedDetail.value = null;
}

const nodeByKeyMap = computed(() => {
  const m = {};
  simNodes.value.forEach((n) => {
    m[n.unit_key] = n;
  });
  return m;
});

function nodeByKey(unitKey) {
  return nodeByKeyMap.value?.[unitKey];
}

function layoutXY(unitKey) {
  const xy = structLayout.value[unitKey];
  if (xy) return xy;
  return { x: 0.5, y: 0.5 };
}

function layoutAllXY(unitKey) {
  const xy = allLayout.value[unitKey];
  if (xy) return xy;
  return { x: 0.5, y: 0.5 };
}

function allNodeKey(u) {
  if (!u || typeof u !== 'object') return '';
  const nodeId = String(u.node_id || '').trim();
  if (nodeId) return nodeId;
  const historyId = Number(u.history_id);
  const unitKey = String(u.unit_key || '').trim();
  if (Number.isFinite(historyId) && unitKey) return `${historyId}:${unitKey}`;
  return unitKey;
}

function allEdgeFromKey(e) {
  if (!e || typeof e !== 'object') return '';
  const nodeId = String(e.from_node_id || '').trim();
  if (nodeId) return nodeId;
  const historyId = Number(e.history_id);
  const fromKey = String(e.from_unit_key || '').trim();
  if (Number.isFinite(historyId) && fromKey) return `${historyId}:${fromKey}`;
  return fromKey;
}

function allEdgeToKey(e) {
  if (!e || typeof e !== 'object') return '';
  const nodeId = String(e.to_node_id || '').trim();
  if (nodeId) return nodeId;
  const historyId = Number(e.history_id);
  const toKey = String(e.to_unit_key || '').trim();
  if (Number.isFinite(historyId) && toKey) return `${historyId}:${toKey}`;
  return toKey;
}

function buildLayoutMap(units, keyGetter = (u) => u.unit_key) {
  const emb = [];
  const keys = [];
  units.forEach((u) => {
    const k = String(keyGetter(u) || '').trim();
    if (!k) return;
    const e = u.embedding;
    if (Array.isArray(e) && e.length >= 2) {
      emb.push([e[0], e[1]]);
      keys.push(k);
    }
  });
  const map = {};
  if (!emb.length) {
    units.forEach((u, i) => {
      const k = String(keyGetter(u) || '').trim();
      if (!k) return;
      const n = Math.max(units.length, 1);
      const ang = (2 * Math.PI * i) / n;
      map[k] = { x: 0.5 + 0.35 * Math.cos(ang), y: 0.5 + 0.35 * Math.sin(ang) };
    });
    return map;
  }
  let min0 = Infinity;
  let max0 = -Infinity;
  let min1 = Infinity;
  let max1 = -Infinity;
  emb.forEach(([a, b]) => {
    min0 = Math.min(min0, a);
    max0 = Math.max(max0, a);
    min1 = Math.min(min1, b);
    max1 = Math.max(max1, b);
  });
  const pad = 0.08;
  const nx = (v, lo, hi) => (lo === hi ? 0.5 : pad + (1 - 2 * pad) * ((v - lo) / (hi - lo)));
  keys.forEach((k, i) => {
    const [a, b] = emb[i];
    map[k] = { x: nx(a, min0, max0), y: 1 - nx(b, min1, max1) };
  });
  return map;
}

async function loadHistory() {
  historyLoading.value = true;
  try {
    const params = {};
    if (systemStore.systemId) params.system_id = systemStore.systemId;
    const data = await listHistory(params);
    records.value = Array.isArray(data) ? data : [];
    if (selectedId.value && !records.value.some((r) => String(r.id) === String(selectedId.value))) {
      selectedId.value = '';
    }
  } catch (e) {
    await alertDialog(`加载历史失败：${e.message || e}`);
  } finally {
    historyLoading.value = false;
  }
}

function onRecordChange() {
  embedPoints.value = [];
  embedError.value = '';
  simNodes.value = [];
  simEdges.value = [];
  structUnits.value = [];
  structEdges.value = [];
  structLayout.value = {};
}

async function loadEmbed() {
  if (!selectedId.value) return;
  embedLoading.value = true;
  embedError.value = '';
  embedPoints.value = [];
  try {
    const body = { history_id: Number(selectedId.value), method: embedMethod.value };
    if (systemStore.systemId) body.system_id = systemStore.systemId;
    const data = await fetchEmbeddings2d(body);
    embedPoints.value = Array.isArray(data.points) ? data.points : [];
    embedMeta.value = { method: data.method || '', model: data.embedding_model || '' };
    if (!embedPoints.value.length && data.note === 'not_enough_vectors') {
      const total = Number(data.units_total ?? 0);
      const withEmb = Number(data.units_with_embedding ?? 0);
      const embeddingsTotal = Number(data.embeddings_total ?? 0);
      const edgesTotal = Number(data.edges_total ?? 0);
      if (total <= 0) {
        embedError.value = `该记录下没有需求单元数据（requirement_units: ${total}，requirement_embeddings: ${embeddingsTotal}，requirement_edges: ${edgesTotal}）。请确认你当前在下拉框里选中的 history_id 是否与「产生向量库」时的记录一致。`;
      } else if (withEmb <= 0) {
        embedError.value = `已读到 ${total} 条单元，但 unit 与 embedding 对不起来（units_with_embedding: ${withEmb}，requirement_embeddings: ${embeddingsTotal}）。请检查是否有历史ID不一致，或重新对该记录执行「产生向量库」。`;
      } else {
        embedError.value = `向量解析/降维后仍不足以展示（units_with_embedding: ${withEmb}）。可稍后重试或检查嵌入维度/模型配置。`;
      }
    }
  } catch (e) {
    embedError.value = e.message || String(e);
    await alertDialog(`加载失败：${embedError.value}`);
  } finally {
    embedLoading.value = false;
  }
}

async function loadSim() {
  if (!selectedId.value) return;
  simLoading.value = true;
  simError.value = '';
  simNodes.value = [];
  simEdges.value = [];
  try {
    const body = { history_id: Number(selectedId.value), top_k_per_node: 16, max_nodes: 600 };
    if (systemStore.systemId) body.system_id = systemStore.systemId;
    const data = await fetchSimilarityGraph(body);
    simNodes.value = Array.isArray(data.nodes) ? data.nodes : [];
    simEdges.value = Array.isArray(data.edges) ? data.edges : [];
  } catch (e) {
    simError.value = e.message || String(e);
    await alertDialog(`加载失败：${simError.value}`);
  } finally {
    simLoading.value = false;
  }
}

async function runDebug() {
  const q = String(debugQuery.value || '').trim();
  if (!q) return;
  debugLoading.value = true;
  debugError.value = '';
  debugRows.value = [];
  debugNote.value = '';
  try {
    const body = {
      query: q,
      top_k: Number(debugTopK.value) || 12,
      low_score_threshold: Number(debugLowTh.value) || 0.5,
    };
    if (systemStore.systemId) body.system_id = systemStore.systemId;
    if (selectedId.value) body.history_id = Number(selectedId.value);
    const data = await debugVectorQuery(body);
    debugRows.value = Array.isArray(data.hits) ? data.hits : [];
    debugNote.value = data.note === 'network_not_built' ? '当前筛选范围内尚无向量数据，请先建库。' : '';
  } catch (e) {
    debugError.value = e.message || String(e);
    await alertDialog(`调试失败：${debugError.value}`);
  } finally {
    debugLoading.value = false;
  }
}

function parseHistoryIds(text) {
  const s = String(text || '').trim();
  if (!s) return [];
  const parts = s.split(',').map((x) => x.trim()).filter(Boolean);
  const out = [];
  for (const p of parts) {
    const n = Number(p);
    if (Number.isFinite(n) && n > 0 && !out.includes(n)) out.push(n);
  }
  return out.slice(0, 80);
}

async function runRecordSimilarity() {
  const ids = parseHistoryIds(recordIdsText.value);
  if (ids.length < 2) {
    recordSimError.value = '请至少输入 2 个 history_id';
    return;
  }
  recordSimLoading.value = true;
  recordSimError.value = '';
  recordSimPairs.value = [];
  recordSimMeta.value = [];
  try {
    const body = { history_ids: ids, top_pairs: 30 };
    if (systemStore.systemId) body.system_id = systemStore.systemId;
    const data = await fetchRecordSimilarity(body);
    recordSimPairs.value = Array.isArray(data.pairs) ? data.pairs : [];
    recordSimMeta.value = Array.isArray(data.meta) ? data.meta : [];
  } catch (e) {
    recordSimError.value = e.message || String(e);
    await alertDialog(`计算失败：${recordSimError.value}`);
  } finally {
    recordSimLoading.value = false;
  }
}

async function loadStruct() {
  if (!selectedId.value) return;
  structLoading.value = true;
  structError.value = '';
  structUnits.value = [];
  structEdges.value = [];
  structLayout.value = {};
  try {
    const body = { history_id: Number(selectedId.value) };
    if (systemStore.systemId) body.system_id = systemStore.systemId;
    const data = await fetchRequirementNetworkGraph(body.history_id, body.system_id);
    structUnits.value = Array.isArray(data.units) ? data.units : [];
    structEdges.value = Array.isArray(data.edges) ? data.edges : [];
    structLayout.value = buildLayoutMap(structUnits.value);
  } catch (e) {
    structError.value = e.message || String(e);
    await alertDialog(`加载失败：${structError.value}`);
  } finally {
    structLoading.value = false;
  }
}

async function loadAllGraph() {
  allLoading.value = true;
  allError.value = '';
  allUnits.value = [];
  allEdges.value = [];
  allLayout.value = {};
  try {
    // 为“全量网络图”尽可能拉取更多 nodes/edges。
    // 注意：如果你的库很大，加载会明显变慢。
    const body = { show_all: true, limit_units: 50000, limit_edges: 80000 };
    if (systemStore.systemId) body.system_id = systemStore.systemId;
    const data = await fetchRequirementNetworkGraphAll(body);
    allUnits.value = Array.isArray(data.units) ? data.units : [];
    allEdges.value = Array.isArray(data.edges) ? data.edges : [];
    allLayout.value = buildLayoutMap(allUnits.value, allNodeKey);
  } catch (e) {
    allError.value = e.message || String(e);
    await alertDialog(`加载失败：${allError.value}`);
  } finally {
    allLoading.value = false;
  }
}

async function loadCounts() {
  countsLoading.value = true;
  countsError.value = '';
  countsRows.value = [];
  try {
    const body = { limit: 200 };
    if (systemStore.systemId) body.system_id = systemStore.systemId;
    const data = await fetchRequirementNetworkCounts(body);
    countsRows.value = Array.isArray(data.rows) ? data.rows : [];
    if (!countsRows.value.length) {
      countsError.value = '当前 MySQL 库中暂无任何 requirement_units 写入记录（请先对某条需求执行「产生向量库」）。';
    }
  } catch (e) {
    countsError.value = e.message || String(e);
    await alertDialog(`加载失败：${countsError.value}`);
  } finally {
    countsLoading.value = false;
  }
}

watch(
  () => systemStore.systemId,
  () => {
    selectedId.value = '';
    onRecordChange();
    loadHistory();
  },
);

onMounted(() => {
  loadHistory();
});
</script>

<style scoped>
.vec-graph {
  padding: 16px 20px 40px;
  max-width: 1280px;
}

.page-header h1 {
  margin: 0 0 8px;
  font-size: 22px;
  font-weight: 600;
  color: #1e293b;
}

.page-header p {
  margin: 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.65;
}

.toolbar {
  margin-top: 16px;
  padding: 14px 16px;
}

.toolbar-row {
  display: flex;
  gap: 12px;
  align-items: flex-end;
  flex-wrap: wrap;
}

.form-group.grow {
  flex: 1;
  min-width: 220px;
}

.form-group label {
  display: block;
  font-size: 12px;
  color: #64748b;
  margin-bottom: 6px;
}

.input {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 13px;
  box-sizing: border-box;
}

.input-sm {
  width: auto;
  min-width: 100px;
}

.w80 {
  width: 80px;
}

.btn {
  padding: 8px 14px;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  border: 1px solid #e2e8f0;
  background: #fff;
  height: 36px;
}

.btn-primary {
  background: #1677ff;
  border-color: #1677ff;
  color: #fff;
}

.btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
  border-top: 1px solid #f1f5f9;
  padding-top: 12px;
}

.tab {
  padding: 8px 14px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #fff;
  font-size: 13px;
  cursor: pointer;
  color: #475569;
}

.tab.active {
  border-color: #1677ff;
  background: #e6f4ff;
  color: #0958d9;
  font-weight: 600;
}

.tab:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.panel {
  margin-top: 14px;
  padding: 16px;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.panel-head h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #334155;
}

.panel-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.hint {
  font-size: 12px;
  color: #94a3b8;
  margin: 0 0 12px;
  line-height: 1.55;
}

.err {
  color: #dc2626;
  font-size: 13px;
  margin-bottom: 8px;
}

.state-muted {
  color: #94a3b8;
  font-size: 13px;
  padding: 12px 0;
}

.svg-wrap {
  position: relative;
}

.network-svg {
  width: 100%;
  height: auto;
  display: block;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}

.tooltip {
  position: absolute;
  right: 12px;
  bottom: 12px;
  max-width: min(480px, 94%);
  padding: 12px 14px;
  font-size: 12px;
  line-height: 1.5;
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.12);
  z-index: 2;
}

.tt-block { display:flex; flex-direction: column; gap: 6px; }
.tt-row { display:flex; gap: 8px; align-items: flex-start; }
.tt-k { flex: 0 0 auto; font-weight: 700; color: #334155; }
.tt-v { flex: 1 1 auto; color: #475569; white-space: pre-wrap; word-break: break-word; }
.tt-warn { margin-top: 6px; color: #cf1322; font-weight: 700; }

.modal-mask { position: fixed; inset: 0; background: rgba(0,0,0,0.45); display:flex; align-items: center; justify-content: center; padding: 24px; z-index: 70; }
.modal { width: min(980px, 100%); max-height: 84vh; overflow:auto; padding: 14px 16px; }
.detail-section { margin-top: 12px; border-top: 1px solid #f1f5f9; padding-top: 12px; }
.detail-title { font-weight: 800; color: #334155; margin-bottom: 8px; }
.detail-pre {
  margin: 0;
  padding: 10px 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 12px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
}
.detail-kv { display:grid; grid-template-columns: 1fr; gap: 8px; }
.kv { display:flex; gap: 10px; align-items: baseline; }
.kv .k { width: 64px; font-weight: 800; color: #64748b; }
.kv .v { color: #334155; word-break: break-word; }

.meta-line {
  margin-top: 10px;
  font-size: 12px;
  color: #64748b;
}

.debug-form .textarea {
  width: 100%;
  box-sizing: border-box;
  padding: 10px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 13px;
  margin-bottom: 10px;
}

.debug-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.debug-row label {
  font-size: 12px;
  color: #64748b;
}

.table-wrap {
  overflow: auto;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  margin-top: 12px;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.data-table th,
.data-table td {
  border-bottom: 1px solid #f1f5f9;
  padding: 8px 10px;
  text-align: left;
  vertical-align: top;
}

.data-table th {
  background: #f8fafc;
  color: #64748b;
  font-weight: 600;
}

.data-table tr.warn {
  background: #fff7ed;
}

.cell-content {
  max-width: 520px;
  white-space: pre-wrap;
  word-break: break-word;
}

.card {
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
}
</style>
