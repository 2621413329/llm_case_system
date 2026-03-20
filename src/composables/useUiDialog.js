import { reactive } from 'vue';

const state = reactive({
  open: false,
  mode: 'alert', // alert | confirm
  title: '提示',
  message: '',
  confirmText: '确定',
  cancelText: '取消',
  // 全局 loading：用于长耗时 AI/批处理时锁定 UI
  loadingOpen: false,
  loadingTitle: '处理中...',
  loadingMessage: '',
  loadingLogs: [],
  _resolver: null,
});

function closeWith(result) {
  const resolver = state._resolver;
  state.open = false;
  state._resolver = null;
  if (typeof resolver === 'function') resolver(result);
}

export function useUiDialog() {
  const alertDialog = (message, title = '提示') =>
    new Promise((resolve) => {
      state.mode = 'alert';
      state.title = title;
      state.message = String(message ?? '');
      state.confirmText = '确定';
      state.cancelText = '取消';
      state._resolver = () => resolve(true);
      state.open = true;
    });

  const confirmDialog = (
    message,
    {
      title = '请确认',
      confirmText = '确定',
      cancelText = '取消',
    } = {}
  ) =>
    new Promise((resolve) => {
      state.mode = 'confirm';
      state.title = title;
      state.message = String(message ?? '');
      state.confirmText = confirmText;
      state.cancelText = cancelText;
      state._resolver = (ok) => resolve(!!ok);
      state.open = true;
    });

  return {
    state,
    alertDialog,
    confirmDialog,
    closeWith,
    showLoading: ({ title, message } = {}) => {
      state.loadingOpen = true;
      state.loadingTitle = title || '处理中...';
      state.loadingMessage = message || '';
      state.loadingLogs = [];
    },
    setLoadingMessage: (message) => {
      state.loadingMessage = String(message ?? '');
    },
    appendLoadingLog: (log) => {
      const s = String(log ?? '');
      if (!s) return;
      state.loadingLogs.push(s);
    },
    hideLoading: () => {
      state.loadingOpen = false;
      state.loadingTitle = '处理中...';
      state.loadingMessage = '';
      state.loadingLogs = [];
    },
  };
}

