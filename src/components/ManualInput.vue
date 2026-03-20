<template>
  <div class="manual-input">
    <div class="page-header">
      <h1>手动补录 - 页面元素补充</h1>
      <p>将按钮/列表展示/可填写内容等统一维护，支持 OCR 结果二次编辑与属性标注</p>
    </div>

    <div class="card">
      <h2>选择截图记录</h2>
      <div class="form-group">
        <label>截图</label>
        <select class="input" v-model="selectedId">
          <option value="">请选择</option>
          <option v-for="h in history" :key="h.id" :value="String(h.id)">
            {{ h.created_at }} - {{ h.file_name }}
          </option>
        </select>
      </div>
      <div v-if="selectedRecord" class="grid">
        <div class="img-box">
          <img :src="selectedRecord.file_url" :alt="selectedRecord.file_name" class="preview" />
        </div>
        <div>
          <div class="form-group">
            <label>菜单路径</label>
            <div class="muted">{{ breadcrumb(selectedRecord.menu_structure) || '无' }}</div>
          </div>
          <div class="form-group">
            <label>页面类型</label>
            <select class="input" v-model="manual.page_type">
              <option value="">未知</option>
              <option value="list">list（列表页）</option>
              <option value="form">form（表单页）</option>
              <option value="modal">modal（弹窗表单）</option>
              <option value="detail">detail（详情页）</option>
            </select>
          </div>
          <div class="actions">
            <button class="btn btn-default" @click="loadFromRecord" :disabled="!selectedId">加载已补录</button>
            <button class="btn btn-default" @click="generateSuggestions" :disabled="!selectedId || isSuggesting">OCR建议被测项</button>
            <button class="btn btn-primary" @click="saveManual()" :disabled="!selectedId || isSaving">保存页面元素</button>
          </div>
          <div style="margin-top:10px;">
            <label style="display:flex; align-items:center; gap:8px; color:#666; font-size:12px;">
              <input type="checkbox" v-model="useNetwork" />
              优先使用需求网络库（向量检索）
            </label>
          </div>
          <div v-if="suggestHint" style="margin-top:10px; color:#1677ff;">{{ suggestHint }}</div>
          <div v-if="saveHint" style="margin-top:10px; color:#52c41a;">{{ saveHint }}</div>
        </div>
      </div>
    </div>

    <div v-if="selectedRecord" class="card">
      <h2>OCR 识别参考</h2>
      <div class="subtle-block" v-if="manual.ocr_raw_text || ((manual.ocr_refs.button_candidates || []).length + (manual.ocr_refs.field_candidates || []).length)">
        <div class="tag-row">
          <span class="tag tip">按钮候选</span>
          <span v-for="(b, i) in manual.ocr_refs.button_candidates" :key="'btn-' + i" class="tag">{{ b }}</span>
        </div>
        <div class="tag-row" style="margin-top:8px;">
          <span class="tag tip">字段候选</span>
          <span v-for="(f, i) in manual.ocr_refs.field_candidates" :key="'fld-' + i" class="tag">{{ f }}</span>
        </div>
        <div class="ocr-raw-box" v-if="manual.ocr_raw_text">{{ manual.ocr_raw_text }}</div>
      </div>
    </div>

    <div v-if="selectedRecord" class="card">
      <h2>页面元素列表（统一编辑）</h2>
      <div class="form-group">
        <label>新增元素</label>
        <div class="add-row">
          <input class="input" v-model="newElement.name" placeholder="元素名称（如：查询、区域名称、报名进度统计）" style="min-width: 220px;" />
          <select class="input" v-model="newElement.element_type" style="max-width: 150px;">
            <option value="button">按钮</option>
            <option value="field">可填写内容</option>
            <option value="list_column">列表展示</option>
            <option value="filter">筛选条件</option>
            <option value="text">文本说明</option>
            <option value="status">状态标识</option>
            <option value="tab">页签</option>
            <option value="link">链接</option>
            <option value="card">卡片/统计项</option>
            <option value="other">其他</option>
          </select>
          <input class="input" v-model="newElement.ui_pattern" placeholder="UI样式（如：下拉框/输入框/标签）" style="max-width: 220px;" />
          <input class="input" v-model="newElement.validation" placeholder="校验/约束（可选）" style="min-width: 240px;" />
          <button class="btn btn-default" @click="addElement">添加</button>
        </div>
      </div>

      <table class="table">
        <thead>
          <tr>
            <th>名称</th>
            <th>类型</th>
            <th>UI样式</th>
            <th>规则/动作</th>
            <th>属性</th>
            <th>来源</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(e, idx) in manual.page_elements" :key="idx">
            <td><input class="input" v-model="e.name" /></td>
            <td>
              <select class="input" v-model="e.element_type">
                <option value="button">按钮</option>
                <option value="field">可填写内容</option>
                <option value="list_column">列表展示</option>
                <option value="filter">筛选条件</option>
                <option value="text">文本说明</option>
                <option value="status">状态标识</option>
                <option value="tab">页签</option>
                <option value="link">链接</option>
                <option value="card">卡片/统计项</option>
                <option value="other">其他</option>
              </select>
            </td>
            <td><input class="input" v-model="e.ui_pattern" placeholder="下拉框/输入框/按钮等" /></td>
            <td>
              <div style="display:flex; gap:6px; flex-wrap:wrap;">
                <select class="input" v-model="e.action" style="max-width: 120px;">
                  <option value="">动作(可空)</option>
                  <option value="query">query</option>
                  <option value="create">create</option>
                  <option value="edit">edit</option>
                  <option value="delete">delete</option>
                  <option value="export">export</option>
                  <option value="open">open</option>
                </select>
                <input class="input" v-model="e.validation" placeholder="校验规则" style="min-width: 160px;" />
              </div>
            </td>
            <td>
              <div style="display:flex; gap:8px; flex-wrap:wrap;">
                <label><input type="checkbox" v-model="e.required" /> 必填</label>
                <label><input type="checkbox" v-model="e.queryable" /> 可查询</label>
                <label><input type="checkbox" v-model="e.opens_modal" /> 弹窗</label>
                <label><input type="checkbox" v-model="e.requires_confirm" /> 二次确认</label>
              </div>
            </td>
            <td>
              <input class="input" v-model="e.source" placeholder="来源(ocr/manual/llm)" style="max-width: 150px;" />
              <input class="input" v-model="e.source_text" placeholder="命中词" style="max-width: 180px; margin-top: 6px;" />
            </td>
            <td>
              <button class="btn btn-danger" @click="removeElement(idx)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>

      <div class="form-group" style="margin-top: 12px;">
        <label>文字需求补充</label>
        <textarea v-model="manual.text_requirements" placeholder="业务说明、特殊规则、边界约束、验收口径等" style="min-height: 120px;" />
      </div>
      <div class="form-group">
        <label>控制/流程备注</label>
        <textarea v-model="manual.control_logic" placeholder="补充流程逻辑、页面联动、异常处理要求等" style="min-height: 90px;" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { useUiDialog } from '../composables/useUiDialog';

