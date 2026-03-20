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

  <!-- 全局 loading 遮罩：禁止用户继续操作 -->
  <div v-if="state.loadingOpen" class="loading-mask">
    <div class="loading-card">
      <div class="loading-head">
        <div class="loading-title">
          {{ state.loadingTitle }}
        </div>
        <div class="spinner" aria-label="loading" />
      </div>
      <div class="loading-message">{{ state.loadingMessage }}</div>
      <div v-if="state.loadingLogs && state.loadingLogs.length" class="loading-logs">
        <div v-for="(l, idx) in state.loadingLogs" :key="idx" class="loading-log">
          {{ l }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useUiDialog } from '../composables/useUiDialog';

const { state, closeWith } = useUiDialog();

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

.loading-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  z-index: 3000;
}
.loading-card {
  width: min(720px, 100%);
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.15);
  border: 1px solid rgba(0,0,0,0.06);
  padding: 16px 16px 14px 16px;
}
.loading-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.loading-title {
  font-weight: 800;
  font-size: 14px;
  color: #111;
}
.spinner {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 2px solid rgba(24, 144, 255, 0.2);
  border-top-color: #1890ff;
  animation: spin 0.9s linear infinite;
}
.loading-message {
  margin-top: 10px;
  color: #333;
  font-size: 13px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}
.loading-logs {
  margin-top: 12px;
  border: 1px solid #f0f0f0;
  border-radius: 10px;
  background: #fafafa;
  padding: 10px;
  max-height: 340px;
  overflow: auto;
}
.loading-log {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  font-size: 12px;
  color: #333;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.6;
  padding: 4px 2px;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>

