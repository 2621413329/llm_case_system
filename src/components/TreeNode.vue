<template>
  <div
    class="tree-node"
    :class="{ active: isActive, prefixActive: isPrefixActive }"
    @click="emitSelect"
    :style="{ paddingLeft: (node.depth * 14) + 'px' }"
    :title="node.label"
  >
    <span class="tree-label">
      <span v-if="hasChildren" class="tree-toggle" @click.stop="emitToggle">
        {{ node.collapsed ? '▶' : '▼' }}
      </span>
      <span v-else class="tree-toggle-placeholder"></span>
      {{ node.label }}
    </span>
    <span class="tree-count">{{ node.count }}</span>
  </div>

  <template v-if="hasChildren && !node.collapsed">
    <TreeNode
      v-for="c in node.children"
      :key="c.key"
      :node="c"
      :active-path="activePath"
      @toggle="$emit('toggle', $event)"
      @select="$emit('select', $event)"
    />
  </template>
</template>

<script setup>
import { computed } from 'vue';

defineOptions({ name: 'TreeNode' });

const props = defineProps({
  node: { type: Object, required: true },
  activePath: { type: Array, required: true }
});

const emit = defineEmits(['toggle', 'select']);

const hasChildren = computed(() => Array.isArray(props.node.children) && props.node.children.length > 0);

const isActive = computed(() => {
  const p = props.activePath || [];
  const n = props.node.path || [];
  if (p.length !== n.length) return false;
  return n.every((x, i) => x === p[i]);
});

const isPrefixActive = computed(() => {
  const p = props.activePath || [];
  const n = props.node.path || [];
  if (n.length > p.length) return false;
  return n.every((x, i) => x === p[i]);
});

const emitToggle = () => emit('toggle', props.node.key);
const emitSelect = () => emit('select', props.node.path);
</script>