const props = defineProps({
  type: {
    type: String,
    required: true
  }
});

const tabTitle = computed(() => '页面元素补充');

const history = ref([]);
const selectedId = ref('');
const isSaving = ref(false);
const saveHint = ref('');
const isSuggesting = ref(false);
const suggestHint = ref('');
const useNetwork = ref(true);

const manual = ref({
  page_type: '',
  page_elements: [],
  buttons: [],
  fields: [],
  text_requirements: '',
  ocr_raw_text: '',
  ocr_refs: { button_candidates: [], field_candidates: [] },
  control_logic: '',
});

const newElement = ref({ name: '', element_type: 'button', ui_pattern: '按钮', validation: '' });
const { alertDialog } = useUiDialog();

const selectedRecord = computed(() => {
  const id = Number(selectedId.value);
  return history.value.find((h) => h.id === id) || null;
});

const breadcrumb = (menuStructure) => {
  return (Array.isArray(menuStructure) ? menuStructure : []).map((x) => x.name).filter(Boolean).join(' / ');
};

const fetchHistory = async () => {
  const resp = await fetch('/api/history');
  if (!resp.ok) throw new Error('获取截图记录失败');
  const data = await resp.json();
  history.value = (Array.isArray(data) ? data : []).map((r) => ({
    ...r,
    created_at: r.created_at || r.operation_time || '',
    file_url: r.file_url || (r.file_name ? `/uploads/${r.file_name}` : '')
  }));
};

