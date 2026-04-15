<template>
  <div v-if="state.open" class="dialog-mask" @click.self="onCancel">
    <div class="dialog card">
      <div class="dialog-head">
        <div class="dialog-title">{{ state.title }}</div>
      </div>
      <div class="dialog-body">{{ state.message }}</div>
      <div class="dialog-foot">
        <button
          v-if="state.mode === 'confirm'"
          class="btn btn-default"
          @click="onCancel"
        >
          {{ state.cancelText }}
        </button>
        <button class="btn btn-primary" @click="onConfirm">
          {{ state.confirmText }}
        </button>
      </div>
    </div>
  </div>

  <!-- 全局 loading：浅灰全屏 + 居中圆环（长耗时任务锁定 UI） -->
  <div
    v-if="state.loadingOpen"
    class="global-loading-mask"
    role="alertdialog"
    aria-busy="true"
    :aria-label="state.loadingTitle || '加载中'"
  >
    <div class="global-loading-center">
      <div class="global-loading-spinner" aria-hidden="true">
        <span class="global-loading-spinner__arc global-loading-spinner__arc--outer" />
        <span class="global-loading-spinner__arc global-loading-spinner__arc--inner" />
      </div>
      <p v-if="loadingCaption" class="global-loading-caption">{{ loadingCaption }}</p>
      <div v-if="state.loadingLogs && state.loadingLogs.length" class="global-loading-logs">
        <div v-for="(l, idx) in state.loadingLogs" :key="idx" class="global-loading-log">
          {{ l }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { useUiDialog } from '../composables/useUiDialog';

const { state, closeWith } = useUiDialog();

/** 优先展示进度文案，否则标题；无则只显示圆环 */
const loadingCaption = computed(() => {
  const m = String(state.loadingMessage ?? '').trim();
  if (m) return m;
  const t = String(state.loadingTitle ?? '').trim();
  if (t && t !== '处理中...') return t;
  return '';
});

const onConfirm = () => closeWith(true);
const onCancel = () => closeWith(false);
</script>

<style scoped>
.dialog-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  z-index: 2000;
}
.dialog {
  width: min(520px, 100%);
  margin: 0;
}
.dialog-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.dialog-title {
  font-weight: 700;
}
.dialog-body {
  margin-top: 12px;
  color: #333;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.6;
}
.dialog-foot {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.global-loading-mask {
  position: fixed;
  inset: 0;
  background: #d8d8d8;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  z-index: 3000;
  pointer-events: all;
}

.global-loading-center {
  display: flex;
  flex-direction: column;
  align-items: center;
  max-width: min(720px, 100%);
}

/* 双弧交错圆环（细线、深灰，类似参考图） */
.global-loading-spinner {
  position: relative;
  width: 52px;
  height: 52px;
  flex-shrink: 0;
}

.global-loading-spinner__arc {
  display: block;
  position: absolute;
  box-sizing: border-box;
  border-radius: 50%;
  border: 2px solid transparent;
}

.global-loading-spinner__arc--outer {
  inset: 0;
  border-top-color: #4a5563;
  border-right-color: #4a5563;
  animation: global-loading-spin 0.95s linear infinite;
}

.global-loading-spinner__arc--inner {
  width: 68%;
  height: 68%;
  left: 16%;
  top: 16%;
  border-bottom-color: #4a5563;
  border-left-color: #4a5563;
  animation: global-loading-spin 0.75s linear infinite reverse;
}

.global-loading-caption {
  margin: 20px 0 0;
  padding: 0 12px;
  text-align: center;
  font-size: 13px;
  line-height: 1.5;
  color: #4b5563;
  white-space: pre-wrap;
  word-break: break-word;
  max-width: 100%;
}

.global-loading-logs {
  margin-top: 16px;
  width: 100%;
  max-height: min(38vh, 320px);
  overflow: auto;
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.45);
  border: 1px solid rgba(0, 0, 0, 0.06);
}

.global-loading-log {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  font-size: 11px;
  color: #374151;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.55;
  padding: 3px 0;
}

@keyframes global-loading-spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>

