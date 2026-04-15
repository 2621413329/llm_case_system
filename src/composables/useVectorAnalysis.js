import { ref } from 'vue';
import { updateHistory } from '../api/history';
import {
  analyzeRequirementVector,
  buildRequirementNetwork,
  previewRequirementNetworkBuild,
} from '../api/requirement';
import { emitHistoryUpdated } from './useHistorySync';

/**
 * @param {Object} opts
 * @param {import('vue').ComputedRef} opts.activeRecord
 * @param {import('vue').Ref} opts.records
 * @param {Function} opts.alertDialog
 * @param {Object} opts.systemStore
 */
export function useVectorAnalysis({ activeRecord, records, alertDialog, systemStore }) {
  const vectorAnalyzing = ref(false);
  const vectorAnalysisResult = ref('');
  const vectorBuildText = ref('');
  const vectorBuildResult = ref('');
  const syncingVector = ref(false);
  const vectorSyncHint = ref('');
  const vectorSaving = ref(false);

  function mergeUpdatedRecord(recordId, updated) {
    const idx = records.value.findIndex((r) => Number(r.id) === Number(recordId));
    if (idx >= 0 && updated && typeof updated === 'object') {
      Object.assign(records.value[idx], updated);
    }
  }

  async function analyzeVectorForCurrentRecord() {
    const rec = activeRecord.value;
    if (!rec) {
      await alertDialog('请先选择一条记录');
      return;
    }
    vectorAnalyzing.value = true;
    try {
      const data = await analyzeRequirementVector(rec.id, systemStore.systemId || null);
      vectorAnalysisResult.value = String(data.analysis_result || '').trim();

      const updated = await updateHistory(rec.id, {
        analysis: vectorAnalysisResult.value,
      });
      mergeUpdatedRecord(rec.id, updated);
      emitHistoryUpdated();

      if (!vectorAnalysisResult.value) {
        await alertDialog('AI需求分析已执行，但暂未生成可展示的分析总结。');
      }
    } catch (e) {
      await alertDialog(`AI需求分析执行失败：${e.message || e}`);
    } finally {
      vectorAnalyzing.value = false;
    }
  }

  async function ensureVectorBuildTextForCurrentRecord(opts = {}) {
    const rec = activeRecord.value;
    if (!rec) {
      return '';
    }
    const currentText = String(
      opts.buildText || vectorBuildText.value || rec.vector_analysis_text || '',
    ).trim();
    if (currentText && opts.regenerate !== true) {
      vectorBuildText.value = currentText;
      return currentText;
    }

    let buildText = '';
    try {
      const data = await previewRequirementNetworkBuild(rec.id, systemStore.systemId || null);
      buildText = String(data.build_text || '').trim();
    } catch (e) {
      const fallbackText = String(rec.vector_analysis_text || '').trim();
      if (!fallbackText) {
        throw new Error('建库联动文本预览接口不可用，请重启后端后重试');
      }
      buildText = fallbackText;
    }
    vectorBuildText.value = buildText;

    const updated = await updateHistory(rec.id, {
      vector_analysis_text: buildText,
    });
    mergeUpdatedRecord(rec.id, updated);
    emitHistoryUpdated();
    return buildText;
  }

  async function syncVectorForCurrentRecord(opts) {
    const silent = Boolean(opts && opts.silent);
    const rec = activeRecord.value;
    if (!rec) return;

    syncingVector.value = true;
    vectorSyncHint.value = '';
    try {
      // 默认每次「产出向量库」都向后端重算建库文本，否则会一直沿用库里旧的 vector_analysis_text（看不到新模板）
      const regenerateBuildText =
        opts && typeof opts === 'object' && 'regenerateBuildText' in opts
          ? Boolean(opts.regenerateBuildText)
          : true;
      const buildText = await ensureVectorBuildTextForCurrentRecord({
        buildText: opts && opts.buildText,
        regenerate: regenerateBuildText,
      });
      const buildPayload = {
        history_id: rec.id,
        force: 1,
        analysis_result_text: buildText,
        build_scope: 'final_only',
      };
      if (systemStore.systemId) buildPayload.system_id = systemStore.systemId;

      const buildData = await buildRequirementNetwork(buildPayload);
      const built = Number(buildData?.built ?? 0);
      const errs = Array.isArray(buildData?.errors) ? buildData.errors : [];
      if (built <= 0) {
        const e0 = errs[0];
        const em = e0 && typeof e0 === 'object' ? String(e0.error || '').trim() : String(e0 || '').trim();
        throw new Error(
          em || '向量库构建未写入任何单元（built=0），请检查 MySQL、嵌入模型配置、建库联动文本是否为空',
        );
      }
      let summary = String(buildData?.build_summary || '').trim();
      if (!summary && Array.isArray(buildData?.build_results) && buildData.build_results.length) {
        const parts = buildData.build_results
          .map((row) => String(row?.summary || '').trim())
          .filter(Boolean);
        if (parts.length) summary = parts.join('\n\n---\n\n');
      }
      vectorBuildResult.value = summary;
      vectorBuildText.value = buildText;

      const builtAt = new Date().toISOString();
      const updated = await updateHistory(rec.id, {
        vector_analysis_text: buildText,
        vector_build_summary: vectorBuildResult.value,
        vector_built_at: builtAt,
      });
      mergeUpdatedRecord(rec.id, updated);
      emitHistoryUpdated();

      vectorSyncHint.value = '已按最新规则重新生成建库联动文本并完成向量写入。';
      if (!silent) {
        await alertDialog('产出向量库完成：已重新生成建库联动文本（含「【业务检索句】」页面=；操作=；条件=；结果= 模板）并完成建库。');
      }
    } catch (e) {
      vectorSyncHint.value = '';
      if (!silent) await alertDialog(`产出向量库失败：${e.message || e}`);
      else console.warn(e);
    } finally {
      syncingVector.value = false;
    }
  }

  async function saveVectorContent(mode = 'analysis') {
    const rec = activeRecord.value;
    if (!rec) {
      await alertDialog('请先选择一条记录');
      return;
    }
    vectorSaving.value = true;
    try {
      const payload = mode === 'build'
        ? { vector_analysis_text: String(vectorBuildText.value || '').trim() }
        : { analysis: String(vectorAnalysisResult.value || '').trim() };
      const updated = await updateHistory(rec.id, payload);
      mergeUpdatedRecord(rec.id, updated);
      await alertDialog(mode === 'build' ? '当前建库联动文本已保存' : '当前AI需求分析已保存');
      emitHistoryUpdated();
    } catch (e) {
      await alertDialog(`保存失败：${e.message || e}`);
    } finally {
      vectorSaving.value = false;
    }
  }

  return {
    vectorAnalyzing,
    vectorAnalysisResult,
    vectorBuildText,
    vectorBuildResult,
    syncingVector,
    vectorSyncHint,
    vectorSaving,
    analyzeVectorForCurrentRecord,
    ensureVectorBuildTextForCurrentRecord,
    syncVectorForCurrentRecord,
    saveVectorContent,
  };
}
