import { ref, computed, watch, nextTick, onUnmounted } from 'vue';
import { updateHistory } from '../api/history';
import { emitHistoryUpdated } from './useHistorySync';

/** OCR 样式分析「属性」下拉默认项（与产品约定一致） */
const DEFAULT_ATTR_OPTIONS = ['标题', '按钮', '查询', '输入框', '文本', '分页', '表格内容', '表格标题'];

function normalizeStyleRow(r) {
  if (!r || typeof r !== 'object') return { element: '', attribute: '文本', requirement: '' };
  let el = typeof r.element === 'string' ? r.element : '';
  let req = typeof r.requirement === 'string' ? r.requirement : '';
  let attr = typeof r.attribute === 'string' ? r.attribute.trim() : '';
  if (!attr && Array.isArray(r.attributes) && r.attributes.length) {
    attr = String(r.attributes[0] || '').trim();
  }
  if (!attr) attr = '文本';
  if (!el.trim() && req.trim()) {
    el = req;
    req = '';
  }
  return { element: el, attribute: attr, requirement: req };
}

function stripStyleOcrPrefix(text) {
  const t = (text || '').trim();
  if (!t) return '';
  const m = t.match(/^OCR识别原文（来自[^，]+，摘要）：\s*\n?/);
  return m ? t.slice(m[0].length).trim() : t;
}

function linesFromStyleText(text) {
  const body = stripStyleOcrPrefix(text);
  const lines = body.split(/\n/).map((s) => s.trim()).filter(Boolean);
  if (!lines.length) return [{ element: '', attribute: '文本', requirement: '' }];
  return lines.map((line) => ({ element: line, attribute: '文本', requirement: '' }));
}

function styleTextFromRows(rows) {
  if (!Array.isArray(rows)) return '';
  return rows
    .map((r) => (r && typeof r === 'object' ? String(r.element || '').trim() : ''))
    .filter(Boolean)
    .join('\n');
}

function normalizeRowsForSave(rows) {
  const mapped = (Array.isArray(rows) ? rows : []).map((r) => ({
    element: (r?.element || '').trim(),
    attribute: (r?.attribute || '文本').trim() || '文本',
    requirement: r?.requirement || '',
  }));
  return mapped.length ? mapped : [{ element: '', attribute: '文本', requirement: '' }];
}

function styleTableHasDisplayContent(rows) {
  if (!Array.isArray(rows) || !rows.length) return false;
  return rows.some((r) => {
    const n = normalizeStyleRow(r);
    const attr = (n.attribute || '').trim();
    const attrMeaningful = attr && attr !== '文本';
    return (n.element || '').trim() || (n.requirement || '').trim() || attrMeaningful;
  });
}

/**
 * @param {Object} opts
 * @param {import('vue').Ref} opts.activeRecord
 * @param {import('vue').Ref} opts.activeCategory
 * @param {import('vue').Ref} opts.records
 * @param {import('vue').Ref} opts.selectedId
 * @param {Function} opts.alertDialog
 */
