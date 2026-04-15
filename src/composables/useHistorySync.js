const HISTORY_UPDATED_EVENT = 'history-updated';

export function emitHistoryUpdated() {
  window.dispatchEvent(new Event(HISTORY_UPDATED_EVENT));
}

export function subscribeHistoryUpdated(callback) {
  if (typeof callback !== 'function') return () => {};
  window.addEventListener(HISTORY_UPDATED_EVENT, callback);
  return () => {
    window.removeEventListener(HISTORY_UPDATED_EVENT, callback);
  };
}
