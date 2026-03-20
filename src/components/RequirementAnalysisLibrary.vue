<template>
  <div class="req-lib">
    <div class="page-header">
      <h1>系统需求分析库</h1>
      <p>为所有截图批量生成：样式分析 / 需求内容分析 / 交互分析 / 数据分析（分批归档）。</p>
    </div>

    <div class="card" style="padding: 12px;">
      <div style="display:flex; gap:12px; flex-wrap:wrap; align-items:center; justify-content: space-between;">
        <div style="display:flex; gap:10px; flex-wrap:wrap; align-items:center;">
          <button class="btn btn-primary" @click="generateAll" :disabled="generating">
            {{ generating ? '生成中...' : '一键生成需求分析库（覆盖式）' }}
          </button>
          <span style="color:#666; font-size:13px;">
            {{ lastResultText }}
          </span>
          <label style="display:flex; align-items:center; gap:8px; color:#666; font-size:13px;">
            <input type="checkbox" v-model="buildNetwork" />
            同时构建需求网络库（向量检索）
          </label>
        </div>
        <button class="btn btn-default" @click="fetchHistory" :disabled="generating">刷新</button>
      </div>

      <div style="display:flex; gap:8px; flex-wrap:wrap; margin-top: 12px;">
        <button
          class="btn"
          :class="activeCategory === 'style' ? 'btn-primary' : 'btn-default'"
          @click="activeCategory = 'style'"
        >
          样式分析（OCR）
        </button>
        <button
          class="btn"
          :class="activeCategory === 'content' ? 'btn-primary' : 'btn-default'"
          @click="activeCategory = 'content'"
        >
          需求内容分析（文字补充 + LLM）
        </button>
        <button
          class="btn"
          :class="activeCategory === 'interaction' ? 'btn-primary' : 'btn-default'"
          @click="activeCategory = 'interaction'"
        >
          交互分析（菜单关联）
        </button>
        <button
          class="btn"
          :class="activeCategory === 'data' ? 'btn-primary' : 'btn-default'"
          @click="activeCategory = 'data'"
        >
          数据分析（OCR分批归档）
        </button>
      </div>

      <div class="form-group" style="margin-top: 12px;">
        <label>选择截图记录</label>
        <select class="input" v-model="selectedId" style="max-width: 680px;">
          <option value="">请选择</option>
          <option v-for="r in records" :key="r.id" :value="String(r.id)">
            {{ r.created_at }} - {{ r.file_name }}
          </option>
        </select>
      </div>
    </div>

    <div class="card" style="margin-top: 12px; padding: 12px;">
      <div v-if="activeRecord" style="display:flex; gap:12px; flex-wrap:wrap; align-items:flex-start; justify-content: space-between;">
        <div style="min-width: 320px;">
          <div style="font-weight: 700; font-size: 14px;">{{ activeRecord.file_name }}</div>
          <div style="color:#666; margin-top: 4px; font-size: 12px;">
            菜单：{{ breadcrumb(activeRecord.menu_structure) || '无' }}
          </div>
          <div style="color:#666; margin-top: 4px; font-size: 12px;">
            最近生成：{{ activeRecord.analysis_generated_at || '—' }}
          </div>
        </div>
        <div style="flex: 1; min-width: 220px;">
          <div style="color:#666; font-size:12px;">快捷信息</div>
          <div style="margin-top: 6px; display:flex; gap:8px; flex-wrap:wrap;">
            <span class="tag" v-if="activeRecord.analysis_style && activeRecord.analysis_style.trim()">样式已生成</span>
            <span class="tag" v-if="activeRecord.analysis_content && activeRecord.analysis_content.trim()">内容已生成</span>
            <span class="tag" v-if="activeRecord.analysis_interaction && activeRecord.analysis_interaction.trim()">交互已生成</span>
            <span class="tag" v-if="activeRecord.analysis_data && (Array.isArray(activeRecord.analysis_data) || Object.keys(activeRecord.analysis_data||{}).length)">数据已生成</span>
          </div>
        </div>
      </div>

      <div v-else style="color:#999; padding: 14px;">
        请先选择截图记录。
      </div>

      <div v-if="activeRecord" style="margin-top: 12px;">
        <div style="color:#666; font-size:12px; margin-bottom: 8px;">
          当前标签：{{ categoryLabel }}
        </div>

        <div style="border:1px solid #eee; border-radius:8px; background:#fafafa; padding: 12px; white-space: pre-wrap; min-height: 280px;">
          <template v-if="activeCategory !== 'data'">
            {{ activeCategoryText }}
          </template>
          <template v-else>
            {{ dataRenderText }}
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { useUiDialog } from '../composables/useUiDialog';

const { alertDialog, showLoading, appendLoadingLog, setLoadingMessage, hideLoading } = useUiDialog();

const records = ref([]);
const selectedId = ref('');
const activeCategory = ref('style'); // style/content/interaction/data
const generating = ref(false);
const lastResultText = ref('未生成');
const buildNetwork = ref(true);

const categoryLabel = computed(() => {
  if (activeCategory.value === 'style') return '样式分析（OCR）';
  if (activeCategory.value === 'content') return '需求内容分析（文字补充 + LLM）';
  if (activeCategory.value === 'interaction') return '交互分析（菜单关联）';
  if (activeCategory.value === 'data') return '数据分析（OCR需求归纳）';
  return '';
});