export function useStyleTable({ activeRecord, activeCategory, records, selectedId, alertDialog }) {
  const styleRows = ref([]);
  const extraAttrOptions = ref([]);
  const newAttrOption = ref('');
  const styleSaving = ref(false);
  const styleTableHydrating = ref(false);
  const styleSaveStatus = ref('');
  let styleAutoSaveTimer = null;
  let styleSaveStatusClearTimer = null;

  const allAttributeOptions = computed(() => {
    const set = new Set([...DEFAULT_ATTR_OPTIONS, ...extraAttrOptions.value]);
    return Array.from(set);
  });

  function loadStyleRowsFromRecord(rec) {
    const table = rec?.analysis_style_table;
    if (Array.isArray(table) && styleTableHasDisplayContent(table)) {
      styleRows.value = table.map(normalizeStyleRow);
      return;
    }
    styleRows.value = linesFromStyleText(rec?.analysis_style || '');
  }

  function coerceHistoryId(id) {
    const n = Number(id);
    return Number.isFinite(n) ? n : NaN;
  }

  async function flushStyleToHistoryId(historyId, silent = true, opts = {}) {
    const { suppressStatus = false, skipSavingState = false } = opts;
    if (!historyId || !Number.isFinite(Number(historyId))) return;
    if (!skipSavingState) styleSaving.value = true;
    try {
      const rows = normalizeRowsForSave(styleRows.value);
      const data = await updateHistory(Number(historyId), {
        analysis_style_table: rows,
        analysis_style: styleTextFromRows(rows),
      });
      const idx = records.value.findIndex((r) => Number(r.id) === Number(historyId));
      if (idx >= 0) Object.assign(records.value[idx], data);
      if (!silent) emitHistoryUpdated();
      if (silent) {
        if (!suppressStatus) {
          styleSaveStatus.value = `已自动保存 ${new Date().toLocaleTimeString()}`;
          clearTimeout(styleSaveStatusClearTimer);
          styleSaveStatusClearTimer = setTimeout(() => { styleSaveStatus.value = ''; }, 4000);
        }
      } else {
        await alertDialog('保存成功');
      }
    } catch (e) {
      if (silent) {
        if (!suppressStatus) {
          styleSaveStatus.value = '自动保存失败，请检查网络';
          clearTimeout(styleSaveStatusClearTimer);
          styleSaveStatusClearTimer = setTimeout(() => { styleSaveStatus.value = ''; }, 6000);
        }
        console.warn(e);
      } else {
        await alertDialog(`保存失败：${e.message || e}`);
      }
    } finally {
      if (!skipSavingState) styleSaving.value = false;
    }
  }

  async function persistStyleTable(silent = true) {
    const rec = activeRecord.value;
    if (!rec) return;
    if (activeCategory.value !== 'style') return;
    if (styleTableHydrating.value) return;
    await flushStyleToHistoryId(rec.id, silent);
  }

  function addStyleRow() {
    styleRows.value.push({ element: '', attribute: '文本', requirement: '' });
  }

  async function removeStyleRow(idx) {
    const rec = activeRecord.value;
    if (!rec || activeCategory.value !== 'style') return;
    const hid = coerceHistoryId(rec.id);
    const rowIdx = Number(idx);
    if (!Number.isFinite(hid) || !Number.isInteger(rowIdx) || rowIdx < 0) {
      await alertDialog('无效记录或行号');
      return;
    }
    clearTimeout(styleAutoSaveTimer);
    styleSaving.value = true;
    styleTableHydrating.value = true;
    const prevRows = styleRows.value.map((r) => ({ ...r }));
    try {
      const mapped = normalizeRowsForSave(styleRows.value);
      let nextRows = mapped.filter((_, i) => i !== rowIdx);
      nextRows = normalizeRowsForSave(nextRows);
      styleRows.value = nextRows.map((r) => ({ ...r }));
      const data = await updateHistory(hid, {
        analysis_style_table: nextRows,
        analysis_style: styleTextFromRows(nextRows),
      });
      if (data && typeof data === 'object' && data.id != null) {
        const ridx = records.value.findIndex((r) => Number(r.id) === Number(data.id));
        if (ridx >= 0) Object.assign(records.value[ridx], data);
        loadStyleRowsFromRecord(ridx >= 0 ? records.value[ridx] : data);
      } else {
        loadStyleRowsFromRecord(data || {});
      }
      styleSaveStatus.value = `已删除 ${new Date().toLocaleTimeString()}`;
      clearTimeout(styleSaveStatusClearTimer);
      styleSaveStatusClearTimer = setTimeout(() => { styleSaveStatus.value = ''; }, 4000);
      emitHistoryUpdated();
    } catch (e) {
      styleRows.value = prevRows;
      await alertDialog(`删除失败：${e.message || e}`);
    } finally {
      styleSaving.value = false;
      await nextTick();
      styleTableHydrating.value = false;
    }
  }

  function addCustomAttrOption() {
    const s = (newAttrOption.value || '').trim();
    if (!s) return;
    if (!extraAttrOptions.value.includes(s)) extraAttrOptions.value.push(s);
    newAttrOption.value = '';
  }

  const saveStyleTableManual = () => persistStyleTable(false);

  /** 供外部在切换记录/标签前取消待写入的防抖保存，避免写到错误 history */
  function clearStyleAutoSaveDebounce() {
    clearTimeout(styleAutoSaveTimer);
    styleAutoSaveTimer = null;
  }

  watch(styleRows, () => {
    if (styleTableHydrating.value) return;
    if (!activeRecord.value || activeCategory.value !== 'style') return;
    clearTimeout(styleAutoSaveTimer);
    styleAutoSaveTimer = setTimeout(() => { persistStyleTable(true); }, 550);
  }, { deep: true });

  onUnmounted(() => {
    clearTimeout(styleAutoSaveTimer);
    clearTimeout(styleSaveStatusClearTimer);
  });

  return {
    styleRows,
    extraAttrOptions,
    newAttrOption,
    styleSaving,
    styleTableHydrating,
    styleSaveStatus,
    allAttributeOptions,
    loadStyleRowsFromRecord,
    flushStyleToHistoryId,
    clearStyleAutoSaveDebounce,
    persistStyleTable,
    addStyleRow,
    removeStyleRow,
    addCustomAttrOption,
    saveStyleTableManual,
    DEFAULT_ATTR_OPTIONS,
  };
}
