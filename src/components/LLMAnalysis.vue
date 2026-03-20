<template>
  <div class="llm-analysis">
    <div class="page-header">
      <h1>LLM 分析系统交互</h1>
      <p>基于 OCR 识别结果，预填“手动补录”字段/按钮并联动用例生成</p>
    </div>

    <div class="card">
      <h2>选择截图</h2>

      <div class="form-group">
        <label>截图记录</label>
        <select class="input" v-model="selectedId">
          <option value="">请选择</option>
          <option v-for="r in records" :key="r.id" :value="String(r.id)">
            {{ r.created_at }} - {{ r.file_name }}
          </option>
        </select>
      </div>

      <div v-if="selectedRecord" class="card" style="margin-top: 16px;">
        <h3>预览</h3>
        <div style="display:grid; grid-template-columns: 1fr 360px; gap: 16px; align-items:start;">
          <div style="border: 1px solid #eee; border-radius: 8px; background:#fafafa; padding: 12px; text-align:center;">
            <img :src="selectedRecord.file_url" :alt="selectedRecord.file_name" style="max-width:100%; max-height: 420px; object-fit:contain; border-radius: 6px;" />
          </div>
          <div>
            <div class="form-group">
              <label>文件名</label>
              <div>{{ selectedRecord.file_name }}</div>
            </div>
            <div class="form-group">
              <label>菜单路径</label>
              <div style="color:#666;">
                {{ breadcrumb(selectedRecord.menu_structure) || '无' }}
              </div>
            </div>
            <div style="display:flex; gap: 8px;">
              <button class="btn btn-default" @click="fetchHistory" :disabled="isGenerating || isSavingManual">刷新列表</button>
              <button class="btn btn-primary" @click="generateAnalysis" :disabled="isGenerating || isSavingManual">
                {{ isGenerating ? '生成中...' : '生成分析' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- OCR 分析弹窗：预览截图 + 可填写被测字段（保存将写入 history.manual） -->
    <div class="modal-mask" v-if="manualModalOpen" @click.self="manualModalOpen=false">
      <div class="modal card">
        <div style="display:flex; justify-content: space-between; align-items:center; gap:12px;">
          <div style="font-weight:700;">OCR 建议的被测项（可编辑）</div>
          <button class="btn btn-default" @click="manualModalOpen=false" :disabled="isGenerating || isSavingManual">关闭</button>
        </div>

        <div style="display:grid; grid-template-columns: 1fr 420px; gap: 16px; margin-top: 12px;">
          <div style="border:1px solid #eee; border-radius:8px; background:#fafafa; padding:10px;">
            <div style="color:#666; font-size:13px; margin-bottom:8px;">截图预览</div>
            <img
              v-if="selectedRecord"
              :src="selectedRecord.file_url"
              :alt="selectedRecord.file_name"
              style="width:100%; max-height: 64vh; object-fit: contain; border-radius:6px;"
            />
          </div>

          <div>
            <div class="form-group">
              <label>页面类型</label>
              <select class="input" v-model="manualDraft.page_type">
                <option value="">未知</option>
                <option value="list">list</option>
                <option value="form">form</option>
                <option value="modal">modal</option>
                <option value="detail">detail</option>
              </select>
            </div>

            <div class="form-group">
              <label>可填写字段（用于手动补录/后续用例生成）</label>
              <div v-if="manualDraft.fields && manualDraft.fields.length" style="display:flex; flex-direction:column; gap:10px;">
                <div
                  v-for="(f, idx) in manualDraft.fields"
                  :key="idx"
                  style="border:1px solid #eee; border-radius:8px; padding:10px; background:#fafafa;"
                >
                  <div style="display:flex; gap:8px; align-items:center;">
                    <div style="flex:1;">
                      <input class="input" v-model="f.name" placeholder="字段名，如：关键字段A" />
                    </div>
                    <select class="input" v-model="f.type" style="max-width:160px;">
                      <option value="text">text</option>
                      <option value="number">number</option>
                      <option value="phone">phone</option>
                      <option value="email">email</option>
                      <option value="date">date</option>
                      <option value="select">select</option>
                    </select>
                  </div>

                  <div style="display:flex; gap:12px; align-items:center; margin-top:8px;">
                    <label style="display:flex; align-items:center; gap:6px;">
                      <input type="checkbox" v-model="f.required" />
                      必填
                    </label>
                    <button class="btn btn-danger" @click="removeField(idx)" :disabled="manualDraft.fields.length<=1">删除字段</button>
                  </div>

                  <div
                    v-if="f.hint || fieldHintMap[f.name]"
                    style="margin-top:8px; color:#666; font-size:12px; white-space:pre-wrap;"
                  >
                    <div style="font-weight:600; margin-bottom:6px;">期望被测项方向</div>
                    {{ f.hint || fieldHintMap[f.name] }}
                  </div>
                </div>
              </div>
              <div v-else style="color:#999;">OCR 暂未识别到字段，将保留默认字段。</div>
            </div>

            <div class="form-group" style="margin-top: 16px;">
              <label>操作按钮（可新增）</label>

              <div style="display:flex; gap:8px; flex-wrap:wrap; margin-top:10px;">
                <input class="input" v-model="newButton.name" placeholder="按钮名称（如：查询/新增/编辑/删除）" style="max-width: 280px;" />
                <select class="input" v-model="newButton.action" style="max-width: 180px;">
                  <option value="">动作(可选)</option>
                  <option value="query">query</option>
                  <option value="create">create</option>
                  <option value="edit">edit</option>
                  <option value="delete">delete</option>
                  <option value="export">export</option>
                  <option value="open">open</option>
                </select>
                <label style="display:flex; align-items:center; gap:6px;">
                  <input type="checkbox" v-model="newButton.opens_modal" /> 弹窗
                </label>
                <label style="display:flex; align-items:center; gap:6px;">
                  <input type="checkbox" v-model="newButton.requires_confirm" /> 二次确认
                </label>
                <button class="btn btn-default" @click="addButtonToDraft" :disabled="isGenerating || isSavingManual">添加按钮</button>
              </div>

              <div v-if="manualDraft.buttons && manualDraft.buttons.length" style="margin-top: 12px;">
                <div v-for="(b, idx) in manualDraft.buttons" :key="idx" style="border:1px solid #eee; border-radius:8px; padding:10px; background:#fafafa; margin-top:10px;">
                  <div style="display:flex; gap:8px; flex-wrap:wrap; align-items:center;">
                    <input class="input" v-model="b.name" style="flex: 1; min-width: 180px;" />
                    <select class="input" v-model="b.action" style="max-width: 180px;">
                      <option value="">(空)</option>
                      <option value="query">query</option>
                      <option value="create">create</option>
                      <option value="edit">edit</option>
                      <option value="delete">delete</option>
                      <option value="export">export</option>
                      <option value="open">open</option>
                    </select>
                    <label style="display:flex; align-items:center; gap:6px;">
                      <input type="checkbox" v-model="b.opens_modal" /> 弹窗
                    </label>
                    <label style="display:flex; align-items:center; gap:6px;">
                      <input type="checkbox" v-model="b.requires_confirm" /> 二次确认
                    </label>
                    <button
                      class="btn btn-danger"
                      @click="removeButtonFromDraft(idx)"
                      :disabled="b.name === '取消' || b.name === '保存'"
                      title="取消/保存不可删除（用于联动所有页面）"
                    >
                      删除
                    </button>
                  </div>
                  <div v-if="b.source || b.source_text" style="margin-top:6px; font-size:12px; color:#666;">
                    来源：{{ b.source || 'manual' }}<span v-if="b.source_text">，命中：{{ b.source_text }}</span>
                  </div>
                </div>
              </div>
            </div>

            <div class="form-group" style="margin-top: 16px;">
              <label>OCR 参考项（用于补录）</label>
              <div style="border:1px solid #eee; border-radius:8px; padding:10px; background:#fafafa;">
                <div style="font-size:12px; color:#666;">参考按钮：</div>
                <div style="display:flex; gap:6px; flex-wrap:wrap; margin-top:6px;">
                  <span
                    v-for="(b, i) in (ocrRefs.button_candidates || [])"
                    :key="'obr-' + i"
                    class="tag tag-info"
                  >{{ b }}</span>
                  <span v-if="!(ocrRefs.button_candidates || []).length" style="color:#999;">无</span>
                </div>
                <div style="font-size:12px; color:#666; margin-top:10px;">参考字段：</div>
                <div style="display:flex; gap:6px; flex-wrap:wrap; margin-top:6px;">
                  <span
                    v-for="(f, i) in (ocrRefs.field_candidates || [])"
                    :key="'ofr-' + i"
                    class="tag"
                  >{{ f }}</span>
                  <span v-if="!(ocrRefs.field_candidates || []).length" style="color:#999;">无</span>
                </div>
                <div style="margin-top:10px; font-size:12px; color:#666;">OCR 原文（摘要）：</div>
                <div style="white-space:pre-wrap; margin-top:6px; border:1px dashed #ddd; border-radius:6px; background:#fff; padding:8px; max-height:120px; overflow:auto;">
                  {{ ocrPreviewText || '无' }}
                </div>
              </div>
            </div>

            <div class="form-group" style="margin-top: 16px;">
              <label>页面元素（全量可编辑）</label>
              <div style="display:flex; gap:8px; flex-wrap:wrap; margin-top:8px;">
                <input class="input" v-model="newElement.name" placeholder="元素名称" style="min-width:180px;" />
                <select class="input" v-model="newElement.element_type" style="max-width:140px;">
                  <option value="button">按钮</option>
                  <option value="field">可填写内容</option>
                  <option value="list_column">列表展示</option>
                  <option value="filter">筛选条件</option>
                  <option value="text">文本说明</option>
                  <option value="status">状态</option>
                  <option value="tab">页签</option>
                  <option value="link">链接</option>
                  <option value="card">卡片</option>
                  <option value="other">其他</option>
                </select>
                <input class="input" v-model="newElement.ui_pattern" placeholder="UI样式" style="max-width:180px;" />
                <input class="input" v-model="newElement.validation" placeholder="校验规则(可选)" style="min-width:180px;" />
                <button class="btn btn-default" @click="addElementToDraft">添加元素</button>
              </div>
              <div v-if="manualDraft.page_elements && manualDraft.page_elements.length" style="margin-top:10px;">
                <div v-for="(e, i) in manualDraft.page_elements" :key="'pe-'+i" style="border:1px solid #eee; border-radius:8px; padding:10px; background:#fff; margin-top:8px;">
                  <div style="display:flex; gap:8px; flex-wrap:wrap; align-items:center;">
                    <input class="input" v-model="e.name" style="min-width:160px;" />
                    <select class="input" v-model="e.element_type" style="max-width:140px;">
                      <option value="button">按钮</option>
                      <option value="field">可填写内容</option>
                      <option value="list_column">列表展示</option>
                      <option value="filter">筛选条件</option>
                      <option value="text">文本说明</option>
                      <option value="status">状态</option>
                      <option value="tab">页签</option>
                      <option value="link">链接</option>
                      <option value="card">卡片</option>
                      <option value="other">其他</option>
                    </select>
                    <input class="input" v-model="e.ui_pattern" placeholder="UI样式" style="max-width:160px;" />
                    <input class="input" v-model="e.validation" placeholder="规则" style="min-width:150px;" />
                    <input class="input" v-model="e.action" placeholder="action" style="max-width:120px;" />
                    <label><input type="checkbox" v-model="e.required" /> 必填</label>
                    <label><input type="checkbox" v-model="e.queryable" /> 可查询</label>
                    <label><input type="checkbox" v-model="e.opens_modal" /> 弹窗</label>
                    <label><input type="checkbox" v-model="e.requires_confirm" /> 二次确认</label>
                    <button class="btn btn-danger" @click="removeElementFromDraft(i)">删除</button>
                  </div>
                </div>
              </div>
            </div>

            <div style="margin-top: 12px; color:#666; font-size:13px;">
              操作按钮联动：弹窗内包含 `取消` 与 `保存`，保存后会写入 `history.manual` 并触发所有页面刷新。
            </div>

            <div style="display:flex; gap:12px; margin-top: 16px;">
              <button class="btn btn-default" @click="manualModalOpen=false" :disabled="isGenerating || isSavingManual">取消</button>
              <button class="btn btn-primary" @click="saveManualDraft" :disabled="isGenerating || isSavingManual || !selectedId">
                {{ isSavingManual ? '保存中...' : '保存' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { useUiDialog } from '../composables/useUiDialog';

const records = ref([]);
const selectedId = ref('');
const analysisText = ref('');
const candidateItems = ref([]);
const isGenerating = ref(false);
const isSaving = ref(false);
const saveHint = ref('');

// OCR->manual 弹窗状态（保存写入 history.manual）
const manualModalOpen = ref(false);
const manualDraft = ref({ page_type: '', buttons: [], fields: [], control_logic: '' });
const fieldHints = ref([]);
const isSavingManual = ref(false);
const newButton = ref({ name: '', action: '', opens_modal: false, requires_confirm: false });
const newElement = ref({ name: '', element_type: 'button', ui_pattern: '按钮', validation: '' });
const ocrPreviewText = ref('');
const ocrRefs = ref({ button_candidates: [], field_candidates: [] });
const { alertDialog } = useUiDialog();

const fieldHintMap = computed(() => {
  const m = {};
  if (!Array.isArray(fieldHints.value)) return m;
  for (const h of fieldHints.value) {
    if (h && typeof h.name === 'string') m[h.name] = h.direction || '';
  }
  return m;
});

const selectedRecord = computed(() => {
  const id = Number(selectedId.value);
  return records.value.find((r) => r.id === id) || null;
});

const fetchHistory = async () => {
  const resp = await fetch('/api/history');
  if (!resp.ok) throw new Error('获取截图记录失败');
  const data = await resp.json();
  records.value = (Array.isArray(data) ? data : []).map((r) => ({
    ...r,
    created_at: r.created_at || r.operation_time || '',
    file_url: r.file_url || (r.file_name ? `/uploads/${r.file_name}` : ''),
    analysis: r.analysis || ''
  }));
};

function breadcrumb(menuStructure) {
  return (Array.isArray(menuStructure) ? menuStructure : []).map((x) => x.name).filter(Boolean).join(' / ');
}

function extractCandidates(text) {
  const src = String(text || '');
  const lines = src.split(/\r?\n/);
  const candidates = [];

  // 1) 优先解析后端 OCR 修正区，保证“被测项”来自 AI 输出
  const ocrMarker = 'OCR识别修正后的被测项建议';
  const markerIdx = lines.findIndex((l) => (l || '').includes(ocrMarker));
  if (markerIdx !== -1) {
    let i = markerIdx + 1;
    while (i < lines.length) {
      const line = (lines[i] || '').trim();
      if (line.startsWith('- ')) {
        const title = line.slice(2).trim();
        i += 1;
        const dirLines = [];
        while (i < lines.length) {
          const l2 = (lines[i] || '').trim();
          if (l2.startsWith('- ')) break;
          if (l2) dirLines.push(l2);
          i += 1;
        }
        if (title) candidates.push({ title, direction: dirLines.join('\n') });
      } else {
        i += 1;
      }
    }
    if (candidates.length) return candidates;
  }

  const joinSectionBullets = (startKey, endKey) => {
    const sIdx = lines.findIndex((l) => l.includes(startKey));
    if (sIdx === -1) return [];
    const eIdx = endKey ? lines.findIndex((l, idx) => idx > sIdx && l.includes(endKey)) : -1;
    const end = eIdx === -1 ? lines.length : eIdx;
    const out = [];
    for (let i = sIdx + 1; i < end; i++) {
      const l = lines[i] || '';
      if (l.trim().startsWith('-')) out.push(l.trim().slice(1).trim());
    }
    return out;
  };

  const featureBullets = joinSectionBullets('可能涉及的功能点', '测试用例方向');
  const directionBullets = joinSectionBullets('测试用例方向', null);

  const push = (title, direction) => {
    if (!candidates.find((x) => x.title === title)) candidates.push({ title, direction });
  };

  for (const b of featureBullets) {
    if (b.includes('页面展示')) {
      push('页面可用性', ['进入页面后验证关键区域可见', '检查无空白/错位/明显报错', '按钮可点击、loading/禁用态可正常切换'].join('\\n'));
    } else if (b.includes('查询') || b.includes('筛选') || b.includes('搜索')) {
      push('查询/筛选', ['验证：不填条件时返回默认/全量结果', '填写关键字段后命中正确', '重置/清空后结果回到初始状态', '异常条件（空数据/接口失败）提示清晰'].join('\\n'));
    } else if (b.includes('新增') || b.includes('编辑') || b.includes('修改') || b.includes('表单')) {
      push('新增/编辑（校验与提交）', ['打开弹窗/表单后校验必填与长度/格式', '提交成功提示与列表刷新正确', '提交失败/异常时提示文案明确', '二次快速点击防抖/禁用态正确'].join('\\n'));
    } else if (b.includes('删除')) {
      push('删除（确认与回滚）', ['二次确认取消：不删除且列表不变化', '二次确认确认：删除成功提示与列表刷新', '接口失败时错误提示清晰'].join('\\n'));
    } else if (b.includes('权限') || b.includes('异常') || b.includes('失败')) {
      push('权限与异常处理', ['无权限/无数据/接口异常时不白屏', '错误提示可读、可定位（如按钮提示/空状态）', '可恢复操作（重试/返回列表）'].join('\\n'));
    }
  }

  // 把“测试用例方向”也作为兜底候选展示
  if (directionBullets.length) {
    push('通用测试方向', directionBullets.join('\\n').replace(/^-\\s*/, ''));
  }

  // 基于 OCR 关键词补一点字段校验方向（若 OCR 里识别到）
  const ocrKeywords = ['邮箱', '备注', '用户名', '金额', '数量', '字段', '输入', '校验'];
  const hit = ocrKeywords.filter((k) => src.includes(k));
  if (hit.length) {
    const sample = hit.slice(0, 4).join('、');
    push('字段校验（来自OCR关键词）', [
      `识别到：${sample}`,
      '校验必填/长度/格式（按当前字段规则）',
      '构造不合法输入触发提示，确保禁止提交',
      '边界值（最小/最大长度）行为符合预期',
    ].join('\\n'));
  }

  // 基于 OCR 交互关键词补“被测项”类型
  const ocrActionChecks = [
    {
      kw: '查询',
      title: '查询/筛选',
      direction: ['验证：不填条件时返回默认/全量结果', '填写关键字段后命中正确', '重置/清空后结果回到初始状态', '异常条件（空数据/接口失败）提示清晰'].join('\\n'),
    },
    {
      kw: '筛选',
      title: '查询/筛选',
      direction: ['验证：筛选条件组合正确生效', '筛选后分页/排序（如有）保持正确', '异常筛选时提示清晰'].join('\\n'),
    },
    {
      kw: '新增',
      title: '新增/编辑（校验与提交）',
      direction: ['打开弹窗/表单后校验必填与长度/格式', '提交成功提示与列表刷新正确', '提交失败/异常时提示文案明确', '二次快速点击防抖/禁用态正确'].join('\\n'),
    },
    {
      kw: '编辑',
      title: '新增/编辑（校验与提交）',
      direction: ['进入编辑后展示当前数据且可修改', '修改提交后持久化成功与列表/详情联动正确', '编辑失败/接口异常时错误提示清晰'].join('\\n'),
    },
    {
      kw: '修改',
      title: '新增/编辑（校验与提交）',
      direction: ['进入修改流程后校验必填与格式', '提交后状态/数据回显正确', '边界值（长度/数值范围）提示符合预期'].join('\\n'),
    },
    {
      kw: '删除',
      title: '删除（确认与回滚）',
      direction: ['二次确认取消：不删除且列表不变化', '二次确认确认：删除成功提示与列表刷新', '接口失败时错误提示清晰'].join('\\n'),
    },
    {
      kw: '保存',
      title: '新增/编辑（校验与提交）',
      direction: ['点击保存触发校验与提交', '校验失败时禁止提交并展示错误信息', '保存成功后提示与回到列表/详情的行为符合预期'].join('\\n'),
    },
    {
      kw: '提交',
      title: '新增/编辑（校验与提交）',
      direction: ['提交按钮触发校验、loading 与禁用态', '提交成功/失败提示文案正确', '接口慢/失败场景下页面不会卡死或丢失数据'].join('\\n'),
    },
  ];

  for (const c of ocrActionChecks) {
    if (src.includes(c.kw)) push(c.title, c.direction);
  }

  return candidates;
}

const loadSavedAnalysis = () => {
  if (!selectedRecord.value) return;
  analysisText.value = selectedRecord.value.analysis || '';
  candidateItems.value = extractCandidates(analysisText.value);
};

const generateAnalysis = async () => {
  if (!selectedId.value) return;
  isGenerating.value = true;
  try {
    // 1) 生成并保存本次分析（覆盖为最新一次）
    const aResp = await fetch(`/api/analyze/${selectedId.value}`);
    const aData = await aResp.json().catch(() => ({}));
    if (!aResp.ok) throw new Error(aData.error || '分析生成失败');
    const latestAnalysis = String(aData.analysis || '');
    analysisText.value = latestAnalysis;
    candidateItems.value = extractCandidates(latestAnalysis);
    if (latestAnalysis) {
      const saveResp = await fetch(`/api/history/${selectedId.value}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ analysis: latestAnalysis }),
      });
      if (!saveResp.ok) {
        const err = await saveResp.json().catch(() => ({}));
        throw new Error(err.error || '分析保存失败');
      }
    }

    // 2) 生成 OCR 建议补录弹窗
    const resp = await fetch(`/api/ocr/manual/${selectedId.value}`);
    if (!resp.ok) throw new Error('生成失败');
    const data = await resp.json();
    manualDraft.value = data.manual_draft || { page_type: '', buttons: [], fields: [], control_logic: '' };
    if (!Array.isArray(manualDraft.value.buttons)) manualDraft.value.buttons = [];
    if (!Array.isArray(manualDraft.value.fields)) manualDraft.value.fields = [];
    if (!Array.isArray(manualDraft.value.page_elements)) manualDraft.value.page_elements = [];
    if (typeof manualDraft.value.control_logic !== 'string') manualDraft.value.control_logic = '';
    ocrPreviewText.value = data.ocr_preview || manualDraft.value.ocr_raw_text || '';
    ocrRefs.value = (manualDraft.value && typeof manualDraft.value.ocr_refs === 'object' && manualDraft.value.ocr_refs)
      ? manualDraft.value.ocr_refs
      : { button_candidates: [], field_candidates: [] };

    fieldHints.value = Array.isArray(data.field_hints) ? data.field_hints : [];
    await fetchHistory();
    window.dispatchEvent(new Event('history-updated'));
    manualModalOpen.value = true;
  } catch (e) {
    console.error(e);
    await alertDialog('生成分析失败，请稍后重试');
  } finally {
    isGenerating.value = false;
  }
};

const removeField = (idx) => {
  if (!manualDraft.value?.fields || manualDraft.value.fields.length <= 1) return;
  manualDraft.value.fields.splice(idx, 1);
};

const addButtonToDraft = () => {
  const name = (newButton.value?.name || '').trim();
  if (!name) return;
  if (!Array.isArray(manualDraft.value.buttons)) manualDraft.value.buttons = [];
  if (manualDraft.value.buttons.find((b) => b?.name === name)) return;
  manualDraft.value.buttons.push({
    name,
    action: newButton.value?.action || '',
    opens_modal: !!newButton.value?.opens_modal,
    requires_confirm: !!newButton.value?.requires_confirm,
    source: 'manual',
    source_text: '',
  });
  newButton.value = { name: '', action: '', opens_modal: false, requires_confirm: false };
};

const addElementToDraft = () => {
  const name = (newElement.value?.name || '').trim();
  if (!name) return;
  if (!Array.isArray(manualDraft.value.page_elements)) manualDraft.value.page_elements = [];
  const key = `${newElement.value.element_type || 'other'}::${name}`;
  const exists = manualDraft.value.page_elements.find((x) => `${x?.element_type || 'other'}::${x?.name || ''}` === key);
  if (exists) return;
  manualDraft.value.page_elements.push({
    name,
    element_type: newElement.value.element_type || 'other',
    ui_pattern: newElement.value.ui_pattern || '',
    required: false,
    queryable: false,
    validation: newElement.value.validation || '',
    action: '',
    opens_modal: false,
    requires_confirm: false,
    source: 'manual',
    source_text: '',
  });
  newElement.value = { name: '', element_type: 'button', ui_pattern: '按钮', validation: '' };
};

const removeElementFromDraft = (idx) => {
  if (!Array.isArray(manualDraft.value.page_elements)) return;
  manualDraft.value.page_elements.splice(idx, 1);
};

const removeButtonFromDraft = (idx) => {
  if (!Array.isArray(manualDraft.value.buttons)) return;
  const b = manualDraft.value.buttons[idx];
  if (!b) return;
  if (b.name === '取消' || b.name === '保存') return;
  manualDraft.value.buttons.splice(idx, 1);
};

const saveManualDraft = async () => {
  if (!selectedId.value) return;
  isSavingManual.value = true;
  try {
    const payload = {
      page_type: manualDraft.value.page_type || '',
      buttons: Array.isArray(manualDraft.value.buttons) ? manualDraft.value.buttons : [],
      fields: Array.isArray(manualDraft.value.fields) ? manualDraft.value.fields : [],
      page_elements: Array.isArray(manualDraft.value.page_elements) ? manualDraft.value.page_elements : [],
      ocr_raw_text: manualDraft.value.ocr_raw_text || ocrPreviewText.value || '',
      ocr_refs: ocrRefs.value || { button_candidates: [], field_candidates: [] },
      control_logic: manualDraft.value.control_logic || '',
    };

    const resp = await fetch(`/api/history/${selectedId.value}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ manual: payload }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.error || '保存失败');
    }

    await fetchHistory();
    window.dispatchEvent(new Event('history-updated'));
    manualModalOpen.value = false;
    await alertDialog('已保存补录（用于后续用例生成）');
  } catch (e) {
    console.error(e);
    await alertDialog(`保存失败: ${e.message}`);
  } finally {
    isSavingManual.value = false;
  }
};

const saveAnalysis = async () => {
  if (!selectedId.value) return;
  isSaving.value = true;
  saveHint.value = '';
  try {
    const resp = await fetch(`/api/history/${selectedId.value}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ analysis: analysisText.value })
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.error || '保存失败');
    }
    await fetchHistory();
    window.dispatchEvent(new Event('history-updated'));
    saveHint.value = '已保存到截图记录（截图预览页可查看）';
  } catch (e) {
    console.error(e);
    await alertDialog(`保存失败: ${e.message}`);
  } finally {
    isSaving.value = false;
  }
};

watch(selectedId, () => {
  saveHint.value = '';
  manualModalOpen.value = false;
  fieldHints.value = [];
});

watch(analysisText, (v) => {
  // 用户手动编辑分析内容时，也同步更新候选被测项展示
  candidateItems.value = extractCandidates(v);
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
.llm-analysis {
  min-height: 100vh;
}
</style>