const loadFromRecord = () => {
  if (!selectedRecord.value) return;
  const m = selectedRecord.value.manual || {};
  manual.value = {
    page_type: m.page_type || '',
    page_elements: Array.isArray(m.page_elements) ? m.page_elements : [],
    buttons: Array.isArray(m.buttons) ? m.buttons : [],
    fields: Array.isArray(m.fields) ? m.fields : [],
    text_requirements: m.text_requirements || '',
    ocr_raw_text: m.ocr_raw_text || '',
    ocr_refs: (m.ocr_refs && typeof m.ocr_refs === 'object') ? m.ocr_refs : { button_candidates: [], field_candidates: [] },
    control_logic: m.control_logic || ''
  };
};

const generateSuggestions = async () => {
  if (!selectedId.value) return;
  isSuggesting.value = true;
  suggestHint.value = '';
  try {
    const resp = await fetch(`/api/ocr/manual/${selectedId.value}`);
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(data.error || 'OCR建议生成失败');
    const md = data.manual_draft || {};
    if (!Array.isArray(manual.value.page_elements)) manual.value.page_elements = [];
    const incoming = Array.isArray(md.page_elements) ? md.page_elements : [];
    const keys = new Set(manual.value.page_elements.map((x) => `${x.element_type || 'other'}::${x.name || ''}`));
    let added = 0;
    for (const it of incoming) {
      const key = `${it.element_type || 'other'}::${it.name || ''}`;
      if (!it?.name || keys.has(key)) continue;
      keys.add(key);
      manual.value.page_elements.push(it);
      added += 1;
    }
    manual.value.ocr_raw_text = md.ocr_raw_text || '';
    manual.value.ocr_refs = md.ocr_refs || { button_candidates: [], field_candidates: [] };
    if (!manual.value.page_type) manual.value.page_type = md.page_type || '';

    let addedNetwork = 0;
    if (useNetwork.value) {
      const query =
        (manual.value.text_requirements || '').trim() ||
        (manual.value.control_logic || '').trim() ||
        (manual.value.ocr_raw_text || '').trim() ||
        (selectedRecord.value ? breadcrumb(selectedRecord.value.menu_structure) : '');

      try {
        const resp2 = await fetch('/api/requirement-network/search', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: query.slice(0, 1500), top_k: 25, unit_type: 'element' }),
        });
        const data2 = await resp2.json().catch(() => ({}));
        const results2 = Array.isArray(data2.results) ? data2.results : [];
        if (Array.isArray(results2) && results2.length) {
          for (const r of results2) {
            const md = r && r.metadata && typeof r.metadata === 'object' ? r.metadata : {};
            const et = md.element_type || 'other';
            const nm = md.name || '';
            const key = `${et}::${nm}`;
            if (!nm || keys.has(key)) continue;
            keys.add(key);
            manual.value.page_elements.push({
              name: nm,
              element_type: et,
              ui_pattern: md.ui_pattern || '',
              validation: md.validation || '',
              min_len: md.min_len || '',
              max_len: md.max_len || '',
              options: Array.isArray(md.options) ? md.options : [],
              action: md.action || '',
              required: !!md.required,
              queryable: !!md.queryable,
              opens_modal: !!md.opens_modal,
              requires_confirm: !!md.requires_confirm,
              source: md.source || 'network',
              source_text: md.source_text || '',
              raw_text: '',
              notes: '',
            });
            addedNetwork += 1;
          }
        }
      } catch (e) {
        // ignore: 网络库不存在/未构建时不阻断 OCR 流程
      }
    }

    suggestHint.value = `已导入 OCR 建议元素 ${added} 个${useNetwork.value ? `，并追加需求网络库元素 ${addedNetwork} 个` : ''}，可继续编辑后保存`;
  } catch (e) {
    console.error(e);
    await alertDialog('生成建议失败');
  } finally {
    isSuggesting.value = false;
  }
};

