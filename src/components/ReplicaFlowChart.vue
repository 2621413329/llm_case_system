<template>
  <div class="replica-flow-canvas">
    <div class="replica-flow-canvas__title">流程图预览</div>
    <div class="replica-wireframe">
      <div class="replica-wireframe__inner">
      <svg class="replica-wireframe__lines" viewBox="0 0 1320 340" preserveAspectRatio="xMinYMin meet" aria-hidden="true">
        <defs>
          <marker id="replica-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M0 0 L10 5 L0 10 z" />
          </marker>
        </defs>

        <path id="rep-line-style-content"
          class="replica-wireframe__path replica-wireframe__path--pre"
          :class="{ 'is-ready': stageDoneMap.style, 'is-locked': !stageDoneMap.style }"
          d="M218 166 L264 166 L320 78" />
        <path id="rep-line-style-interaction"
          class="replica-wireframe__path replica-wireframe__path--pre"
          :class="{ 'is-ready': stageDoneMap.style, 'is-locked': !stageDoneMap.style }"
          d="M218 166 L272 166 L320 168" />
        <path id="rep-line-style-data"
          class="replica-wireframe__path replica-wireframe__path--pre"
          :class="{ 'is-ready': stageDoneMap.style, 'is-locked': !stageDoneMap.style }"
          d="M218 166 L264 166 L320 258" />
        <path id="rep-line-content-ai"
          class="replica-wireframe__path replica-wireframe__path--to-ai"
          :class="{ 'is-ready': aggregationReady, 'is-locked': !aggregationReady }"
          d="M540 78 L580 78 L620 168" />
        <path id="rep-line-interaction-ai"
          class="replica-wireframe__path replica-wireframe__path--to-ai"
          :class="{ 'is-ready': aggregationReady, 'is-locked': !aggregationReady }"
          d="M540 168 L580 168 L620 168" />
        <path id="rep-line-data-ai"
          class="replica-wireframe__path replica-wireframe__path--to-ai"
          :class="{ 'is-ready': aggregationReady, 'is-locked': !aggregationReady }"
          d="M540 258 L580 258 L620 168" />
        <path id="rep-line-hub-ai"
          class="replica-wireframe__path replica-wireframe__path--to-ai"
          :class="{ 'is-ready': aggregationReady, 'is-locked': !aggregationReady }"
          d="M716 168 L900 168" />
        <path id="rep-line-ai-output"
          class="replica-wireframe__path replica-wireframe__path--to-output"
          :class="{ 'is-ready': canBuildVectorLibrary, 'is-locked': !canBuildVectorLibrary }"
          d="M1120 168 L1160 168" />

        <text class="replica-wireframe__line-text">
          <textPath href="#rep-line-style-content" startOffset="40%">（基于样式/OCR）</textPath>
        </text>
        <text class="replica-wireframe__line-text">
          <textPath href="#rep-line-style-interaction" startOffset="38%">（基于样式/OCR）</textPath>
        </text>
        <text class="replica-wireframe__line-text">
          <textPath href="#rep-line-style-data" startOffset="40%">（功能与上下游）</textPath>
        </text>
      </svg>

      <div class="replica-aggregate-hub" :class="{ 'is-ready': aggregationReady, 'is-locked': !aggregationReady }">
        需求分析聚合
      </div>

      <button type="button"
        v-for="stage in stageNodes" :key="stage.key"
        :class="['replica-flow-node', `replica-flow-node--${stage.key}`, ...stageClassByKey(stage.key)]"
        :disabled="isStageNodeDisabled(stage.key)"
        @click="$emit('stage-click', stage.key)">
        <span class="replica-flow-node__title">{{ stage.title }}</span>
        <span class="replica-flow-node__hint">{{ stage.hint }}</span>
        <span class="replica-flow-node__status">{{ stageStatusLabel(stage.key) }}</span>
      </button>

      <button type="button"
        class="replica-flow-node replica-flow-node--ai"
        :class="{ 'is-locked': !canRunOverallAnalyze && !hasOverallAnalysis, 'is-done': hasOverallAnalysis }"
        :disabled="!canRunOverallAnalyze"
        @click="$emit('overall-click')">
        <span class="replica-flow-node__title">AI需求分析产出向量库</span>
        <span class="replica-flow-node__hint">列表查询</span>
        <span class="replica-flow-node__status">{{ hasOverallAnalysis ? '已完成' : (canRunOverallAnalyze ? '可执行' : '待聚合完成') }}</span>
      </button>

      <button type="button"
        class="replica-flow-node replica-flow-node--output"
        :class="{ 'is-locked': !hasOverallAnalysis && !vectorBuiltForCurrent, 'is-done': vectorBuiltForCurrent }"
        :disabled="!hasOverallAnalysis && !vectorBuiltForCurrent"
        @click="$emit('output-click')">
        <span class="replica-flow-node__title">产出向量库</span>
        <span class="replica-flow-node__hint">查询</span>
        <span class="replica-flow-node__status">{{ vectorBuiltForCurrent ? '已完成' : (hasOverallAnalysis ? '可查看' : '待总体分析结果') }}</span>
      </button>
      </div>
    </div>
    <div class="replica-flow-note">需求内容分析/交互分析/数据分析三项完成后，才会解锁「需求分析聚合」并可进入 AI 需求分析节点。</div>
  </div>
