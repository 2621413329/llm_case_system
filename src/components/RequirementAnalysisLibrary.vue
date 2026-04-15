<template>
  <div class="req-lib" :class="{ 'req-lib--replica': isReplicaMode }">
    <div v-if="isReplicaMode" class="card replica-shell">
      <div class="replica-shell__head">
        <div class="replica-shell__selector">
          <label class="replica-label">选择需求记录</label>
          <div class="replica-record-select">
            <el-select
              v-model="selectedId"
              class="req-record-picker"
              filterable
              clearable
              :fit-input-width="false"
              :title="recordPickerTitleAttr"
              placeholder="搜索路径、文件名、时间、ID 或状态（未完成/进行中/已完成）…"
              :disabled="recordPickerDisabledReplica"
              :filter-method="onRecordSelectFilter"
              popper-class="req-record-picker-dropdown"
              teleported
              style="width: 100%"
              @visible-change="onRecordPickerVisible"
            >
              <template #empty>
                <div class="req-record-picker-empty">{{ historyLoading ? '加载中…' : '暂无需求记录' }}</div>
              </template>
              <el-option
                v-for="r in recordsForSelectDropdown"
                :key="`rep-${r.id}`"
                :label="recordSelectDisplayLabel(r)"
                :value="String(r.id)"
              >
                <div class="req-record-option">
                  <div class="req-record-option__path req-record-option__path--with-status">
                    <span class="req-record-option__path-text">{{ recordSelectPrimaryLine(r) }}</span>
                    <span :class="recordStatusClass(r)">{{ recordStatusLabel(r) }}</span>
                  </div>
                  <div class="req-record-option__meta">
                    <span class="req-record-option__time">{{ r.created_at || '—' }}</span>
                    <span class="req-record-option__id">#{{ r.id }}</span>
                  </div>
                  <div v-if="recordSelectFileHint(r)" class="req-record-option__file">{{ recordSelectFileHint(r) }}</div>
                </div>
              </el-option>
            </el-select>
          </div>
          <div v-if="activeRecord" class="replica-record-meta">
            <div class="replica-record-meta__title">{{ displayFileTitle(activeRecord.file_name) }}</div>
            <div class="replica-record-meta__sub">上传时间：{{ activeRecord.created_at || '—' }}</div>
            <div class="replica-record-meta__sub">菜单路径：{{ breadcrumb(activeRecord.menu_structure) || '无' }}</div>
            <div class="replica-record-meta__tags">
              <span class="replica-record-tag" :class="{ 'is-done': recordStyleStageDone(activeRecord) }">样式</span>
              <span class="replica-record-tag" :class="{ 'is-done': !!String(activeRecord.analysis_content || '').trim() }">内容</span>
              <span class="replica-record-tag" :class="{ 'is-done': !!String(activeRecord.analysis_interaction || '').trim() }">交互</span>
              <span class="replica-record-tag" :class="{ 'is-done': !!isReplicaStageDone('data') }">数据</span>
            </div>
          </div>
        </div>
        <div class="replica-shell__preview">
          <div class="replica-preview-head">
            <div class="replica-label">需求缩略图</div>
            <span class="replica-preview-head__hint">高清预览</span>
          </div>
          <div class="replica-preview-box">
            <el-image
              v-if="previewImageUrl"
              :src="previewImageUrl"
              :alt="displayFileTitle(activeRecord?.file_name) || '需求'"
              class="replica-preview-img"
              fit="contain"
              :preview-src-list="[previewImageUrl]"
              preview-teleported
              @error="onPreviewError"
            />
            <div v-else class="replica-preview-empty">暂无需求</div>
          </div>
        </div>
      </div>
      <div class="replica-action-grid">
        <div class="replica-action-card" :class="replicaTopStepClass('style')">
          <el-button
            class="replica-action-btn"
            @click="generateStyleOnly"
            :disabled="replicaTopStepLocked.style || generating || historyLoading"
          >
            {{ generating ? '处理中…' : '启动样式分析' }}
          </el-button>
          <div class="replica-action-meta">{{ replicaTopStepStatus.style }}</div>
        </div>
        <div class="replica-action-card" :class="replicaTopStepClass('rest')">
          <el-button
            class="replica-action-btn"
            @click="generateRestByStyle"
            :disabled="replicaTopStepLocked.rest || generating || historyLoading"
          >
            {{ generating ? '处理中…' : '基于样式分析需求内容/交互/数据' }}
          </el-button>
          <div class="replica-action-meta">{{ replicaTopStepStatus.rest }}</div>
        </div>
        <template v-if="canVectorOps">
          <div class="replica-action-card" :class="replicaTopStepClass('overall')">
            <el-button
              class="replica-action-btn"
              @click="vectorPanelMode = 'analysis'; activeMainTab = 'vector'; analyzeVectorForCurrentRecord()"
              :disabled="replicaTopStepLocked.overall || vectorAnalyzing || generating || historyLoading"
            >
              {{ vectorAnalyzing ? '分析中…' : '总体分析' }}
            </el-button>
            <div class="replica-action-meta">{{ replicaTopStepStatus.overall }}</div>
          </div>
          <div class="replica-action-card" :class="replicaTopStepClass('output')">
            <el-button
              class="replica-action-btn"
              @click="onReplicaBuildVector"
              :disabled="replicaTopStepLocked.output || syncingVector || vectorAnalyzing || generating || historyLoading"
            >
              产出向量库
            </el-button>
            <div class="replica-action-meta">{{ replicaTopStepStatus.output }}</div>
          </div>
        </template>
      </div>
      <ReplicaFlowChart
        :stage-done-map="replicaStageDoneMap"
        :aggregation-ready="replicaAggregationReady"
        :can-run-overall-analyze="canRunOverallAnalyze"
        :can-build-vector-library="canBuildVectorLibrary"
        :has-overall-analysis="hasOverallAnalysis"
        :vector-built-for-current="vectorBuiltForCurrent"
        :stage-class-by-key="replicaStageClassByKey"
        :stage-status-label="replicaStageStatusLabel"
        :is-stage-node-disabled="isReplicaStageNodeDisabled"
        @stage-click="onReplicaStageClick"
        @overall-click="onReplicaOverallClick"
        @output-click="onReplicaOutputClick"
      />
      <div v-if="false" class="replica-flow-canvas">
        <div class="replica-flow-canvas__title">流程图预览（已提取到 ReplicaFlowChart）</div>
        <div class="replica-wireframe">
          <div class="replica-wireframe__inner">
          <svg class="replica-wireframe__lines" viewBox="0 0 1320 340" preserveAspectRatio="xMinYMin meet" aria-hidden="true">
            <defs>
              <marker id="replica-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M0 0 L10 5 L0 10 z" />
              </marker>
            </defs>

            <path
              id="rep-line-style-content"
              class="replica-wireframe__path replica-wireframe__path--pre"
              :class="{ 'is-ready': replicaStageDoneMap.style, 'is-locked': !replicaStageDoneMap.style }"
              d="M218 166 L264 166 L320 78"
            />
            <path
              id="rep-line-style-interaction"
              class="replica-wireframe__path replica-wireframe__path--pre"
              :class="{ 'is-ready': replicaStageDoneMap.style, 'is-locked': !replicaStageDoneMap.style }"
              d="M218 166 L272 166 L320 168"
            />
            <path
              id="rep-line-style-data"
              class="replica-wireframe__path replica-wireframe__path--pre"
              :class="{ 'is-ready': replicaStageDoneMap.style, 'is-locked': !replicaStageDoneMap.style }"
              d="M218 166 L264 166 L320 258"
            />
            <path
              id="rep-line-content-ai"
              class="replica-wireframe__path replica-wireframe__path--to-ai"
              :class="{ 'is-ready': replicaAggregationReady, 'is-locked': !replicaAggregationReady }"
              d="M540 78 L580 78 L620 168"
            />
            <path
              id="rep-line-interaction-ai"
              class="replica-wireframe__path replica-wireframe__path--to-ai"
              :class="{ 'is-ready': replicaAggregationReady, 'is-locked': !replicaAggregationReady }"
              d="M540 168 L580 168 L620 168"
            />
            <path
              id="rep-line-data-ai"
              class="replica-wireframe__path replica-wireframe__path--to-ai"
              :class="{ 'is-ready': replicaAggregationReady, 'is-locked': !replicaAggregationReady }"
              d="M540 258 L580 258 L620 168"
            />
            <path
              id="rep-line-hub-ai"
              class="replica-wireframe__path replica-wireframe__path--to-ai"
              :class="{ 'is-ready': replicaAggregationReady, 'is-locked': !replicaAggregationReady }"
              d="M716 168 L900 168"
            />
            <path
              id="rep-line-ai-output"
              class="replica-wireframe__path replica-wireframe__path--to-output"
              :class="{ 'is-ready': canBuildVectorLibrary, 'is-locked': !canBuildVectorLibrary }"
              d="M1120 168 L1160 168"
            />

            <text class="replica-wireframe__line-text">
              <textPath href="#rep-line-style-content" startOffset="40%">(基于样式/OCR)</textPath>
            </text>
            <text class="replica-wireframe__line-text">
              <textPath href="#rep-line-style-interaction" startOffset="38%">(基于样式/OCR)</textPath>
            </text>
            <text class="replica-wireframe__line-text">
              <textPath href="#rep-line-style-data" startOffset="40%">（功能与上下游）</textPath>
            </text>
          </svg>

          <div class="replica-aggregate-hub" :class="{ 'is-ready': replicaAggregationReady, 'is-locked': !replicaAggregationReady }">
            需求分析聚合
          </div>

          <button
            type="button"
            class="replica-flow-node replica-flow-node--style"
            :class="replicaStageClassByKey('style')"
            :disabled="isReplicaStageNodeDisabled('style')"
            @click="onReplicaStageClick('style')"
          >
            <span class="replica-flow-node__title">样式分析（OCR）</span>
            <span class="replica-flow-node__hint">样式列表</span>
            <span class="replica-flow-node__status">{{ replicaStageStatusLabel('style') }}</span>
          </button>

          <button
            type="button"
            class="replica-flow-node replica-flow-node--content"
            :class="replicaStageClassByKey('content')"
            :disabled="isReplicaStageNodeDisabled('content')"
            @click="onReplicaStageClick('content')"
          >
            <span class="replica-flow-node__title">需求内容分析</span>
            <span class="replica-flow-node__hint">文本输入</span>
            <span class="replica-flow-node__status">{{ replicaStageStatusLabel('content') }}</span>
          </button>

          <button
            type="button"
            class="replica-flow-node replica-flow-node--interaction"
            :class="replicaStageClassByKey('interaction')"
            :disabled="isReplicaStageNodeDisabled('interaction')"
            @click="onReplicaStageClick('interaction')"
          >
            <span class="replica-flow-node__title">交互分析</span>
            <span class="replica-flow-node__hint">文本输入</span>
            <span class="replica-flow-node__status">{{ replicaStageStatusLabel('interaction') }}</span>
          </button>

          <button
            type="button"
            class="replica-flow-node replica-flow-node--data"
            :class="replicaStageClassByKey('data')"
            :disabled="isReplicaStageNodeDisabled('data')"
            @click="onReplicaStageClick('data')"
          >
            <span class="replica-flow-node__title">数据分析</span>
            <span class="replica-flow-node__hint">文本输入</span>
            <span class="replica-flow-node__status">{{ replicaStageStatusLabel('data') }}</span>
          </button>

          <button
            type="button"
            class="replica-flow-node replica-flow-node--ai"
            :class="{ 'is-locked': !canRunOverallAnalyze && !hasOverallAnalysis, 'is-done': hasOverallAnalysis }"
            :disabled="!canRunOverallAnalyze"
            @click="activeMainTab = 'vector'"
          >
            <span class="replica-flow-node__title">AI需求分析产出向量库</span>
            <span class="replica-flow-node__hint">列表查询</span>
            <span class="replica-flow-node__status">{{ hasOverallAnalysis ? '已完成' : (canRunOverallAnalyze ? '可执行' : '待聚合完成') }}</span>
          </button>

          <button
            type="button"
            class="replica-flow-node replica-flow-node--output"
            :class="{ 'is-locked': !canBuildVectorLibrary && !vectorBuiltForCurrent, 'is-done': vectorBuiltForCurrent }"
            :disabled="!canBuildVectorLibrary"
            @click="vectorPanelMode = 'build'; activeMainTab = 'vector'"
          >
            <span class="replica-flow-node__title">产出向量库</span>
            <span class="replica-flow-node__hint">输出节点</span>
            <span class="replica-flow-node__status">{{ vectorBuiltForCurrent ? '已完成' : (canBuildVectorLibrary ? '可执行' : '待总体分析结果') }}</span>
          </button>
          </div>
        </div>
        <div class="replica-flow-note">需求内容分析/交互分析/数据分析三项完成后，才会解锁“需求分析聚合”并可进入 AI 需求分析节点。</div>
      </div>
      <div class="replica-hint">{{ resultStatusHint }}</div>
      <div
        v-if="replicaWorkflowLoading"
        class="replica-shell-loading-mask"
        role="status"
        aria-live="polite"
      >
        <div class="req-lib-vector-loading-chip">
          <span class="req-lib-vector-loading-dot" aria-hidden="true" />
          <span>{{ replicaWorkflowLoadingText }}</span>
        </div>
      </div>
    </div>

    <div v-if="!isReplicaMode" class="page-header">
      <h1>系统需求分析库</h1>
      <p>为需求生成：样式分析 / 需求内容分析 / 交互分析 / 数据分析（当前功能与上下游数据逻辑关系）。</p>
    </div>
    <div v-if="!isReplicaMode" class="card" style="padding: 12px; margin-bottom: 12px;">
      <div style="font-weight: 700; margin-bottom: 10px;">系统需求分析库</div>
      <div style="display:flex; gap:8px; flex-wrap:wrap;">
        <el-button :type="activeMainTab === 'pre' ? 'primary' : 'default'" @click="activeMainTab = 'pre'">
          系统元素预识别
        </el-button>
        <el-button :type="activeMainTab === 'vector' ? 'primary' : 'default'" @click="vectorPanelMode = 'analysis'; activeMainTab = 'vector'">
          建库内容与用例输入
        </el-button>
      </div>
    </div>

    <div v-if="historyLoading && activeMainTab === 'pre' && !isReplicaMode" class="req-lib-loading-banner" role="status" aria-live="polite">
      <span class="req-lib-spinner" aria-hidden="true" />
      <span>正在从服务器加载需求历史记录…</span>
    </div>

    <div v-if="activeMainTab === 'pre' && !isReplicaMode" class="card" style="padding: 12px;" :class="{ 'req-lib-card--dim': historyLoading }">
      <div style="display:flex; gap:12px; flex-wrap:wrap; align-items:center; justify-content: space-between;">
        <div style="display:flex; gap:10px; flex-wrap:wrap; align-items:center;">
          <el-button type="primary" @click="generateStyleOnly" :disabled="generating || historyLoading || !selectedId">
            {{ generating ? '生成中…' : '1) 生成样式分析（OCR）' }}
          </el-button>
          <el-button @click="generateRestByStyle" :disabled="generating || historyLoading || !selectedId || !styleReady">
            {{ generating ? '生成中…' : '2) 基于样式生成内容/交互/数据' }}
          </el-button>
          <span style="color:#666; font-size:13px;">
            {{ resultStatusHint }}
          </span>
        </div>
        <el-button @click="fetchHistory" :disabled="generating || historyLoading">
          {{ historyLoading ? '加载中…' : '刷新' }}
        </el-button>
      </div>

      <div style="display:flex; gap:8px; flex-wrap:wrap; margin-top: 12px;">
        <el-button
          :type="activeCategory === 'style' ? 'primary' : 'default'"
          :disabled="historyLoading"
          @click="activeCategory = 'style'"
        >
          样式分析（OCR）
        </el-button>
        <el-button
          :type="activeCategory === 'content' ? 'primary' : 'default'"
          :disabled="historyLoading"
          @click="activeCategory = 'content'"
        >
          需求内容分析（基于样式/OCR）
        </el-button>
        <el-button
          :type="activeCategory === 'interaction' ? 'primary' : 'default'"
          :disabled="historyLoading"
          @click="activeCategory = 'interaction'"
        >
          交互分析（基于样式/OCR）
        </el-button>
        <el-button
          :type="activeCategory === 'data' ? 'primary' : 'default'"
          :disabled="historyLoading"
          @click="activeCategory = 'data'"
        >
          数据分析（功能与上下游）
        </el-button>
      </div>

      <div class="form-group req-record-picker-wrap" style="margin-top: 12px;">
        <label>选择需求记录</label>
        <el-select
          v-model="selectedId"
          class="req-record-picker"
          filterable
          clearable
          :fit-input-width="false"
          :title="recordPickerTitleAttr"
          placeholder="搜索路径、文件名、时间、ID 或状态（未完成/进行中/已完成）…"
          :disabled="recordPickerDisabledDefault"
          :filter-method="onRecordSelectFilter"
          popper-class="req-record-picker-dropdown"
          teleported
          style="width: 100%; max-width: 960px;"
          @visible-change="onRecordPickerVisible"
        >
          <template #empty>
            <div class="req-record-picker-empty">{{ historyLoading ? '加载中…' : '暂无需求记录' }}</div>
          </template>
          <el-option
            v-for="r in recordsForSelectDropdown"
            :key="r.id"
            :label="recordSelectDisplayLabel(r)"
            :value="String(r.id)"
          >
            <div class="req-record-option">
              <div class="req-record-option__path req-record-option__path--with-status">
                <span class="req-record-option__path-text">{{ recordSelectPrimaryLine(r) }}</span>
                <span :class="recordStatusClass(r)">{{ recordStatusLabel(r) }}</span>
              </div>
              <div class="req-record-option__meta">
                <span class="req-record-option__time">{{ r.created_at || '—' }}</span>
                <span class="req-record-option__id">#{{ r.id }}</span>
              </div>
              <div v-if="recordSelectFileHint(r)" class="req-record-option__file">{{ recordSelectFileHint(r) }}</div>
            </div>
          </el-option>
        </el-select>
      </div>
    </div>

    <div v-if="activeMainTab === 'pre'" class="card req-lib-detail-card" style="margin-top: 12px; padding: 12px;" :class="{ 'req-lib-card--dim': historyLoading }">
      <div class="req-lib-detail-shell">
        <div
          v-if="recordDetailLoading"
          class="req-lib-detail-overlay"
          role="status"
          aria-live="polite"
        >
          <div class="req-lib-detail-spinner" aria-hidden="true">
            <span class="req-lib-detail-spinner__arc req-lib-detail-spinner__arc--outer" />
            <span class="req-lib-detail-spinner__arc req-lib-detail-spinner__arc--inner" />
          </div>
          <span class="req-lib-detail-overlay-caption">正在加载需求内容…</span>
        </div>
        <div
          v-if="detailGeneratingLoading"
          class="req-lib-generate-overlay"
          role="status"
          aria-live="polite"
        >
          <div class="req-lib-generate-panel">
            <div class="req-lib-generate-head">
              <div class="req-lib-generate-spinner" aria-hidden="true">
                <span class="req-lib-generate-spinner__ring req-lib-generate-spinner__ring--outer" />
                <span class="req-lib-generate-spinner__ring req-lib-generate-spinner__ring--inner" />
              </div>
              <div>
                <div class="req-lib-generate-title">AI 需求分析正在执行</div>
                <div class="req-lib-generate-subtitle">{{ detailGeneratingPhaseText || '准备中…' }}</div>
              </div>
            </div>
            <div class="req-lib-generate-log-wrap">
              <div v-if="detailGeneratingLogs.length === 0" class="req-lib-generate-log-empty">正在等待服务端返回过程日志…</div>
              <div v-for="(line, idx) in detailGeneratingLogs" :key="`gen-${idx}`" class="req-lib-generate-log-line">{{ line }}</div>
            </div>
          </div>
        </div>
        <div class="req-lib-detail-body" :class="{ 'req-lib-detail-body--dim': recordDetailLoading || detailGeneratingLoading }">
      <div v-if="activeRecord" class="record-top">
        <div class="record-top-main">
          <div style="min-width: 200px; flex: 1;">
            <div style="font-weight: 700; font-size: 14px;">{{ displayFileTitle(activeRecord.file_name) }}</div>
            <div style="color:#666; margin-top: 4px; font-size: 12px;">
              菜单：{{ breadcrumb(activeRecord.menu_structure) || '无' }}
            </div>
            <div style="color:#666; margin-top: 4px; font-size: 12px;">
              最近生成：{{ activeRecord.analysis_generated_at || '—' }}
            </div>
          </div>
          <div style="flex: 1; min-width: 180px;">
            <div style="color:#666; font-size:12px;">快捷信息</div>
            <div style="margin-top: 6px; display:flex; gap:8px; flex-wrap:wrap;">
              <span class="tag" v-if="recordStyleStageDone(activeRecord)">样式已生成</span>
              <span class="tag" v-if="activeRecord.analysis_content && activeRecord.analysis_content.trim()">内容已生成</span>
              <span class="tag" v-if="activeRecord.analysis_interaction && activeRecord.analysis_interaction.trim()">交互已生成</span>
              <span class="tag" v-if="activeRecord.analysis_data && (Array.isArray(activeRecord.analysis_data) || Object.keys(activeRecord.analysis_data||{}).length)">数据已生成</span>
            </div>
          </div>
        </div>
        <div v-if="previewImageUrl && !isReplicaMode" class="screenshot-preview-wrap">
          <div class="screenshot-preview-label">需求预览</div>
          <div class="screenshot-preview-inner">
            <el-image
              :src="previewImageUrl"
              :alt="displayFileTitle(activeRecord.file_name) || '需求'"
              class="screenshot-preview-img"
              fit="contain"
              :preview-src-list="[previewImageUrl]"
              preview-teleported
              @error="onPreviewError"
            />
          </div>
        </div>
      </div>

      <div v-else style="color:#999; padding: 14px;">
        请先选择需求记录。
      </div>

      <div v-if="activeRecord" style="margin-top: 12px;">
        <div style="color:#666; font-size:12px; margin-bottom: 8px;">
          当前标签：{{ categoryLabel }}
        </div>

        <!-- 样式分析：表格（元素列承载 OCR 原文；属性为单选下拉） -->
        <div v-if="activeCategory === 'style'" class="panel-block panel-block--style">
          <p class="panel-desc">“元素”列放置 OCR/生成得到的原始需求文本；“属性”为界面类型分类；“补充需求”可填写数据层联动、规则等说明。</p>
          <div class="toolbar">
            <el-button @click="addStyleRow">新增行</el-button>
            <div class="custom-attr">
              <input v-model="newAttrOption" class="input input-sm" placeholder="自定义属性（加入下拉）" @keydown.enter.prevent="addCustomAttrOption" />
              <el-button @click="addCustomAttrOption">添加</el-button>
            </div>
          </div>
          <div class="table-wrap table-wrap--rounded">
            <table class="style-table">
              <thead>
                <tr>
                  <th class="col-idx">序号</th>
                  <th class="col-el">元素（OCR 原文 / 原有需求）</th>
                  <th class="col-attr">属性</th>
                  <th class="col-req">补充需求</th>
                  <th class="col-act">操作</th>
                </tr>
              </thead>
              <tbody :key="`style-tbody-${selectedId || 'none'}`">
                <tr v-for="(row, idx) in styleRows" :key="`s-${selectedId || 'x'}-r${idx}`">
                  <td class="td-index">{{ idx + 1 }}</td>
                  <td class="td-el">
                    <input
                      v-model="row.element"
                      type="text"
                      class="input input-el-compact"
                      placeholder="OCR 原文"
                      maxlength="2048"
                    />
                  </td>
                  <td>
                    <select v-model="row.attribute" class="select-attr">
                      <option v-for="opt in allAttributeOptions" :key="opt" :value="opt">{{ opt }}</option>
                    </select>
                  </td>
                  <td>
                    <textarea v-model="row.requirement" class="textarea-cell" rows="4" placeholder="补充说明（可选）"></textarea>
                  </td>
                  <td>
                    <el-button size="small" :disabled="styleSaving" @click="removeStyleRow(idx)">删除</el-button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="save-bar save-bar--auto">
            <span v-if="styleSaveStatus" class="style-save-status">{{ styleSaveStatus }}</span>
            <el-button :disabled="styleSaving" @click="saveStyleTableManual">
              立即保存
            </el-button>
          </div>
        </div>

        <!-- 需求内容 / 交互：可编辑文本 -->
        <div v-else-if="activeCategory === 'content' || activeCategory === 'interaction'" class="panel-block">
          <textarea
            :key="`draft-${selectedId || ''}-${activeCategory}`"
            v-model="draftText"
            class="textarea-block"
            :placeholder="activeCategory === 'content' ? '需求内容分析…' : '交互分析…'"
          />
          <div class="save-bar">
            <el-button type="primary" :disabled="saving" @click="saveTextCategory">
              {{ saving ? '保存中…' : '保存' }}
            </el-button>
          </div>
        </div>

        <!-- 数据分析：当前功能 + 上下游数据逻辑关系，写入后与样式、内容、交互一并进入需求向量库 -->
        <div v-else class="panel-block panel-block--data">
          <p class="panel-desc">
            数据分析描述当前功能与上下游数据逻辑关系（输入来源、处理规则、输出影响），以文本形式保存。
          </p>
          <textarea
            :key="`data-${selectedId || ''}`"
            v-model="draftDataText"
            class="textarea-block"
            placeholder="文本数据分析（当前功能、上游依赖、下游影响、逻辑关系）"
          />
          <div class="save-bar save-bar--split">
            <el-button type="primary" :disabled="saving" @click="saveDataCategory">
              {{ saving ? '保存中…' : '保存数据分析' }}
            </el-button>
          </div>
        </div>
      </div>
        </div>
      </div>
    </div>

    <div v-if="activeMainTab === 'vector'" class="card" style="padding: 12px;">
      <div class="panel-block panel-block--data req-lib-vector-shell">
        <div v-if="activeRecord" class="record-top" style="margin-top: 10px;">
          <div class="record-top-main">
            <div style="min-width: 220px; flex: 1;">
              <div style="font-weight: 700; font-size: 14px;">{{ displayFileTitle(activeRecord.file_name) }}</div>
              <div style="color:#666; margin-top: 4px; font-size: 12px;">
                菜单：{{ breadcrumb(activeRecord.menu_structure) || '无' }}
              </div>
            </div>
          </div>
          <div v-if="previewImageUrl && !isReplicaMode" class="screenshot-preview-wrap">
            <div class="screenshot-preview-label">需求预览</div>
            <div class="screenshot-preview-inner">
              <el-image
                :src="previewImageUrl"
                :alt="displayFileTitle(activeRecord.file_name) || '需求'"
                class="screenshot-preview-img"
                fit="contain"
                :preview-src-list="[previewImageUrl]"
                preview-teleported
                @error="onPreviewError"
              />
            </div>
          </div>
        </div>
        <div class="form-group" style="margin-top: 12px;">
          <label>{{ vectorPanelHeadingText }}</label>
          <div style="margin-top: 6px; color:#667085; font-size: 12px; line-height: 1.6;">
            {{ vectorPanelDescriptionText }}
          </div>
          <div
            :style="{
              marginTop: '8px',
              display: 'inline-flex',
              alignItems: 'center',
              padding: '4px 10px',
              borderRadius: '999px',
              fontSize: '12px',
              color: vectorPanelMode === 'build' ? '#8a3200' : '#0b5cad',
              background: vectorPanelMode === 'build' ? '#fff4e8' : '#eef6ff',
              border: vectorPanelMode === 'build' ? '1px solid #ffd6ae' : '1px solid #bfdbfe',
            }"
          >
            {{ vectorPanelMode === 'build' ? '向量建库联动视角' : '测试用例分析视角' }}
          </div>
          <textarea
            :key="`vec-${selectedId || ''}-${vectorPanelMode}`"
            :value="vectorPanelMode === 'build' ? vectorBuildText : vectorAnalysisResult"
            @input="vectorPanelMode === 'build' ? (vectorBuildText = $event.target.value) : (vectorAnalysisResult = $event.target.value)"
            class="textarea-block"
            :disabled="vectorAnalyzing || syncingVector"
            :placeholder="vectorPanelPlaceholderText"
          />
          <div class="save-bar" style="margin-top: 8px; justify-content: flex-start;">
            <el-button :disabled="!selectedId || vectorSaving || vectorAnalyzing || syncingVector" @click="saveVectorContent(vectorPanelMode)">
              {{ vectorSaving ? '保存中…' : '保存当前建库内容' }}
            </el-button>
          </div>
        </div>
        <div v-if="vectorSyncHint" class="vector-sync-hint" style="margin-top: 10px;">{{ vectorSyncHint }}</div>
        <div v-if="vectorPanelLoading" class="req-lib-vector-loading-mask" role="status" aria-live="polite">
          <div class="req-lib-vector-loading-chip">
            <span class="req-lib-vector-loading-dot" aria-hidden="true" />
            <span>{{ vectorPanelLoadingText }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
import { useSystemStore } from '../stores/system';
import { useAuthStore } from '../stores/auth';
import { sseUrlWithAuth, streamSse } from '../api/http';
import { useUiDialog } from '../composables/useUiDialog';
import { useStyleTable } from '../composables/useStyleTable';
import { useVectorAnalysis } from '../composables/useVectorAnalysis';
import { getHistoryDetail, listHistory, updateHistory } from '../api/history';
import { emitHistoryUpdated } from '../composables/useHistorySync';
import ReplicaFlowChart from './ReplicaFlowChart.vue';

const props = defineProps({
  mode: {
    type: String,
    default: 'default',
  },
});

const systemStore = useSystemStore();
const authStore = useAuthStore();
const canVectorOps = computed(() => authStore.can('action.requirement.vector_build'));

const { alertDialog } = useUiDialog();
const isReplicaMode = computed(() => props.mode === 'replica');

const records = ref([]);
const selectedId = ref('');
const activeMainTab = ref('pre');
const activeCategory = ref('style');
const vectorPanelMode = ref('analysis');
const generating = ref(false);
const historyLoading = ref(false);
const recordDetailLoading = ref(false);
const detailGeneratingLoading = ref(false);
const detailGeneratingPhaseText = ref('');
const detailGeneratingLogs = ref([]);

const draftText = ref('');
const draftDataText = ref('');
const saving = ref(false);

const activeRecord = computed(() => {
  const id = Number(selectedId.value);
  if (!id) return null;
  return records.value.find((r) => Number(r.id) === id) || null;
});

const vectorPanelHeading = computed(() => {
  if (vectorPanelMode.value === 'build') return '当前建库联动文本';
  return '当前AI需求分析总结';
});

const vectorPanelDescription = computed(() => {
  if (vectorPanelMode.value === 'build') {
    return '这里展示的是产出向量库专用的建库联动文本。';
  }
  return '这里展示的是用于测试用例生成的AI需求分析总结。';
});

const vectorPanelPlaceholder = computed(() => {
  if (vectorPanelMode.value === 'build') {
    return '这里是向量库建库联动文本，可补充跨页面关联、触发动作和上下游依赖。';
  }
  return '这里是AI需求分析总结，可补充主流程、校验规则和异常分支。';
});

const vectorPanelHeadingText = computed(() => (
  vectorPanelMode.value === 'build' ? '当前建库联动文本' : '当前AI需求分析总结'
));

const vectorPanelDescriptionText = computed(() => {
  if (vectorPanelMode.value === 'build') {
    return '这里展示的是“产出向量库”专用的需求联动文本，用于跨页面索引、上下游关系检索和向量建库。';
  }
  return '这里展示的是对样式分析、需求内容分析、交互分析、数据分析的总结结果，主要服务测试用例生成。';
});

const vectorPanelPlaceholderText = computed(() => {
  if (vectorPanelMode.value === 'build') {
    return '这里是当前页面用于向量建库的需求联动文本，可补充上下游页面、触发动作、联动结果、依赖条件和检索关键词。';
  }
  return '这里是当前页面用于测试用例设计的分析总结，可补充主流程、字段规则、异常分支、结果校验和测试重点。';
});

const {
  styleRows, styleSaving, styleTableHydrating, styleSaveStatus,
  allAttributeOptions, newAttrOption, extraAttrOptions,
  loadStyleRowsFromRecord, flushStyleToHistoryId, clearStyleAutoSaveDebounce, persistStyleTable,
  addStyleRow, removeStyleRow, addCustomAttrOption, saveStyleTableManual,
  DEFAULT_ATTR_OPTIONS,
} = useStyleTable({ activeRecord, activeCategory, records, selectedId, alertDialog });

const {
  vectorAnalyzing, vectorAnalysisResult, vectorBuildText, vectorBuildResult, syncingVector, vectorSyncHint, vectorSaving,
  analyzeVectorForCurrentRecord, ensureVectorBuildTextForCurrentRecord, syncVectorForCurrentRecord, saveVectorContent,
} = useVectorAnalysis({ activeRecord, records, alertDialog, systemStore });

const categoryLabel = computed(() => {
  if (activeCategory.value === 'style') return '样式分析（OCR）';
  if (activeCategory.value === 'content') return '需求内容分析（基于样式/OCR）';
  if (activeCategory.value === 'interaction') return '交互分析（基于样式/OCR）';
  if (activeCategory.value === 'data') return '数据分析（当前功能与上下游逻辑）';
  return '';
});

function isReplicaStageDone(key) {
  const rec = activeRecord.value;
  if (!rec) return false;
  // 与下拉状态、styleReady 一致：样式可仅存于 analysis_style_table，不能只看 analysis_style 文本
  if (key === 'style') return recordStyleStageDone(rec);
  if (key === 'content') return !!String(rec.analysis_content || '').trim();
  if (key === 'interaction') return !!String(rec.analysis_interaction || '').trim();
  if (key === 'data') {
    if (typeof rec.analysis_data === 'string') return !!rec.analysis_data.trim();
    if (Array.isArray(rec.analysis_data)) return rec.analysis_data.length > 0;
    if (rec.analysis_data && typeof rec.analysis_data === 'object') return Object.keys(rec.analysis_data).length > 0;
    return false;
  }
  return false;
}

const replicaStageDoneMap = computed(() => ({
  style: isReplicaStageDone('style'),
  content: isReplicaStageDone('content'),
  interaction: isReplicaStageDone('interaction'),
  data: isReplicaStageDone('data'),
}));

const replicaStageLockedMap = computed(() => {
  const done = replicaStageDoneMap.value;
  return {
    style: false,
    content: !done.style,
    interaction: !done.content,
    data: !done.interaction,
  };
});

const replicaAggregationReady = computed(() => {
  const done = replicaStageDoneMap.value;
  return done.content && done.interaction && done.data;
});

const hasOverallAnalysis = computed(() => !!String(activeRecord.value?.analysis || vectorAnalysisResult.value || '').trim());
const vectorBuiltForCurrent = computed(() => !!String(activeRecord.value?.vector_built_at || '').trim());

/** 流程区状态文案：随当前记录与分析进度变化，避免已生成内容仍显示「未生成」 */
const resultStatusHint = computed(() => {
  if (generating.value) return '正在生成，请稍候…';
  const rec = activeRecord.value;
  if (!rec) return '请先选择需求记录';
  const m = replicaStageDoneMap.value;
  if (m.style && m.content && m.interaction && m.data) {
    const has = !!String(rec.analysis || vectorAnalysisResult.value || '').trim();
    if (has) {
      if (String(rec.vector_built_at || '').trim()) return '向量库已生成';
      return 'AI 需求分析已完成';
    }
    return '前置分析已完成，可执行总体分析';
  }
  if (m.style) return '样式分析已完成，可继续生成内容/交互/数据';
  return '请先完成样式分析';
});

const vectorPanelLoading = computed(() => vectorAnalyzing.value || syncingVector.value);
const vectorPanelLoadingText = computed(() => {
  if (syncingVector.value) return '正在构建向量库，请稍候…';
  return 'AI 需求分析执行中，请稍候…';
});

const replicaWorkflowLoading = computed(
  () =>
    isReplicaMode.value
    && (generating.value || vectorAnalyzing.value || syncingVector.value || recordDetailLoading.value),
);
const replicaWorkflowLoadingText = computed(() => {
  if (generating.value) return '需求分析生成中，请稍候…';
  if (vectorAnalyzing.value) return 'AI 需求分析执行中，请稍候…';
  if (syncingVector.value) return '正在构建向量库，请稍候…';
  return '正在加载…';
});

const canRunOverallAnalyze = computed(() => {
  return canVectorOps.value
    && !!selectedId.value
    && !vectorAnalyzing.value
    && replicaAggregationReady.value;
});

const canBuildVectorLibrary = computed(() => {
  return canVectorOps.value
    && !!selectedId.value
    && !syncingVector.value
    && !vectorAnalyzing.value
    && replicaAggregationReady.value
    && hasOverallAnalysis.value;
});

function onReplicaOverallClick() {
  if (!canVectorOps.value) return;
  vectorPanelMode.value = 'analysis';
  activeMainTab.value = 'vector';
}

function onReplicaOutputClick() {
  if (!canVectorOps.value) return;
  vectorPanelMode.value = 'build';
  activeMainTab.value = 'vector';
}

async function onReplicaBuildVector() {
  if (!canVectorOps.value) return;
  if (!canBuildVectorLibrary.value) {
    await alertDialog('当前记录尚未满足建库前置条件：请先完成内容/交互/数据三项分析，并执行「总体分析」后再产出向量库。');
    return;
  }
  vectorPanelMode.value = 'build';
  activeMainTab.value = 'vector';
  await syncVectorForCurrentRecord({ silent: false });
}

const replicaTopStepLocked = computed(() => ({
  style: !selectedId.value,
  rest: !selectedId.value || !replicaStageDoneMap.value.style,
  overall: !selectedId.value || !replicaAggregationReady.value,
  output: !selectedId.value || !replicaAggregationReady.value || !hasOverallAnalysis.value,
}));

const replicaTopStepDone = computed(() => ({
  style: replicaStageDoneMap.value.style,
  rest: replicaAggregationReady.value,
  overall: hasOverallAnalysis.value,
  output: vectorBuiltForCurrent.value,
}));

const replicaTopStepStatus = computed(() => ({
  style: replicaTopStepDone.value.style ? '已完成' : (replicaTopStepLocked.value.style ? '请先选择记录' : '待执行'),
  rest: replicaTopStepDone.value.rest ? '已完成' : (replicaTopStepLocked.value.rest ? '待样式完成' : '待执行'),
  overall: replicaTopStepDone.value.overall ? '已完成' : (replicaTopStepLocked.value.overall ? '待三项分析完成' : '待执行'),
  output: replicaTopStepDone.value.output
    ? '已完成'
    : (replicaTopStepLocked.value.output ? '待总体分析完成' : '待执行'),
}));

const replicaStages = computed(() => {
  const done = replicaStageDoneMap.value;
  const locked = replicaStageLockedMap.value;
  return [
    {
      key: 'style',
      title: '样式分析',
      hint: '基于样式/OCR',
      status: done.style ? '已完成' : '未完成',
      locked: locked.style,
    },
    {
      key: 'content',
      title: '需求内容分析',
      hint: '原有需求文本输入',
      status: done.content ? '已完成' : (locked.content ? '待前置完成' : '未完成'),
      locked: locked.content,
    },
    {
      key: 'interaction',
      title: '交互分析',
      hint: '原有交互分析文本输入',
      status: done.interaction ? '已完成' : (locked.interaction ? '待前置完成' : '未完成'),
      locked: locked.interaction,
    },
    {
      key: 'data',
      title: '数据分析',
      hint: '原有数据分析文本输入',
      status: done.data ? '已完成' : (locked.data ? '待前置完成' : '未完成'),
      locked: locked.data,
    },
  ];
});

const replicaStageByKey = computed(() => {
  const map = {};
  for (const s of replicaStages.value) {
    map[s.key] = s;
  }
  return map;
});

function getReplicaStageByKey(key) {
  return replicaStageByKey.value[key] || {
    key,
    title: '',
    hint: '',
    status: '未完成',
    locked: true,
  };
}

function replicaStageClassByKey(key) {
  return replicaStageClass(getReplicaStageByKey(key));
}

function replicaStageStatusLabel(key) {
  const stage = getReplicaStageByKey(key);
  if (stage.locked) return '待前置完成';
  return stage.status;
}

function isReplicaStageNodeDisabled(key) {
  const stage = getReplicaStageByKey(key);
  return stage.locked || generating.value || historyLoading.value || recordDetailLoading.value;
}

function onReplicaStageClick(key) {
  if (isReplicaStageNodeDisabled(key)) return;
  activeMainTab.value = 'pre';
  activeCategory.value = key;
}

function replicaTopStepClass(key) {
  return {
    'is-locked': !!replicaTopStepLocked.value[key],
    'is-done': !!replicaTopStepDone.value[key],
  };
}

// goToVectorQuery 已移除：此处要求只展示已生成的向量建库结果。

function replicaStageClass(stage) {
  const classes = [];
  if (activeCategory.value === stage.key) classes.push('is-active');
  if (stage.locked) classes.push('is-locked');
  if (stage.status === '已完成') classes.push('is-done');
  else classes.push('is-pending');
  return classes;
}

const fetchHistory = async () => {
  historyLoading.value = true;
  try {
    const params = {};
    if (systemStore.systemId) params.system_id = systemStore.systemId;
    const data = await listHistory(params);
    records.value = Array.isArray(data) ? data : [];
    if (!selectedId.value && records.value.length) selectedId.value = String(records.value[0].id);
  } catch (e) {
    console.error(e);
    await alertDialog('刷新失败');
  } finally {
    historyLoading.value = false;
  }
};

const styleReady = computed(() => {
  const rec = activeRecord.value;
  if (!rec) return false;
  return recordStyleStageDone(rec);
});

const generateByStage = async (stage) => {
  const currentId = Number(selectedId.value);
  if (!Number.isFinite(currentId) || currentId <= 0) {
    await alertDialog('请先选择一条需求记录');
    return;
  }
  if (stage === 'rest' && !styleReady.value) {
    await alertDialog('请先完成样式分析（OCR），并保存样式后再生成其余分析');
    return;
  }
  generating.value = true;
  detailGeneratingLoading.value = true;
  detailGeneratingPhaseText.value = stage === 'style'
    ? `准备生成样式分析（ID=${currentId}）…`
    : `准备基于样式生成内容/交互/数据（ID=${currentId}）…`;
  detailGeneratingLogs.value = [];
  const pushDetailGeneratingLog = (text) => {
    const s = String(text || '').trim();
    if (!s) return;
    detailGeneratingLogs.value.push(s);
    if (detailGeneratingLogs.value.length > 120) {
      detailGeneratingLogs.value.splice(0, detailGeneratingLogs.value.length - 120);
    }
  };
  try {
    pushDetailGeneratingLog(
      stage === 'style'
        ? `开始样式分析（ID=${currentId}）`
        : `开始基于样式生成内容/交互/数据（ID=${currentId}）`
    );

    let sseUrl = `/api/requirement-analysis/generate/sse?force=1&history_id=${currentId}&stage=${encodeURIComponent(stage)}`;
    if (systemStore.systemId) sseUrl += `&system_id=${systemStore.systemId}`;
    sseUrl = sseUrlWithAuth(sseUrl);

    /** 使用 fetch+流式解析替代 EventSource：避免连接关闭时 onerror 与 done 竞态导致未刷新列表，且统一 UTF-8 解码 */
    let donePayload = null;
    await streamSse(sseUrl, {
      progress: (d) => {
        try {
          const st = d.stage || '';
          const hid = d.history_id ?? '';
          detailGeneratingPhaseText.value = `生成进度：${hid !== '' && hid != null ? `[${hid}] ` : ''}${st}`;
        } catch {
          // ignore
        }
      },
      log: (d) => {
        try {
          const hid = d.history_id ? `[${d.history_id}] ` : '';
          if (d.msg) pushDetailGeneratingLog(hid + d.msg);
          if (d.previews && typeof d.previews === 'object') {
            const p = d.previews;
            if (p.analysis_style) pushDetailGeneratingLog(`样式预览：${p.analysis_style}`);
            if (p.analysis_content) pushDetailGeneratingLog(`内容预览：${p.analysis_content}`);
            if (p.analysis_interaction) pushDetailGeneratingLog(`交互预览：${p.analysis_interaction}`);
          }
        } catch {
          // ignore
        }
      },
      done: (d) => {
        donePayload = d && typeof d === 'object' ? d : null;
      },
    });

    if (!donePayload) {
      throw new Error('服务端未返回完成事件（done），请刷新页面或点击「刷新」确认列表是否已更新。');
    }
    const d = donePayload;
    pushDetailGeneratingLog(`完成：generated=${d.generated ?? 0}/${d.total ?? 0}`);
    if (Array.isArray(d.errors) && d.errors.length) {
      const err0 = d.errors[0];
      const em = err0 && typeof err0 === 'object' ? String(err0.error || '') : String(err0 || '');
      if (em.trim()) pushDetailGeneratingLog(`服务端提示：${em.trim()}`);
    }
    if (stage === 'style') {
      activeCategory.value = 'style';
    } else {
      activeCategory.value = 'content';
    }
    await fetchHistory();
    emitHistoryUpdated();
    const refreshed = records.value.find((r) => Number(r.id) === currentId) || null;
    if (refreshed) {
      styleTableHydrating.value = true;
      loadStyleRowsFromRecord(refreshed);
      if (activeCategory.value === 'content') draftText.value = refreshed.analysis_content || '';
      else if (activeCategory.value === 'interaction') draftText.value = refreshed.analysis_interaction || '';
      else if (activeCategory.value === 'data') {
        const ad = refreshed.analysis_data;
        draftDataText.value = typeof ad === 'string' ? ad : (ad ? JSON.stringify(ad, null, 2) : '');
      }
      vectorAnalysisResult.value = String(refreshed.analysis || '').trim();
      await nextTick();
      styleTableHydrating.value = false;
    }
  } catch (e) {
    console.error(e);
    pushDetailGeneratingLog(`生成失败：${e.message || e}`);
    await alertDialog(`生成失败：${e.message || e}`);
  } finally {
    detailGeneratingPhaseText.value = '';
    detailGeneratingLoading.value = false;
    generating.value = false;
  }
};

const generateStyleOnly = async () => {
  await generateByStage('style');
};

const generateRestByStyle = async () => {
  const rec = activeRecord.value;
  if (rec && activeCategory.value === 'style') {
    await persistStyleTable(true);
  }
  await generateByStage('rest');
};

const previewImageUrl = computed(() => {
  const r = activeRecord.value;
  if (!r) return '';
  const u = typeof r.file_url === 'string' ? r.file_url.trim() : '';
  return u || '';
});

function onPreviewError(ev) {
  const el = ev?.target;
  if (el && el.style) el.style.display = 'none';
}

const breadcrumb = (menuStructure) => {
  return (Array.isArray(menuStructure) ? menuStructure : []).map((x) => x.name).filter(Boolean).join(' / ');
};

/** 列表/卡片标题：去掉常见图片扩展名，避免整段文件名当作标题展示 */
function displayFileTitle(name) {
  const s = String(name || '').trim();
  if (!s) return '';
  return s.replace(/\.(png|jpe?g|gif|webp|bmp|svg)$/i, '');
}

/** 单条记录：样式阶段是否完成（与 styleReady / 流程锁定一致） */
function recordStyleStageDone(r) {
  if (!r || typeof r !== 'object') return false;
  const table = r.analysis_style_table;
  if (Array.isArray(table) && table.some((row) => String(row?.element || '').trim() || String(row?.requirement || '').trim())) {
    return true;
  }
  return !!String(r.analysis_style || '').trim();
}

function recordDataStageDone(r) {
  if (!r || typeof r !== 'object') return false;
  const ad = r.analysis_data;
  if (typeof ad === 'string') return !!ad.trim();
  if (Array.isArray(ad)) return ad.length > 0;
  if (ad && typeof ad === 'object') return Object.keys(ad).length > 0;
  return false;
}

/**
 * 下拉列表状态：预识别四步（样式 → 内容 / 交互 / 数据）
 * - 未完成：样式未完成
 * - 进行中：样式已完成，但内容/交互/数据未全部完成
 * - 已完成：四步均有实质内容
 */
function requirementRecordListStatus(r) {
  if (!recordStyleStageDone(r)) {
    return { key: 'pending', label: '未完成' };
  }
  const contentOk = !!String(r.analysis_content || '').trim();
  const interactionOk = !!String(r.analysis_interaction || '').trim();
  const dataOk = recordDataStageDone(r);
  if (contentOk && interactionOk && dataOk) {
    return { key: 'done', label: '已完成' };
  }
  return { key: 'progress', label: '进行中' };
}

function recordStatusLabel(r) {
  return requirementRecordListStatus(r).label;
}

function recordStatusClass(r) {
  const k = requirementRecordListStatus(r).key;
  if (k === 'done') return 'req-record-status is-done';
  if (k === 'progress') return 'req-record-status is-progress';
  return 'req-record-status is-pending';
}

const recordSelectFilter = ref('');

const recordsSortedForPicker = computed(() => {
  const list = Array.isArray(records.value) ? [...records.value] : [];
  list.sort((a, b) => String(b.created_at || '').localeCompare(String(a.created_at || '')));
  return list;
});

const recordsForSelectDropdown = computed(() => {
  const q = recordSelectFilter.value.trim().toLowerCase();
  const list = recordsSortedForPicker.value;
  if (!q) return list;
  return list.filter((r) => {
    const path = breadcrumb(r.menu_structure);
    const title = displayFileTitle(r.file_name);
    const st = requirementRecordListStatus(r);
    const hay = [
      String(r.id),
      String(r.file_name || ''),
      String(r.created_at || ''),
      path,
      title,
      st.label,
      st.key,
    ]
      .join('\u0000')
      .toLowerCase();
    return hay.includes(q);
  });
});

function onRecordSelectFilter(query) {
  recordSelectFilter.value = query == null ? '' : String(query);
}

function onRecordPickerVisible(visible) {
  if (visible) recordSelectFilter.value = '';
}

const recordPickerDisabledReplica = computed(
  () => historyLoading.value || generating.value || vectorAnalyzing.value,
);
const recordPickerDisabledDefault = computed(() => historyLoading.value);

function recordSelectPrimaryLine(r) {
  const path = breadcrumb(r.menu_structure);
  if (path) return path;
  return displayFileTitle(r.file_name) || `记录 #${r.id}`;
}

/** 收起时输入框用（过长会省略，与 Element Plus 单行展示一致） */
function recordSelectDisplayLabel(r) {
  const line = recordSelectPrimaryLine(r);
  const tag = recordStatusLabel(r);
  const combined = `${line} · ${tag}`;
  return combined.length > 64 ? `${combined.slice(0, 61)}…` : combined;
}

/** 悬停 title：完整路径 + 状态 */
function recordSelectFullLabel(r) {
  if (!r || typeof r !== 'object') return '';
  return `${recordSelectPrimaryLine(r)} · ${recordStatusLabel(r)}`;
}

const recordPickerTitleAttr = computed(() => {
  const id = selectedId.value;
  if (!id) return undefined;
  const r = records.value.find((x) => String(x.id) === String(id));
  return r ? recordSelectFullLabel(r) : undefined;
});

/** 下拉项第三行：带时间戳前缀等长文件名时展示，便于与菜单路径对照 */
function recordSelectFileHint(r) {
  const raw = String(r.file_name || '').trim();
  if (!raw) return '';
  const path = breadcrumb(r.menu_structure);
  if (!path) return '';
  if (raw.includes(' - ') || raw.length > 56) {
    return raw.length > 92 ? `${raw.slice(0, 89)}…` : raw;
  }
  return '';
}

/** 去掉批量生成写入的固定前缀，便于按行拆成表格行 */
// stripStyleOcrPrefix, linesFromStyleText -> moved to useStyleTable

/** 与 analysis_style_table 同步保存，避免回填逻辑把已删除行“复活” */
// styleTextFromRows, normalizeRowsForSave, styleTableHasDisplayContent,
// loadStyleRowsFromRecord -> moved to useStyleTable

function _watchTargetKey(sid, cat, main) {
  return `${String(sid ?? '')}:${String(cat ?? '')}:${String(main ?? '')}`;
}

/** 样式表行是否无任何有效识别/补充内容（仅空白或默认「文本」） */
function styleRowsVisuallyEmpty(rows) {
  if (!Array.isArray(rows) || !rows.length) return true;
  return rows.every((r) => {
    const el = String(r?.element || '').trim();
    const req = String(r?.requirement || '').trim();
    const attr = String(r?.attribute || '文本').trim();
    return !el && !req && (!attr || attr === '文本');
  });
}

watch(
  [selectedId, activeCategory, activeMainTab],
  async ([newSid, newCat, newMain], oldTuple) => {
    const oldSid = oldTuple?.[0];
    const oldCat = oldTuple?.[1];
    const targetKey = _watchTargetKey(newSid, newCat, newMain);
    /** 下拉切换需求（而非仅切换标签页） */
    const switchingScreenshot =
      oldTuple !== undefined && String(newSid ?? '') !== String(oldSid ?? '');
    const showDetailWait = switchingScreenshot && !generating.value && !historyLoading.value;

    if (showDetailWait) {
      recordDetailLoading.value = true;
    }
    if (switchingScreenshot) {
      vectorSyncHint.value = '';
      vectorPanelMode.value = 'analysis';
    }

    try {
      // 离开样式分析或切换需求前，立即保存当前表格，避免编辑丢失。
      if (oldTuple !== undefined && oldSid !== undefined && oldSid !== '' && oldCat === 'style') {
        const leavingStyleTab = newCat !== oldCat;
        const recordChanged = String(newSid ?? '') !== String(oldSid ?? '');
        if (leavingStyleTab || recordChanged) {
          clearStyleAutoSaveDebounce();
          await flushStyleToHistoryId(Number(oldSid), true);
        }
      }

      // await 之后用户可能已切换标签/需求：继续执行会用错分类或旧数据覆盖草稿（表现为「点交互为空，刷新才有」）
      if (_watchTargetKey(selectedId.value, activeCategory.value, activeMainTab.value) !== targetKey) {
        return;
      }

      const hid = Number(newSid);
      const fresh = Number.isFinite(hid) && hid > 0
        ? records.value.find((r) => Number(r.id) === hid)
        : null;
      const rec = fresh || activeRecord.value;
      if (!rec) {
        styleRows.value = [];
        draftText.value = '';
        draftDataText.value = '';
        vectorAnalysisResult.value = '';
        vectorBuildText.value = '';
        vectorBuildResult.value = '';
        extraAttrOptions.value = [];
        return;
      }
      styleTableHydrating.value = true;
      try {
        if (switchingScreenshot) {
          extraAttrOptions.value = [];
        }
        loadStyleRowsFromRecord(rec);
        for (const row of styleRows.value) {
          const a = row.attribute;
          if (a && !DEFAULT_ATTR_OPTIONS.includes(a) && !extraAttrOptions.value.includes(a)) {
            extraAttrOptions.value.push(a);
          }
        }
        // 列表项可能缺 analysis_style_table：有生成时间但表格为空时拉详情（与内容/交互分支一致）
        if (
          newCat === 'style'
          && Number.isFinite(hid)
          && hid > 0
          && styleRowsVisuallyEmpty(styleRows.value)
          && String(rec.analysis_generated_at || '').trim()
        ) {
          try {
            const full = await getHistoryDetail(hid);
            if (_watchTargetKey(selectedId.value, activeCategory.value, activeMainTab.value) !== targetKey) {
              return;
            }
            if (full && typeof full === 'object') {
              const ix = records.value.findIndex((r) => Number(r.id) === hid);
              if (ix >= 0) Object.assign(records.value[ix], full);
              const src = ix >= 0 ? records.value[ix] : full;
              loadStyleRowsFromRecord(src);
              for (const row of styleRows.value) {
                const a = row.attribute;
                if (a && !DEFAULT_ATTR_OPTIONS.includes(a) && !extraAttrOptions.value.includes(a)) {
                  extraAttrOptions.value.push(a);
                }
              }
            }
          } catch {
            // 忽略
          }
        }
        if (newCat === 'content') draftText.value = rec.analysis_content || '';
        else if (newCat === 'interaction') draftText.value = rec.analysis_interaction || '';
        else if (newCat === 'data') {
          const ad = rec.analysis_data;
          draftDataText.value = typeof ad === 'string' ? ad : (ad ? JSON.stringify(ad, null, 2) : '');
        }
        vectorAnalysisResult.value = String(rec.analysis || '').trim();
        vectorBuildText.value = String(rec.vector_analysis_text || '').trim();
        vectorBuildResult.value = String(rec.vector_build_summary || '').trim();

        // 列表项可能被局部 merge 遗漏字段：详情仍为空时再拉一条完整记录
        if (
          (newCat === 'interaction' || newCat === 'content')
          && !String(draftText.value || '').trim()
          && Number.isFinite(hid)
          && hid > 0
        ) {
          try {
            const full = await getHistoryDetail(hid);
            if (_watchTargetKey(selectedId.value, activeCategory.value, activeMainTab.value) !== targetKey) {
              return;
            }
            if (full && typeof full === 'object') {
              const ix = records.value.findIndex((r) => Number(r.id) === hid);
              if (ix >= 0) Object.assign(records.value[ix], full);
              const src = ix >= 0 ? records.value[ix] : full;
              if (newCat === 'interaction') {
                draftText.value = String(src.analysis_interaction || '');
              } else {
                draftText.value = String(src.analysis_content || '');
              }
            }
          } catch {
            // 忽略：无网或接口不可用时保持空
          }
        }

        if (
          newCat === 'data'
          && !String(draftDataText.value || '').trim()
          && Number.isFinite(hid)
          && hid > 0
        ) {
          try {
            const full = await getHistoryDetail(hid);
            if (_watchTargetKey(selectedId.value, activeCategory.value, activeMainTab.value) !== targetKey) {
              return;
            }
            if (full && typeof full === 'object') {
              const ix = records.value.findIndex((r) => Number(r.id) === hid);
              if (ix >= 0) Object.assign(records.value[ix], full);
              const src = ix >= 0 ? records.value[ix] : full;
              const ad = src.analysis_data;
              draftDataText.value = typeof ad === 'string' ? ad : (ad ? JSON.stringify(ad, null, 2) : '');
            }
          } catch {
            // 忽略
          }
        }

        await nextTick();
        await nextTick();
      } finally {
        styleTableHydrating.value = false;
      }
    } finally {
      if (showDetailWait) {
        recordDetailLoading.value = false;
      }
    }
  },
  { immediate: true },
);

// styleRows watcher, addStyleRow, removeStyleRow, addCustomAttrOption -> useStyleTable
// syncVectorForCurrentRecord, analyzeVectorForCurrentRecord, saveVectorAnalysisResult -> useVectorAnalysis
// flushStyleToHistoryId, persistStyleTable, saveStyleTableManual -> useStyleTable

function coerceHistoryId(id) {
  const n = Number(id);
  return Number.isFinite(n) ? n : NaN;
}

async function putHistory(id, payload) {
  const hid = coerceHistoryId(id);
  if (!Number.isFinite(hid)) {
    throw new Error('Invalid id');
  }
  return updateHistory(hid, payload);
}

const saveTextCategory = async () => {
  const rec = activeRecord.value;
  if (!rec) return;
  saving.value = true;
  try {
    const payload =
      activeCategory.value === 'content'
        ? { analysis_content: draftText.value }
        : { analysis_interaction: draftText.value };
    await putHistory(rec.id, payload);
    await fetchHistory();
    emitHistoryUpdated();
    await alertDialog('保存成功');
  } catch (e) {
    await alertDialog(`保存失败：${e.message || e}`);
  } finally {
    saving.value = false;
  }
};

const saveDataCategory = async () => {
  const rec = activeRecord.value;
  if (!rec) return;
  saving.value = true;
  try {
    await putHistory(rec.id, { analysis_data: String(draftDataText.value || '').trim() });
    await fetchHistory();
    emitHistoryUpdated();
    await alertDialog('保存成功');
  } catch (e) {
    await alertDialog(`保存失败：${e.message || e}`);
  } finally {
    saving.value = false;
  }
};

onMounted(async () => {
  await fetchHistory();
});

// Timer cleanup now handled by useStyleTable composable
</script>

<style scoped>
.req-lib {
  min-height: 100vh;
}

.req-lib--replica {
  background: linear-gradient(180deg, #f7f9fd 0%, #f1f4fa 100%);
  padding: 2px;
}
.replica-shell {
  position: relative;
  border: 1px solid #d7deea;
  box-shadow: 0 10px 26px rgba(31, 54, 91, 0.09);
  background: linear-gradient(180deg, #ffffff 0%, #fdfefe 100%);
}
.replica-shell-loading-mask {
  position: absolute;
  inset: 0;
  z-index: 20;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 120px;
  background: rgba(255, 255, 255, 0.55);
  border-radius: inherit;
  backdrop-filter: blur(2px);
}
.replica-shell__head {
  display: flex;
  gap: 16px;
  align-items: stretch;
  justify-content: space-between;
  padding: 4px;
}
.replica-shell__selector {
  flex: 1;
  min-width: min(420px, 100%);
}
.replica-label {
  display: block;
  font-size: 13px;
  color: #4a5870;
  font-weight: 600;
  margin-bottom: 8px;
}
.replica-record-select {
  border: 1px solid #d9e1ef;
  border-radius: 10px;
  background: linear-gradient(180deg, #ffffff 0%, #f7faff 100%);
  padding: 10px;
}
.replica-record-select :deep(.el-select__wrapper) {
  min-height: 42px;
  border-radius: 8px;
  border: 1px solid #c9d7ef;
  background: #fff;
  box-shadow: none;
  font-size: 13px;
}
/* 多行标签（多选）时允许换行；勿改 placeholder 定位，否则会与 filterable 输入框纵向错行 */
.replica-record-select :deep(.el-select__tags-text) {
  white-space: normal;
  word-break: break-word;
  line-height: 1.45;
  max-width: 100%;
}
.replica-record-select :deep(.el-select__wrapper:hover) {
  border-color: #94b4e8;
}
.req-record-picker-wrap :deep(.el-select__wrapper) {
  min-height: 42px;
  border-radius: 8px;
}
.req-record-picker-wrap :deep(.el-select__tags-text) {
  white-space: normal;
  word-break: break-word;
  line-height: 1.45;
  max-width: 100%;
}
.req-record-option {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 2px 0;
  max-width: 100%;
}
.req-record-option__path--with-status {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}
.req-record-option__path-text {
  font-weight: 600;
  color: #1e293b;
  font-size: 13px;
  line-height: 1.4;
  word-break: break-word;
  flex: 1;
  min-width: 0;
}
.req-record-status {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 9px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.02em;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  color: #64748b;
}
.req-record-status.is-pending {
  border-color: #e2e8f0;
  background: #f1f5f9;
  color: #64748b;
}
.req-record-status.is-progress {
  border-color: #bfdbfe;
  background: #eff6ff;
  color: #1d4ed8;
}
.req-record-status.is-done {
  border-color: #a7f3d0;
  background: #ecfdf5;
  color: #047857;
}
.req-record-option__meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 12px;
  color: #64748b;
}
.req-record-option__id {
  font-family: ui-monospace, Consolas, monospace;
  font-size: 11px;
  color: #64748b;
  padding: 1px 6px;
  border-radius: 4px;
  background: #f1f5f9;
}
.req-record-option__file {
  font-size: 11px;
  color: #94a3b8;
  line-height: 1.35;
  word-break: break-all;
}
.req-record-picker-empty {
  padding: 12px;
  text-align: center;
  color: #94a3b8;
  font-size: 13px;
}
.replica-record-meta {
  margin-top: 10px;
  border: 1px solid #e0e6f2;
  border-radius: 10px;
  background: #f8fafd;
  padding: 10px 12px;
}
.replica-record-meta__title {
  font-size: 13px;
  font-weight: 700;
  color: #223554;
  line-height: 1.4;
  word-break: break-word;
}
.replica-record-meta__sub {
  margin-top: 4px;
  font-size: 12px;
  color: #64748b;
}
.replica-record-meta__tags {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.replica-record-tag {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  border: 1px solid #d4dbe8;
  background: #fff;
  color: #8a96ab;
  font-size: 11px;
}
.replica-record-tag.is-done {
  border-color: #9fd7b6;
  color: #1f8a4e;
  background: #effbf3;
}
.replica-shell__preview {
  width: 300px;
  max-width: 100%;
}
.replica-preview-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.replica-preview-head__hint {
  font-size: 11px;
  color: #6682ad;
  border: 1px solid #ccd8ee;
  border-radius: 999px;
  background: #f3f7ff;
  padding: 2px 8px;
}
.replica-preview-box {
  border: 1px solid #d5dcea;
  border-radius: 12px;
  background:
    linear-gradient(45deg, #f7f9fd 25%, transparent 25%) 0 0 / 12px 12px,
    linear-gradient(-45deg, #f7f9fd 25%, transparent 25%) 0 0 / 12px 12px,
    linear-gradient(45deg, transparent 75%, #f7f9fd 75%) 0 0 / 12px 12px,
    linear-gradient(-45deg, transparent 75%, #f7f9fd 75%) 0 0 / 12px 12px,
    #ffffff;
  min-height: 220px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.8);
}
.replica-preview-img {
  display: block;
  max-width: calc(100% - 20px);
  max-height: 260px;
  object-fit: contain;
  border-radius: 8px;
  border: 1px solid #e1e7f1;
  background: #fff;
  box-shadow: 0 8px 20px rgba(24, 55, 102, 0.14);
  transition: transform 0.25s ease;
}
.replica-preview-img:hover {
  transform: scale(1.015);
}
.replica-preview-empty {
  color: #8a93a6;
  font-size: 12px;
  border: 1px dashed #ccd5e4;
  border-radius: 8px;
  background: #fbfcff;
  padding: 12px 16px;
}
.replica-action-grid {
  margin-top: 14px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}
.replica-action-card {
  border: 1px solid #d7deea;
  border-radius: 10px;
  background: #fff;
  padding: 10px;
  box-shadow: 0 1px 3px rgba(31, 54, 91, 0.05);
  transition: all 0.2s ease;
  text-align: center;
}
.replica-action-card.is-done {
  border-color: #9fd7b6;
  background: linear-gradient(180deg, #f5fff8 0%, #eefbf3 100%);
}
.replica-action-card.is-locked {
  border-color: #dde3ef;
  background: #f7f9fc;
}
.replica-action-btn {
  width: 100%;
  background: #fff;
  color: #1f2a37;
  border-color: #d7deea;
}
.replica-action-btn:hover:not(:disabled) {
  border-color: #87a7dd;
  color: #1b4e9b;
  background: #f7fbff;
}
.replica-action-btn:disabled {
  background: #f2f4f7;
  color: #98a2b3;
  border-color: #d6dde8;
  cursor: not-allowed;
  box-shadow: none;
}
.replica-action-btn:disabled:hover {
  background: #f2f4f7;
  color: #98a2b3;
  border-color: #d6dde8;
}
.replica-action-meta {
  margin-top: 8px;
  font-size: 12px;
  color: #64748b;
  text-align: center;
}
.replica-action-card.is-done .replica-action-meta {
  color: #257a4b;
}
.replica-action-card.is-locked .replica-action-meta {
  color: #90a0b6;
}
.replica-hint {
  margin-top: 10px;
  font-size: 12px;
  color: #627089;
}
@media (max-width: 1100px) {
  .replica-shell__head {
    flex-direction: column;
  }
  .replica-shell__preview {
    width: 100%;
  }
  .replica-action-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

/* 涓嬫柟璇︽儏鍗＄墖鍐咃細鍒囨崲鎴浘鏃剁殑灞€閮ㄧ瓑寰咃紙涓庡叏灞€ DialogHost 鍙屽姬椋庢牸涓€鑷达級 */
.req-lib-detail-shell {
  position: relative;
  min-height: 280px;
}
.req-lib-detail-overlay {
  position: absolute;
  inset: 0;
  z-index: 20;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
  background: rgba(216, 216, 216, 0.9);
  border-radius: 8px;
}
.req-lib-detail-body--dim {
  opacity: 0.88;
  pointer-events: none;
  user-select: none;
}
.req-lib-detail-spinner {
  position: relative;
  width: 48px;
  height: 48px;
  flex-shrink: 0;
}
.req-lib-detail-spinner__arc {
  display: block;
  position: absolute;
  box-sizing: border-box;
  border-radius: 50%;
  border: 2px solid transparent;
}
.req-lib-detail-spinner__arc--outer {
  inset: 0;
  border-top-color: #4a5563;
  border-right-color: #4a5563;
  animation: req-lib-detail-spin 0.95s linear infinite;
}
.req-lib-detail-spinner__arc--inner {
  width: 68%;
  height: 68%;
  left: 16%;
  top: 16%;
  border-bottom-color: #4a5563;
  border-left-color: #4a5563;
  animation: req-lib-detail-spin 0.75s linear infinite reverse;
}
.req-lib-detail-overlay-caption {
  font-size: 13px;
  color: #4b5563;
}

.req-lib-generate-overlay {
  position: absolute;
  inset: 0;
  z-index: 22;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: linear-gradient(180deg, rgba(246, 249, 253, 0.86) 0%, rgba(238, 244, 252, 0.92) 100%);
  backdrop-filter: blur(2px);
  border-radius: 8px;
}
.req-lib-generate-panel {
  width: min(780px, 100%);
  border-radius: 14px;
  border: 1px solid rgba(141, 178, 230, 0.35);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.94) 0%, rgba(249, 252, 255, 0.98) 100%);
  box-shadow: 0 12px 30px rgba(36, 87, 163, 0.12);
  padding: 16px;
}
.req-lib-generate-head {
  display: flex;
  align-items: center;
  gap: 12px;
}
.req-lib-generate-title {
  font-size: 14px;
  font-weight: 700;
  color: #243b5f;
}
.req-lib-generate-subtitle {
  margin-top: 4px;
  font-size: 12px;
  color: #5a6b82;
}
.req-lib-generate-spinner {
  position: relative;
  width: 36px;
  height: 36px;
  flex-shrink: 0;
}
.req-lib-generate-spinner__ring {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 2px solid transparent;
}
.req-lib-generate-spinner__ring--outer {
  border-top-color: #4f7fce;
  border-right-color: #4f7fce;
  animation: req-lib-detail-spin 0.95s linear infinite;
}
.req-lib-generate-spinner__ring--inner {
  inset: 22%;
  border-left-color: #7ea6e8;
  border-bottom-color: #7ea6e8;
  animation: req-lib-detail-spin 0.8s linear infinite reverse;
}
.req-lib-generate-log-wrap {
  margin-top: 12px;
  max-height: 200px;
  overflow: auto;
  border: 1px solid #e4ecf8;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.8);
  padding: 10px 12px;
}
.req-lib-generate-log-empty {
  color: #8a98ac;
  font-size: 12px;
}
.req-lib-generate-log-line {
  font-size: 12px;
  color: #31445f;
  line-height: 1.45;
  word-break: break-word;
}
.req-lib-generate-log-line + .req-lib-generate-log-line {
  margin-top: 7px;
  padding-top: 7px;
  border-top: 1px dashed rgba(196, 214, 240, 0.7);
}
@keyframes req-lib-detail-spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.req-lib-loading-banner {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  margin-bottom: 12px;
  background: linear-gradient(180deg, #e6f7ff 0%, #d6efff 100%);
  border: 1px solid #91d5ff;
  border-radius: 10px;
  color: #0958d9;
  font-size: 14px;
  box-shadow: 0 1px 4px rgba(24, 144, 255, 0.12);
}
.req-lib-spinner {
  display: inline-block;
  width: 20px;
  height: 20px;
  border: 2px solid rgba(24, 144, 255, 0.35);
  border-top-color: #1890ff;
  border-radius: 50%;
  animation: req-lib-spin 0.65s linear infinite;
  flex-shrink: 0;
}
@keyframes req-lib-spin {
  to {
    transform: rotate(360deg);
  }
}
.req-lib-card--dim {
  opacity: 0.88;
  pointer-events: none;
  transition: opacity 0.2s ease;
}
.record-top {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: flex-start;
}
.record-top-main {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  flex: 1;
  min-width: 0;
}
.screenshot-preview-wrap {
  flex-shrink: 0;
  width: 100%;
  max-width: 420px;
}
.screenshot-preview-label {
  font-size: 12px;
  color: #666;
  margin-bottom: 6px;
}
.screenshot-preview-inner {
  border: 1px solid #e8eaef;
  border-radius: 10px;
  overflow: hidden;
  background: #f5f5f5;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 120px;
  max-height: 280px;
}
.screenshot-preview-img {
  max-width: 100%;
  max-height: 280px;
  width: auto;
  height: auto;
  object-fit: contain;
  display: block;
}
.vector-sync-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #eee;
}
.vector-sync-hint {
  font-size: 12px;
  color: #52c41a;
}
.req-lib-vector-shell {
  position: relative;
}
.req-lib-vector-loading-mask {
  position: absolute;
  inset: 0;
  z-index: 12;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 14px;
  background: rgba(245, 249, 255, 0.18);
  border-radius: 10px;
  backdrop-filter: blur(1px);
}
.req-lib-vector-loading-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 999px;
  border: 1px solid #cfe2ff;
  background: rgba(255, 255, 255, 0.94);
  color: #245a9d;
  font-size: 12px;
  box-shadow: 0 4px 14px rgba(45, 104, 188, 0.15);
}
.req-lib-vector-loading-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 2px solid rgba(36, 90, 157, 0.28);
  border-top-color: #245a9d;
  animation: req-lib-spin 0.75s linear infinite;
}
.panel-desc {
  margin: 0 0 12px;
  font-size: 13px;
  line-height: 1.55;
  color: #555;
}
.panel-block {
  border: 1px solid #e8e8e8;
  border-radius: 10px;
  background: #fafbfc;
  padding: 16px;
  min-height: 280px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}
.panel-block--style {
  background: linear-gradient(180deg, #fafbfc 0%, #f5f7fa 100%);
}
.panel-block--data .panel-desc strong {
  color: #1890ff;
}
.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin-bottom: 10px;
}
.custom-attr {
  display: flex;
  gap: 8px;
  align-items: center;
}
.input-sm {
  max-width: 220px;
  padding: 6px 10px;
  font-size: 13px;
}
.table-wrap {
  overflow-x: auto;
}
.table-wrap--rounded {
  border-radius: 8px;
  border: 1px solid #e0e4ea;
  overflow: hidden;
  background: #fff;
}
.style-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  background: #fff;
}
.style-table th,
.style-table td {
  border: 1px solid #e8eaef;
  padding: 10px 12px;
  vertical-align: top;
}
.style-table thead th {
  background: linear-gradient(180deg, #f0f2f5 0%, #e8ebf0 100%);
  font-weight: 600;
  text-align: left;
  color: #333;
  letter-spacing: 0.02em;
}
.style-table tbody tr:nth-child(even) {
  background: #fafbfc;
}
.style-table tbody tr:hover {
  background: #f0f7ff;
}
.td-index {
  text-align: center;
  font-weight: 600;
  color: #8c8c8c;
  width: 48px;
  background: #fafafa;
}
.col-idx {
  width: 52px;
}
.col-el {
  width: 22%;
  max-width: 220px;
}
.td-el {
  max-width: 220px;
}
.input-el-compact {
  width: 100%;
  max-width: 200px;
  box-sizing: border-box;
  font-size: 12px;
  padding: 6px 8px;
  line-height: 1.35;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
}
.input-el-compact:focus {
  border-color: #1890ff;
  outline: none;
  box-shadow: 0 0 0 2px rgba(24, 144, 255, 0.12);
}
.col-attr {
  width: 14%;
  min-width: 120px;
}
.col-req {
  min-width: 200px;
}
.col-act {
  width: 72px;
}
.input-cell {
  width: 100%;
  box-sizing: border-box;
}
.textarea-cell {
  width: 100%;
  box-sizing: border-box;
  min-height: 72px;
  resize: vertical;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.45;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  padding: 8px 10px;
}
.style-save-status {
  font-size: 12px;
  color: #52c41a;
  margin-right: auto;
}
.save-bar--auto {
  justify-content: flex-end;
  align-items: center;
}
.select-attr {
  width: 100%;
  max-width: 200px;
  padding: 8px 10px;
  font-size: 13px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
}
.select-attr:focus {
  border-color: #1890ff;
  outline: none;
  box-shadow: 0 0 0 2px rgba(24, 144, 255, 0.15);
}
.btn-sm {
  padding: 4px 10px;
  font-size: 12px;
}
.textarea-block {
  width: 100%;
  min-height: 280px;
  box-sizing: border-box;
  padding: 10px;
  font-size: 13px;
  line-height: 1.5;
  border: 1px solid #e8e8e8;
  border-radius: 6px;
  font-family: inherit;
  resize: vertical;
}
.textarea-block.mono {
  font-family: ui-monospace, Consolas, monospace;
  font-size: 12px;
}
.save-bar {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
.save-bar--split {
  justify-content: space-between;
  flex-wrap: wrap;
}
</style>

<!-- 下拉挂载在 body，需非 scoped 样式 -->
<style>
.req-record-picker-dropdown.el-select__popper,
.el-popper.req-record-picker-dropdown {
  min-width: min(640px, calc(100vw - 24px)) !important;
  max-width: min(960px, calc(100vw - 16px)) !important;
}
.req-record-picker-dropdown .el-select-dropdown {
  min-width: 100% !important;
  box-sizing: border-box;
}
.req-record-picker-dropdown .el-select-dropdown__item {
  height: auto !important;
  line-height: normal !important;
  padding: 0 !important;
  overflow: visible !important;
}
.req-record-picker-dropdown .el-select-dropdown__item.is-selected {
  font-weight: inherit;
}
.req-record-picker-dropdown .el-select-dropdown__item .req-record-option {
  padding: 10px 12px;
}
/* teleported 下拉在 body 下，需与 scoped 中一致的布局与状态徽标 */
.req-record-picker-dropdown .req-record-option__path--with-status {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}
.req-record-picker-dropdown .req-record-option__path-text {
  font-weight: 600;
  color: #1e293b;
  font-size: 13px;
  line-height: 1.4;
  word-break: break-word;
  flex: 1;
  min-width: 0;
}
.req-record-picker-dropdown .req-record-status {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 9px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.02em;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  color: #64748b;
}
.req-record-picker-dropdown .req-record-status.is-pending {
  border-color: #e2e8f0;
  background: #f1f5f9;
  color: #64748b;
}
.req-record-picker-dropdown .req-record-status.is-progress {
  border-color: #bfdbfe;
  background: #eff6ff;
  color: #1d4ed8;
}
.req-record-picker-dropdown .req-record-status.is-done {
  border-color: #a7f3d0;
  background: #ecfdf5;
  color: #047857;
}
</style>
