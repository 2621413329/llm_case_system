import { defineStore } from 'pinia';
import { ref, computed } from 'vue';

export const useSystemStore = defineStore('system', () => {
  const selectedSystem = ref(null);

  const systemId = computed(() => selectedSystem.value?.id ?? null);
  const systemName = computed(() => selectedSystem.value?.name ?? '');

  function selectSystem(sys) {
    selectedSystem.value = sys;
  }

  function clearSystem() {
    selectedSystem.value = null;
  }

  return { selectedSystem, systemId, systemName, selectSystem, clearSystem };
});