const saveManual = async (silent = false) => {
  if (!selectedId.value) return;
  isSaving.value = true;
  saveHint.value = '';
  try {
    const resp = await fetch(`/api/history/${selectedId.value}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ manual: manual.value })
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.error || '保存失败');
    }
    await fetchHistory();
    window.dispatchEvent(new Event('history-updated'));
    saveHint.value = silent ? '已自动保存补录' : '已保存（用例生成会基于该补录动态生成）';
  } catch (e) {
    console.error(e);
    if (!silent) await alertDialog(`保存失败: ${e.message}`);
  } finally {
    isSaving.value = false;
  }
};

const addElement = () => {
  const name = (newElement.value.name || '').trim();
  if (!name) return;
  if (!Array.isArray(manual.value.page_elements)) manual.value.page_elements = [];
  manual.value.page_elements.push({
    name,
    element_type: newElement.value.element_type || 'other',
    ui_pattern: newElement.value.ui_pattern || '',
    required: false,
    queryable: false,
    validation: newElement.value.validation || '',
    min_len: '',
    max_len: '',
    options: [],
    action: '',
    opens_modal: false,
    requires_confirm: false,
    source: 'manual',
    source_text: '',
    raw_text: '',
    notes: '',
  });
  newElement.value = { name: '', element_type: 'button', ui_pattern: '按钮', validation: '' };
};

const removeElement = (idx) => {
  manual.value.page_elements.splice(idx, 1);
};

watch(selectedId, () => {
  saveHint.value = '';
  loadFromRecord();
});

onMounted(async () => {
  try {
    await fetchHistory();
  } catch (e) {
    console.error(e);
  }
});

window.addEventListener('history-updated', () => {
  fetchHistory().catch(() => {});
});
</script>

<style scoped>
.manual-input {
  min-height: 100vh;
}
.manual-toolbar {
  display:flex;
  align-items:center;
  gap:12px;
  flex-wrap:wrap;
}
.grid {
  display:grid;
  grid-template-columns: 1fr 360px;
  gap:16px;
  align-items:start;
}
.img-box {
  border:1px solid #eee;
  border-radius:8px;
  background:#fafafa;
  padding:12px;
  text-align:center;
}
.preview {
  max-width:100%;
  max-height: 360px;
  object-fit: contain;
  border-radius: 6px;
}
.actions {
  display:flex;
  gap:8px;
  flex-wrap:wrap;
}
.add-row {
  display:flex;
  gap:8px;
  flex-wrap:wrap;
}
.subtle-block {
  border: 1px solid #e6f4ff;
  background: #f7fbff;
  border-radius: 8px;
  padding: 10px;
  margin-bottom: 12px;
}
.subtle-title {
  font-size: 13px;
  color: #1d39c4;
  margin-bottom: 8px;
  font-weight: 600;
}
.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}
.tag.tip {
  background: #e6f4ff;
  color: #0958d9;
  border: 1px solid #91caff;
}
.muted {
  color: #999;
  font-size: 12px;
}
.ocr-raw-box {
  margin-top: 10px;
  padding: 8px;
  border: 1px dashed #d9d9d9;
  border-radius: 6px;
  background: #fff;
  max-height: 140px;
  overflow: auto;
  white-space: pre-wrap;
  font-size: 12px;
  color: #555;
}
</style>