const fetchHistory = async () => {
  try {
    const resp = await fetch('/api/history');
    if (!resp.ok) throw new Error('获取历史记录失败');
    const data = await resp.json();
    records.value = Array.isArray(data) ? data : [];
    if (!selectedId.value && records.value.length) selectedId.value = String(records.value[0].id);
  } catch (e) {
    console.error(e);
    await alertDialog('刷新失败');
  }
};

const generateAll = async () => {
  generating.value = true;
  lastResultText.value = '请求中...';
  try {
    showLoading({
      title: 'AI 分析进行中...',
      message: '准备生成系统需求分析库（覆盖式）...',
    });

    // SSE：持续接收后端生成进度与 AI 输出预览
    await new Promise((resolve, reject) => {
      const es = new EventSource('/api/requirement-analysis/generate/sse?force=1');
      let doneHandled = false;

      es.addEventListener('progress', (ev) => {
        try {
          const d = JSON.parse(ev.data || '{}');
          const stage = d.stage || '';
          const hid = d.history_id || '';
          setLoadingMessage(`生成进度：${hid ? `[${hid}] ` : ''}${stage}`);
        } catch {
          // ignore
        }
      });

      es.addEventListener('log', (ev) => {
        try {
          const d = JSON.parse(ev.data || '{}');
          const hid = d.history_id ? `[${d.history_id}] ` : '';
          if (d.msg) appendLoadingLog(hid + d.msg);
          if (d.previews && typeof d.previews === 'object') {
            const p = d.previews;
            if (p.analysis_style) appendLoadingLog(`样式预览：${p.analysis_style}`);
            if (p.analysis_content) appendLoadingLog(`内容预览：${p.analysis_content}`);
            if (p.analysis_interaction) appendLoadingLog(`交互预览：${p.analysis_interaction}`);
          }
        } catch {
          // ignore
        }
      });

      es.addEventListener('done', async (ev) => {
        try {
          const d = JSON.parse(ev.data || '{}');
          doneHandled = true;
          appendLoadingLog(`完成：generated=${d.generated || 0}/${d.total || 0}`);
          lastResultText.value = `已生成 ${d.generated || 0}/${d.total || 0} 条`;
          es.close();
          await fetchHistory();

          if (buildNetwork.value) {
            setLoadingMessage('正在构建需求网络库（向量检索）...');
            const resp2 = await fetch('/api/requirement-network/build', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ force: 1 }),
            });
            const data2 = await resp2.json().catch(() => ({}));
            if (!resp2.ok) {
              const msg2 = data2.error || `HTTP ${resp2.status}`;
              throw new Error(msg2);
            }
            appendLoadingLog(`网络库完成：built=${data2.built || 0}/${data2.total || 0}`);
            lastResultText.value = `已生成 ${d.generated || 0}/${d.total || 0} 条；网络库已构建 ${data2.built || 0}/${data2.total || 0} 条`;
          }
          resolve(true);
        } catch (e) {
          try { es.close(); } catch {}
          reject(e);
        }
      });

      es.onerror = async () => {
        if (doneHandled) return;
        try {
          es.close();
        } catch {}
        reject(new Error('SSE 连接异常或服务端执行失败'));
      };
    });
  } catch (e) {
    console.error(e);
    lastResultText.value = '生成失败';
    await alertDialog(`生成失败：${e.message || e}`);
  } finally {
    hideLoading();
    generating.value = false;
  }
};

const activeRecord = computed(() => {
  const id = Number(selectedId.value);
  if (!id) return null;
  return records.value.find((r) => Number(r.id) === id) || null;
});

const breadcrumb = (menuStructure) => {
  return (Array.isArray(menuStructure) ? menuStructure : []).map((x) => x.name).filter(Boolean).join(' / ');
};

const activeCategoryText = computed(() => {
  if (!activeRecord.value) return '';
  if (activeCategory.value === 'style') return activeRecord.value.analysis_style || '';
  if (activeCategory.value === 'content') return activeRecord.value.analysis_content || '';
  if (activeCategory.value === 'interaction') return activeRecord.value.analysis_interaction || '';
  return '';
});

const dataRenderText = computed(() => {
  if (!activeRecord.value) return '';
  const d = activeRecord.value.analysis_data;
  if (!d) return '暂无数据';
  try {
    if (Array.isArray(d)) return JSON.stringify(d, null, 2);
    const ocrProvider = d.ocr_provider || '';
    const excerpt = d.ocr_raw_excerpt || '';
    const elements = Array.isArray(d.elements_overview) ? d.elements_overview : [];

    const lines = [];
    lines.push(`OCR provider: ${ocrProvider || '—'}`);
    lines.push(`OCR excerpt（摘要）：\n${excerpt || '—'}`);
    lines.push('');
    lines.push(`元素归纳数：${elements.length}`);
    if (elements.length) {
      const top = elements.slice(0, 60);
      for (const e of top) {
        const et = e?.element_type || 'other';
        const name = e?.name || '';
        const rule = e?.validation ? ` / rule=${e.validation}` : '';
        lines.push(`• ${et}：${name}${rule}`);
      }
      if (elements.length > top.length) lines.push(`（仅展示前 ${top.length} 条）`);
    }
    return lines.join('\n');
  } catch {
    return JSON.stringify(d, null, 2);
  }
});

onMounted(async () => {
  await fetchHistory();
});
</script>

<style scoped>
.req-lib {
  min-height: 100vh;
}
</style>