</template>

<script setup>
defineProps({
  stageDoneMap: { type: Object, required: true },
  aggregationReady: { type: Boolean, default: false },
  canRunOverallAnalyze: { type: Boolean, default: false },
  canBuildVectorLibrary: { type: Boolean, default: false },
  hasOverallAnalysis: { type: Boolean, default: false },
  vectorBuiltForCurrent: { type: Boolean, default: false },
  stageClassByKey: { type: Function, required: true },
  stageStatusLabel: { type: Function, required: true },
  isStageNodeDisabled: { type: Function, required: true },
});

defineEmits(['stage-click', 'overall-click', 'output-click']);

const stageNodes = [
  { key: 'style', title: '样式分析（OCR）', hint: '样式列表' },
  { key: 'content', title: '需求内容分析', hint: '文本输入' },
  { key: 'interaction', title: '交互分析', hint: '文本输入' },
  { key: 'data', title: '数据分析', hint: '文本输入' },
];
</script>

<style scoped>
.replica-flow-canvas {
  margin-top: 12px;
  border: 1px solid #d9dfeb;
  border-radius: 12px;
  background: linear-gradient(180deg, #fbfcff 0%, #f4f7fd 100%);
  padding: 12px;
}
.replica-flow-canvas__title {
  font-size: 13px;
  font-weight: 700;
  color: #33445f;
  margin-bottom: 10px;
}
.replica-wireframe {
  position: relative;
  min-height: 320px;
  border: 1px solid #cfd7e6;
  border-radius: 8px;
  background: #fff;
  overflow-x: auto;
  overflow-y: hidden;
  padding: 10px;
}
.replica-wireframe__inner {
  position: relative;
  width: 1320px;
  height: 340px;
}
.replica-wireframe__lines {
  position: absolute;
  left: 0;
  top: 0;
  width: 1320px;
  height: 340px;
  pointer-events: none;
  z-index: 1;
}
.replica-wireframe__path {
  fill: none;
  stroke: #8f9db5;
  stroke-width: 1.1;
  marker-end: url(#replica-arrow);
}
.replica-wireframe__path--pre.is-locked {
  stroke: #aeb8c9;
  stroke-dasharray: 4 4;
}
.replica-wireframe__path--pre.is-ready {
  stroke: #2f73d9;
  stroke-width: 1.5;
  stroke-dasharray: 6 4;
  animation: replica-flow-dash 1.5s linear infinite;
}
.replica-wireframe__path--to-ai.is-locked,
.replica-wireframe__path--to-output.is-locked {
  stroke: #a7b2c5;
  stroke-dasharray: 4 4;
}
.replica-wireframe__path--to-ai.is-ready,
.replica-wireframe__path--to-output.is-ready {
  stroke: #2f73d9;
  stroke-width: 1.5;
  stroke-dasharray: 7 5;
  animation: replica-flow-dash 1.2s linear infinite;
}
.replica-wireframe__lines marker path {
  fill: #8f9db5;
}
.replica-wireframe__line-text {
  font-size: 10px;
  fill: #5e6d86;
  paint-order: stroke;
  stroke: #fff;
  stroke-width: 3px;
  stroke-linejoin: round;
}
.replica-aggregate-hub {
  position: absolute;
  left: 620px;
  top: 152px;
  z-index: 3;
  width: 96px;
  min-height: 28px;
  border: 1px solid #cfd7e6;
  border-radius: 999px;
  background: #f8fafc;
  color: #64748b;
  font-size: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.25s ease;
}
.replica-aggregate-hub.is-ready {
  border-color: #2f73d9;
  color: #1d4fa3;
  background: #eaf3ff;
  box-shadow: 0 0 0 3px rgba(47, 115, 217, 0.12);
}
.replica-aggregate-hub.is-locked {
  opacity: 0.78;
}
.replica-flow-node {
  position: absolute;
  z-index: 2;
  border: 1px solid #ced5e2;
  border-radius: 4px;
  background: #fff;
  text-align: center;
  padding: 8px 10px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  transition: all 0.2s ease;
  min-height: 56px;
  box-shadow: 0 1px 2px rgba(31, 54, 91, 0.05);
}
.replica-flow-node:disabled {
  cursor: not-allowed;
}
.replica-flow-node:hover {
  border-color: #8fb0e8;
  box-shadow: 0 5px 14px rgba(45, 96, 173, 0.12);
}
.replica-flow-node:disabled:hover {
  border-color: #ced5e2;
  box-shadow: none;
}
.replica-flow-node.is-active {
  border-color: #4f7fce;
  background: linear-gradient(180deg, #f7fbff 0%, #eef5ff 100%);
}
.replica-flow-node.is-done {
  border-color: #9fd7b6;
  background: linear-gradient(180deg, #f5fff8 0%, #ecfbf2 100%);
}
.replica-flow-node.is-locked {
  background: #f6f7fa;
  border-color: #d8dde7;
}
.replica-flow-node.is-pending .replica-flow-node__status {
  color: #8b97ab;
}
.replica-flow-node__title {
  font-size: 12px;
  font-weight: 700;
  color: #263754;
}
.replica-flow-node__hint {
  font-size: 11px;
  color: #73829a;
  line-height: 1.3;
}
.replica-flow-node__status {
  margin-top: 2px;
  font-size: 11px;
  color: #3f6cb2;
}
.replica-flow-node.is-locked .replica-flow-node__status {
  color: #95a0b3;
}
.replica-flow-node--style {
  left: 48px;
  top: 138px;
  width: 170px;
}
.replica-flow-node--content {
  left: 320px;
  top: 46px;
  width: 220px;
}
.replica-flow-node--interaction {
  left: 320px;
  top: 138px;
  width: 220px;
}
.replica-flow-node--data {
  left: 320px;
  top: 230px;
  width: 220px;
}
.replica-flow-node--ai {
  left: 900px;
  top: 138px;
  width: 220px;
}
.replica-flow-node--output {
  left: 1160px;
  top: 138px;
  width: 140px;
}
.replica-flow-note {
  margin-top: 8px;
  font-size: 12px;
  color: #6a778f;
}
.replica-flow-node--ai .replica-flow-node__status,
.replica-flow-node--output .replica-flow-node__status {
  transition: color 0.2s ease;
}
@media (max-width: 1100px) {
  .replica-wireframe {
    min-height: 340px;
  }
}
@keyframes replica-flow-dash {
  to {
    stroke-dashoffset: -24;
  }
}
</style>
