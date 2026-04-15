<template>
  <div class="case-mgmt">
    <div class="card case-mgmt-hero">
      <header class="page-header case-mgmt-page-header">
        <h1>{{ onlyExecution ? CM.execTitle : CM.mgmtTitle }}</h1>
        <p v-if="onlyExecution">{{ CM.standaloneHint }}</p>
        <p v-else>{{ CM.featureLine }}</p>
      </header>
      <div class="zt-tabbar">
        <button class="zt-tab" type="button" :class="{ active: activeTab === 'preview' }" @click="activeTab = 'preview'">
          {{ onlyExecution ? CM.tabExecRecord : CM.tabPreview }}
        </button>
        <button v-if="!onlyExecution" type="button" class="zt-tab" :class="{ active: activeTab === 'generate' }" @click="activeTab = 'generate'">{{ CM.tabGenerate }}</button>
        <button v-if="!onlyExecution" type="button" class="zt-tab" :class="{ active: activeTab === 'create' }" @click="activeTab = 'create'">{{ CM.tabCreate }}</button>
        <button v-if="!onlyExecution" type="button" class="zt-tab" :class="{ active: activeTab === 'library' }" @click="activeTab = 'library'">{{ CM.tabLibrary }}</button>
        <div class="zt-tabbar-spacer" />
        <button type="button" class="btn btn-default" @click="refreshAll" :disabled="isPageBusy">{{ isPageBusy ? CM.refreshing : CM.refresh }}</button>
      </div>
    </div>

    <div class="zt-layout">
      <aside class="zt-side card">
        <div style="font-weight:700;">{{ CM.sidebarHeading }}</div>
        <div class="form-group" style="margin-top:10px;">
          <label>{{ CM.treeFilter }}</label>
          <input class="input tree-search" v-model="treeKeyword" :placeholder="CM.searchPlaceholder" />
          <div class="zt-tree">
            <template v-for="node in displayTreeRootsAll" :key="node.key">
              <TreeNode :node="node" :active-path="selectedPath" @toggle="toggleNode" @select="selectPath" />
            </template>
            <div v-if="displayTreeRootsAll.length === 0" style="color:#999;">{{ CM.noScreenshotRecords }}</div>
          </div>
        </div>
        <div class="selected-path-tip">
          {{ CM.selectedPrefix }}{{ selectedPath.length ? selectedPath.join(' / ') : CM.allSubmenus }}
        </div>
        <div style="display:flex; gap:8px; flex-wrap:wrap;">
          <button class="btn btn-default" @click="clearPath" :disabled="isPageBusy">{{ CM.clearFilter }}</button>
        </div>
        <div style="margin-top:10px; color:#999; font-size:12px;">
          {{ CM.filterPrefix }}{{ selectedPath.length ? selectedPath.join(' / ') : CM.all }}
        </div>
      </aside>

      <section class="zt-main">
        <div class="card" v-if="activeTab === 'preview'">
          <div class="zt-title">{{ CM.previewTitle }}</div>

          <template v-if="onlyExecution">
            <div class="zt-metrics zt-metrics--clickable">
              <div
                class="zt-metric"
                :class="{ 'zt-metric--active': !filterStatus && !filterPriority }"
                role="button"
                tabindex="0"
                @click="clearExecutionFilters"
                @keydown.enter.prevent="clearExecutionFilters"
              >
                <div class="k">{{ CM.metricTotal }}</div>
                <div class="v">{{ filteredCasesByMenu.length }}</div>
              </div>
              <div
                class="zt-metric"
                :class="{ 'zt-metric--active': filterStatus === 'draft' }"
                role="button"
                tabindex="0"
                @click="filterStatus = 'draft'"
                @keydown.enter.prevent="filterStatus = 'draft'"
              >
                <div class="k">{{ CM.notRun }}</div>
                <div class="v">{{ filteredCasesByMenu.filter((c) => c.status === 'draft').length }}</div>
              </div>
              <div
                class="zt-metric"
                :class="{ 'zt-metric--active': filterStatus === 'pass' }"
                role="button"
                tabindex="0"
                @click="filterStatus = 'pass'"
                @keydown.enter.prevent="filterStatus = 'pass'"
              >
                <div class="k">{{ CM.pass }}</div>
                <div class="v">{{ filteredCasesByMenu.filter((c) => c.status === 'pass').length }}</div>
              </div>
              <div
                class="zt-metric"
                :class="{ 'zt-metric--active': filterStatus === 'fail' }"
                role="button"
                tabindex="0"
                @click="filterStatus = 'fail'"
                @keydown.enter.prevent="filterStatus = 'fail'"
              >
                <div class="k">{{ CM.fail }}</div>
                <div class="v">{{ filteredCasesByMenu.filter((c) => c.status === 'fail').length }}</div>
              </div>
              <div
                class="zt-metric"
                :class="{ 'zt-metric--active': filterStatus === 'blocked' }"
                role="button"
                tabindex="0"
                @click="filterStatus = 'blocked'"
                @keydown.enter.prevent="filterStatus = 'blocked'"
              >
                <div class="k">{{ CM.blocked }}</div>
                <div class="v">{{ filteredCasesByMenu.filter((c) => c.status === 'blocked').length }}</div>
              </div>
            </div>

            <div class="exec-filter-block">
              <div class="exec-filter-label">{{ CM.colStatus }}</div>
              <div class="exec-pill-row">
                <button type="button" class="exec-pill" :class="{ 'exec-pill--active': !filterStatus }" @click="filterStatus = ''">{{ CM.all }}</button>
                <button type="button" class="exec-pill" :class="{ 'exec-pill--active': filterStatus === 'draft' }" @click="filterStatus = 'draft'">{{ CM.notRun }}</button>
                <button type="button" class="exec-pill" :class="{ 'exec-pill--active': filterStatus === 'pass' }" @click="filterStatus = 'pass'">{{ CM.pass }}</button>
                <button type="button" class="exec-pill" :class="{ 'exec-pill--active': filterStatus === 'fail' }" @click="filterStatus = 'fail'">{{ CM.fail }}</button>
                <button type="button" class="exec-pill" :class="{ 'exec-pill--active': filterStatus === 'blocked' }" @click="filterStatus = 'blocked'">{{ CM.blocked }}</button>
              </div>
            </div>
            <div class="exec-filter-block">
              <div class="exec-filter-label">{{ CM.filterPriorityLabel }}</div>
              <div class="exec-pill-row">
                <button type="button" class="exec-pill" :class="{ 'exec-pill--active': !filterPriority }" @click="filterPriority = ''">{{ CM.priorityAll }}</button>
                <button type="button" class="exec-pill exec-pill--p0" :class="{ 'exec-pill--active': filterPriority === 'P0' }" @click="filterPriority = 'P0'">P0</button>
                <button type="button" class="exec-pill exec-pill--p1" :class="{ 'exec-pill--active': filterPriority === 'P1' }" @click="filterPriority = 'P1'">P1</button>
                <button type="button" class="exec-pill exec-pill--p2" :class="{ 'exec-pill--active': filterPriority === 'P2' }" @click="filterPriority = 'P2'">P2</button>
                <button type="button" class="exec-pill exec-pill--p3" :class="{ 'exec-pill--active': filterPriority === 'P3' }" @click="filterPriority = 'P3'">P3</button>
              </div>
            </div>
            <div class="zt-filterbar">
              <input class="input exec-search" v-model="keyword" :placeholder="CM.searchPlaceholder" />
            </div>
          </template>

          <template v-else>
            <div class="zt-metrics">
              <div class="zt-metric">
                <div class="k">{{ CM.metricTotal }}</div>
                <div class="v">{{ filteredCasesByMenu.length }}</div>
              </div>
              <div class="zt-metric">
                <div class="k">{{ CM.pass }}</div>
                <div class="v">{{ filteredCasesByMenu.filter((c) => c.status === 'pass').length }}</div>
              </div>
              <div class="zt-metric">
                <div class="k">{{ CM.fail }}</div>
                <div class="v">{{ filteredCasesByMenu.filter((c) => c.status === 'fail').length }}</div>
              </div>
              <div class="zt-metric">
                <div class="k">{{ CM.blocked }}</div>
                <div class="v">{{ filteredCasesByMenu.filter((c) => c.status === 'blocked').length }}</div>
              </div>
              <div class="zt-metric">
                <div class="k">{{ CM.notRun }}</div>
                <div class="v">{{ filteredCasesByMenu.filter((c) => c.status === 'draft').length }}</div>
              </div>
            </div>

            <div class="zt-filterbar">
              <select class="input" v-model="filterStatus" style="max-width:200px;">
                <option value="">{{ CM.allStatus }}</option>
                <option value="draft">{{ CM.notRun }}</option>
                <option value="pass">{{ CM.pass }}</option>
                <option value="fail">{{ CM.fail }}</option>
                <option value="blocked">{{ CM.blocked }}</option>
              </select>
              <input class="input" v-model="keyword" :placeholder="CM.searchPlaceholder" style="max-width:360px;" />
            </div>
          </template>

          <div class="zt-tablewrap">
            <table class="table" :class="{ 'table--exec': onlyExecution }">
              <thead>
                <tr>
                  <th style="width:90px;">ID</th>
                  <th>{{ CM.colTitle }}</th>
                  <th style="width:120px;">{{ CM.colStatus }}</th>
                  <th v-if="onlyExecution" style="width:88px;">{{ CM.colPriority }}</th>
                  <th style="width:180px;">{{ CM.colLastRun }}</th>
                  <th v-if="onlyExecution" style="width:120px;">{{ CM.colExecutor }}</th>
                  <th :style="onlyExecution ? { width: '220px' } : { width: '260px' }">{{ CM.colActions }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="c in previewList" :key="c.id">
                  <td>{{ c.id }}</td>
                  <td>
                    <div style="font-weight:600;">{{ c.title }}</div>
                    <div style="color:#666; font-size:12px; margin-top:4px;">{{ CM.screenshotId }}{{ c.history_id || '-' }}</div>
                  </td>
                  <td><span class="tag" :class="statusTagClass(c.status)">{{ statusLabel(c.status) }}</span></td>
                  <td v-if="onlyExecution"><span class="tag" :class="priorityTagClass(c.priority)">{{ priorityLabel(c.priority) }}</span></td>
                  <td>{{ c.last_run_at || '-' }}</td>
                  <td v-if="onlyExecution" class="cell-executor">{{ executorDisplay(c) }}</td>
                  <td>
                    <div style="display:flex; gap:8px; flex-wrap:wrap;">
                      <button type="button" class="btn btn-default" @click="openEdit(c)" :disabled="isPageBusy">{{ CM.edit }}</button>
                      <button type="button" class="btn btn-default" @click="openExecute(c)" :disabled="isPageBusy">{{ CM.run }}</button>
                      <button v-if="!onlyExecution" type="button" class="btn btn-danger" @click="deleteCase(c)" :disabled="isPageBusy">{{ CM.del }}</button>
                    </div>
                  </td>
                </tr>
                <tr v-if="previewList.length === 0">
                  <td :colspan="onlyExecution ? 7 : 5" style="text-align:center; color:#999;">{{ CM.noData }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="card" v-else-if="activeTab === 'generate'">
          <div class="zt-title">{{ CM.genTitle }}</div>
          <div style="color:#666; font-size:13px; margin-top:6px;">{{ CM.genIntro }}</div>

          <div style="display:grid; grid-template-columns: 1fr 360px; gap:16px; margin-top: 12px;">
            <div class="generate-main-col">
              <div class="zt-panel">
                <div style="display:flex; justify-content:space-between; gap:12px; align-items:center;">
                  <div style="font-weight:700;">{{ CM.genCandidatesHeading }}</div>
                  <div style="color:#999;">{{ filteredHistoryCandidates.length }}{{ CM.countSuffix }}</div>
                </div>
                <div style="margin-top:10px;">
                  <div v-if="filteredHistoryCandidates.length === 0" style="color:#999;">{{ CM.genCandidatesEmpty }}</div>
                  <div
                    v-else
                    v-for="h in filteredHistoryCandidates"
                    :key="h.id"
                    class="zt-item"
                    :class="{ active: String(h.id) === String(selectedHistoryId) }"
                    @click="selectHistoryForGenerate(h)"
                  >
                    <div class="t">{{ h.file_name }}</div>
                    <div class="s">{{ breadcrumb(h.menu_structure) || CM.dash }}</div>
                    <div class="s" style="margin-top:4px;">{{ h.created_at || '-' }}</div>
                  </div>
                </div>
              </div>

              <div class="zt-panel" style="margin-top:12px;">
                <div style="font-weight:700;">{{ CM.casesForShot }}</div>
                <div class="zt-scroll" style="margin-top:10px;">
                  <div v-if="selectedHistoryCases.length === 0" style="color:#999;">{{ CM.noCases }}</div>
                  <div
                    v-for="c in selectedHistoryCases"
                    :key="c.id"
                    class="zt-item"
                    :class="{ active: selectedGeneratedCaseId === String(c.id) }"
                    @click="selectGeneratedCase(c)"
                  >
                    <div class="t">{{ c.title }}</div>
                    <div class="s">
                      <span class="tag" :class="statusTagClass(c.status)">{{ statusLabel(c.status) }}</span>
                      <span style="margin-left:8px; color:#999;">{{ c.last_run_at || '-' }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div class="zt-panel">
              <div style="font-weight:700;">{{ CM.actions }}</div>
              <div style="margin-top:6px; color:#666; font-size:12px;">
                {{ CM.generatedCountPrefix }}<b>{{ selectedHistoryCases.length }}</b>{{ CM.countSuffix }}
              </div>
              <div style="margin-top:10px; display:flex; gap:12px; flex-wrap:wrap;">
                <button class="btn btn-primary" @click="generateCases" :disabled="!selectedHistoryId || isPageBusy">
                  {{ isGenerating ? CM.generating : CM.generateCases }}
                </button>
                <button class="btn btn-default" @click="cancelGeneratingCases" :disabled="!isGenerating">
                  {{ CM.cancelGen }}
                </button>
              </div>
              <div style="margin-top:10px; color:#999; font-size:12px;">
                {{ CM.genHint }}
              </div>
              <div class="gen-chat-wrap">
                <div class="gen-chat-head">
                  <span>{{ CM.aiChatTitle }}</span>
                  <button class="btn btn-default btn-mini" @click="clearGenerateLogs" :disabled="isGenerating">{{ CM.clear }}</button>
                </div>
                <div class="gen-chat-body">
                  <div v-if="generateLogs.length === 0" class="gen-chat-empty">{{ CM.genChatEmpty }}</div>
                  <div
                    v-for="item in generateLogs"
                    :key="item.id"
                    class="gen-chat-item"
                    :class="[`gen-chat-item--${item.role}`]"
                  >
                    <div class="gen-chat-meta">{{ item.phase }} {{ CM.dot }} {{ roleLabel(item.role) }}</div>
                    <pre class="gen-chat-text">{{ item.text }}</pre>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="card" v-else-if="activeTab === 'create'">
          <div class="zt-title">{{ CM.createTitle }}</div>
          <div style="display:flex; gap:12px; flex-wrap:wrap; margin-top:12px;">
            <select class="input" v-model="selectedHistoryId" style="max-width: 520px;">
              <option value="">{{ CM.selectScreenshot }}</option>
              <option v-for="h in filteredHistoriesAll" :key="h.id" :value="String(h.id)">
                {{ h.created_at }} - {{ h.file_name }}
              </option>
            </select>
            <button class="btn btn-primary" @click="openCreateForSelected" :disabled="!selectedHistoryId || isPageBusy">{{ CM.newCase }}</button>
          </div>
          <div style="margin-top:10px; color:#999; font-size:12px;">
            {{ CM.createHint }}
          </div>
        </div>

        <div class="card" v-else>
          <div class="zt-title">{{ CM.libraryTitle }}</div>
          <div class="exec-filter-block">
            <div class="exec-filter-label">{{ CM.colStatus }}</div>
            <div class="exec-pill-row">
              <button type="button" class="exec-pill" :class="{ 'exec-pill--active': !filterStatus }" @click="filterStatus = ''">{{ CM.all }}</button>
              <button type="button" class="exec-pill" :class="{ 'exec-pill--active': filterStatus === 'draft' }" @click="filterStatus = 'draft'">{{ CM.notRun }}</button>
              <button type="button" class="exec-pill" :class="{ 'exec-pill--active': filterStatus === 'pass' }" @click="filterStatus = 'pass'">{{ CM.pass }}</button>
              <button type="button" class="exec-pill" :class="{ 'exec-pill--active': filterStatus === 'fail' }" @click="filterStatus = 'fail'">{{ CM.fail }}</button>
              <button type="button" class="exec-pill" :class="{ 'exec-pill--active': filterStatus === 'blocked' }" @click="filterStatus = 'blocked'">{{ CM.blocked }}</button>
            </div>
          </div>
          <div class="exec-filter-block">
            <div class="exec-filter-label">{{ CM.filterPriorityLabel }}</div>
            <div class="exec-pill-row">
              <button type="button" class="exec-pill" :class="{ 'exec-pill--active': !filterPriority }" @click="filterPriority = ''">{{ CM.priorityAll }}</button>
              <button type="button" class="exec-pill exec-pill--p0" :class="{ 'exec-pill--active': filterPriority === 'P0' }" @click="filterPriority = 'P0'">P0</button>
              <button type="button" class="exec-pill exec-pill--p1" :class="{ 'exec-pill--active': filterPriority === 'P1' }" @click="filterPriority = 'P1'">P1</button>
              <button type="button" class="exec-pill exec-pill--p2" :class="{ 'exec-pill--active': filterPriority === 'P2' }" @click="filterPriority = 'P2'">P2</button>
              <button type="button" class="exec-pill exec-pill--p3" :class="{ 'exec-pill--active': filterPriority === 'P3' }" @click="filterPriority = 'P3'">P3</button>
            </div>
          </div>
          <div class="zt-filterbar">
            <input class="input exec-search" v-model="keyword" :placeholder="CM.searchPlaceholder" />
          </div>
          <div class="zt-tablewrap">
            <table class="table">
              <thead>
                <tr>
                  <th style="width:90px;">ID</th>
                  <th>{{ CM.colTitle }}</th>
                  <th style="width:120px;">{{ CM.colStatus }}</th>
                  <th style="width:88px;">{{ CM.colPriority }}</th>
                  <th style="width:180px;">{{ CM.colLastRun }}</th>
                  <th style="width:260px;">{{ CM.colActions }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="c in libraryList" :key="c.id">
                  <td>{{ c.id }}</td>
                  <td>
                    <div style="font-weight:600;">{{ c.title }}</div>
                    <div style="color:#666; font-size:12px; margin-top:4px;">{{ CM.screenshotId }}{{ c.history_id || '-' }}</div>
                  </td>
                  <td><span class="tag" :class="statusTagClass(c.status)">{{ statusLabel(c.status) }}</span></td>
                  <td><span class="tag" :class="priorityTagClass(c.priority)">{{ priorityLabel(c.priority) }}</span></td>
                  <td>{{ c.last_run_at || '-' }}</td>
                  <td>
                    <div style="display:flex; gap:8px; flex-wrap:wrap;">
                      <button class="btn btn-default" @click="openEdit(c)" :disabled="isPageBusy">{{ CM.edit }}</button>
                      <button class="btn btn-default" @click="openExecute(c)" :disabled="isPageBusy">{{ CM.run }}</button>
                      <button class="btn btn-danger" @click="deleteCase(c)" :disabled="isPageBusy">{{ CM.del }}</button>
                    </div>
                  </td>
                </tr>
                <tr v-if="libraryList.length === 0">
                  <td colspan="6" style="text-align:center; color:#999;">{{ CM.noData }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </div>

    <div class="modal-mask" v-if="editorOpen" @click.self="closeEditor">
      <div class="modal card editor-case-modal">
        <div class="editor-case-head">
          <div class="editor-case-head-main">
            <h2 class="editor-case-title">{{ editForm.id ? CM.modalEdit : CM.modalNew }}</h2>
            <p class="editor-case-sub">{{ CM.editorSubHint }}</p>
          </div>
          <button type="button" class="btn btn-default editor-case-close" @click="closeEditor" :disabled="isPageBusy">{{ CM.close }}</button>
        </div>

        <div class="editor-case-body">
          <div class="form-group editor-field-tight">
            <label class="editor-label">{{ CM.colTitle }}</label>
            <input class="input editor-input" v-model="editForm.title" />
          </div>
          <div class="form-group editor-field-tight">
            <label class="editor-label">{{ CM.preconditions }}</label>
            <textarea class="editor-textarea-pre" v-model="editForm.preconditions" :placeholder="CM.preconditionsPh" rows="3"></textarea>
          </div>

          <div class="editor-steps-panel">
            <div class="editor-steps-panel-head">
              <span class="editor-steps-panel-title">{{ CM.stepsLabel }}</span>
              <span class="editor-steps-panel-tip">{{ CM.editorStepsTip }}</span>
            </div>
            <div class="zt-tablewrap editor-steps-wrap">
              <table class="table execute-table editor-steps-table">
                <thead>
                  <tr>
                    <th class="editor-th-index">{{ CM.stepIndexCol }}</th>
                    <th>{{ CM.stepCol }}</th>
                    <th>{{ CM.expectedCol }}</th>
                    <th class="editor-th-actions">{{ CM.editStepActions }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, ri) in editStepRows" :key="'es-' + ri" class="editor-step-row">
                    <td class="editor-step-idx-cell">
                      <span class="editor-step-badge">{{ ri + 1 }}</span>
                    </td>
                    <td class="editor-step-cell"><textarea v-model="row.step" class="editor-step-ta" rows="2" :placeholder="CM.editorStepPh"></textarea></td>
                    <td class="editor-step-cell"><textarea v-model="row.expected" class="editor-step-ta" rows="2" :placeholder="CM.editorExpectedPh"></textarea></td>
                    <td class="editor-step-actions">
                      <button
                        type="button"
                        class="btn btn-editor-remove"
                        :disabled="editStepRows.length <= 1 || isPageBusy"
                        @click="removeEditStep(ri)"
                      >
                        {{ CM.editRemoveStep }}
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <button type="button" class="btn editor-add-step" :disabled="isPageBusy" @click="addEditStep">{{ CM.editAddStep }}</button>
          </div>
        </div>

        <div class="editor-case-foot">
          <button type="button" class="btn btn-primary" @click="saveCase" :disabled="isPageBusy">{{ isSaving ? CM.saving : CM.save }}</button>
          <button type="button" class="btn btn-default" @click="closeEditor" :disabled="isPageBusy">{{ CM.cancel }}</button>
        </div>
      </div>
    </div>

    <div class="modal-mask" v-if="generatedPreviewOpen && selectedGeneratedCase" @click.self="closeGeneratedPreview">
      <div class="modal card editor-case-modal">
        <div class="editor-case-head">
          <div class="editor-case-head-main">
            <h2 class="editor-case-title">{{ CM.previewEditTitle }}</h2>
            <p class="editor-case-idline">{{ CM.caseIdPrefix }}{{ selectedGeneratedCase.id }}</p>
          </div>
          <button type="button" class="btn btn-default editor-case-close" @click="closeGeneratedPreview" :disabled="isInlineCaseSaving">{{ CM.close }}</button>
        </div>

        <div class="editor-case-body">
          <div class="form-group editor-field-tight">
            <label class="editor-label">{{ CM.colTitle }}</label>
            <input v-model="inlineCaseForm.title" class="input editor-input" />
          </div>
          <div class="form-group editor-field-tight">
            <label class="editor-label">{{ CM.preconditions }}</label>
            <textarea v-model="inlineCaseForm.preconditions" class="editor-textarea-pre" rows="3" />
          </div>

          <div class="editor-steps-panel">
            <div class="editor-steps-panel-head">
              <span class="editor-steps-panel-title">{{ CM.stepsLabel }}</span>
              <span class="editor-steps-panel-tip">{{ CM.editorStepsTip }}</span>
            </div>
            <div class="zt-tablewrap editor-steps-wrap">
              <table class="table execute-table editor-steps-table">
                <thead>
                  <tr>
                    <th class="editor-th-index">{{ CM.stepIndexCol }}</th>
                    <th>{{ CM.stepCol }}</th>
                    <th>{{ CM.expectedCol }}</th>
                    <th class="editor-th-actions">{{ CM.editStepActions }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, ri) in inlineEditStepRows" :key="'is-' + ri" class="editor-step-row">
                    <td class="editor-step-idx-cell">
                      <span class="editor-step-badge">{{ ri + 1 }}</span>
                    </td>
                    <td class="editor-step-cell"><textarea v-model="row.step" class="editor-step-ta" rows="2" :placeholder="CM.editorStepPh"></textarea></td>
                    <td class="editor-step-cell"><textarea v-model="row.expected" class="editor-step-ta" rows="2" :placeholder="CM.editorExpectedPh"></textarea></td>
                    <td class="editor-step-actions">
                      <button
                        type="button"
                        class="btn btn-editor-remove"
                        :disabled="inlineEditStepRows.length <= 1 || isInlineCaseSaving"
                        @click="removeInlineEditStep(ri)"
                      >
                        {{ CM.editRemoveStep }}
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <button type="button" class="btn editor-add-step" :disabled="isInlineCaseSaving" @click="addInlineEditStep">{{ CM.editAddStep }}</button>
          </div>
        </div>

        <div class="editor-case-foot editor-case-foot--wrap">
          <button type="button" class="btn btn-primary" :disabled="isInlineCaseSaving" @click="saveSelectedGeneratedCase">
            {{ isInlineCaseSaving ? CM.saving : CM.saveChanges }}
          </button>
          <button type="button" class="btn btn-default" :disabled="isInlineCaseSaving" @click="resetInlineCaseEditor">{{ CM.reset }}</button>
          <button type="button" class="btn btn-default" :disabled="isInlineCaseSaving" @click="openExecute(selectedGeneratedCase)">{{ CM.run }}</button>
          <button type="button" class="btn btn-default" :disabled="isInlineCaseSaving" @click="closeGeneratedPreview">{{ CM.cancel }}</button>
        </div>
      </div>
    </div>

    <div class="modal-mask" v-if="executeOpen" @click.self="closeExecute">
      <div class="modal card execute-modal">
        <div class="execute-head" style="display:flex; justify-content: space-between; align-items:center; gap:12px;">
          <div style="font-weight:700;">{{ CM.execModalTitle }}</div>
          <button class="btn btn-default" @click="closeExecute" :disabled="isRunning">{{ CM.close }}</button>
        </div>
        <div class="execute-body" style="margin-top: 12px;">
          <div class="execute-title" style="font-weight: 600;">{{ CM.titlePrefix }}{{ executing?.title || '-' }}</div>
          <div style="margin-top:8px; color:#444;">
            <b>{{ CM.prePrefix }}</b>{{ executing?.preconditions || CM.dash }}
          </div>

          <div class="zt-tablewrap" style="margin-top:12px; max-height: 42vh;">
            <table class="table execute-table">
              <thead>
                <tr>
                  <th style="width:70px;">#</th>
                  <th>{{ CM.stepCol }}</th>
                  <th>{{ CM.expectedCol }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in executeStepRows" :key="row.idx">
                  <td>{{ row.idx }}</td>
                  <td>{{ row.step }}</td>
                  <td>{{ row.expected }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="execute-conclusion">
            <div style="font-weight:700;">{{ CM.conclusion }}</div>
            <div class="form-group" style="margin-top: 10px;">
              <label>{{ CM.testResult }}</label>
              <select class="input" v-model="runStatus">
                <option value="pass">{{ CM.pass }}</option>
                <option value="fail">{{ CM.fail }}</option>
                <option value="blocked">{{ CM.blocked }}</option>
                <option value="draft">{{ CM.notRun }}</option>
              </select>
            </div>
            <div class="form-group">
              <label>{{ CM.actualSituation }}</label>
              <textarea v-model="runNotes" :placeholder="CM.runNotesPh" rows="6"></textarea>
            </div>
            <div class="form-group execute-attachments">
              <label>{{ CM.runAttachLabel }}</label>
              <div style="display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin-top:6px;">
                <input
                  ref="runAttachInputRef"
                  type="file"
                  accept="image/*"
                  multiple
                  class="execute-attach-input"
                  @change="onRunAttachPicked"
                />
                <button type="button" class="btn btn-default" :disabled="isRunning || isUploadingRunAttach" @click="triggerRunAttachPick">
                  {{ isUploadingRunAttach ? CM.runAttachUploading : CM.runAttachPick }}
                </button>
              </div>
              <div style="color:#888; font-size:12px; margin-top:4px;">{{ CM.runAttachHint }}</div>
              <div v-if="runAttachments.length" class="execute-attach-grid">
                <div v-for="(att, ai) in runAttachments" :key="ai + '-' + att.file_url" class="execute-attach-card">
                  <a :href="resolveAttachUrl(att.file_url)" target="_blank" rel="noopener noreferrer" class="execute-attach-thumb-wrap">
                    <img :src="resolveAttachUrl(att.file_url)" :alt="att.original_name || 'screenshot'" class="execute-attach-thumb" />
                  </a>
                  <div class="execute-attach-meta">
                    <span class="execute-attach-name" :title="att.original_name">{{ att.original_name || att.file_url }}</span>
                    <div class="execute-attach-actions">
                      <a :href="resolveAttachUrl(att.file_url)" target="_blank" rel="noopener noreferrer">{{ CM.runAttachOpen }}</a>
                      <button type="button" class="btn btn-default execute-attach-rm" @click="removeRunAttachment(ai)" :disabled="isRunning">{{ CM.runAttachRemove }}</button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="execute-foot" style="display:flex; gap:12px;">
          <button class="btn btn-primary" @click="submitRun" :disabled="isRunning">{{ isRunning ? CM.submitting : CM.save }}</button>
          <button class="btn btn-default" @click="closeExecute" :disabled="isRunning">{{ CM.cancel }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
import { useSystemStore } from '../stores/system';
import { useAuthStore } from '../stores/auth';
import TreeNode from './TreeNode.vue';
import { useUiDialog } from '../composables/useUiDialog';
import { listHistory } from '../api/history';
import { listSystems } from '../api/systems';
import { createCase, deleteCaseById, listCases, updateCase } from '../api/cases';
import { uploadAsset } from '../api/upload';
import { sseUrlWithAuth } from '../api/http';
import { CM } from './caseManagementStrings.js';
import {
  historySystemKey,
  buildSystemLabelMap,
  parseRowSystemId,
  rowBelongsToSystemId,
} from '../utils/systemMenuTree.js';

const props = defineProps({
  initialTab: { type: String, default: 'preview' },
  onlyExecution: { type: Boolean, default: false },
});

const systemStore = useSystemStore();
const authStore = useAuthStore();

const history = ref([]);
const cases = ref([]);
/** ???????????????? id ? ??? */
const registrySystems = ref([]);

const allowedTabs = ['preview', 'generate', 'create', 'library'];
// ????????? props ?? activeTab??? onlyExecution ? true ????????
const activeTab = ref('preview');
const onlyExecution = computed(() => !!props.onlyExecution);

watch(
  [() => props.onlyExecution, () => props.initialTab],
  () => {
    if (props.onlyExecution) {
      activeTab.value = 'preview';
    } else {
      const t = allowedTabs.includes(props.initialTab) ? props.initialTab : 'preview';
      activeTab.value = t;
    }
  },
  { immediate: true },
);

const collapsedKeys = ref(new Set());
const selectedPath = ref([]);

const selectedHistoryId = ref('');
const isGenerating = ref(false);
const selectedGeneratedCaseId = ref('');
const generatedPreviewOpen = ref(false);
const inlineCaseForm = ref({ title: '', preconditions: '' });
const isInlineCaseSaving = ref(false);
const isPageBusy = computed(() => isGenerating.value || isSaving.value || isInlineCaseSaving.value);
const generateLogs = ref([]);
const generatingCanceled = ref(false);
const currentGenerateEventSource = ref(null);
let generateLogSeq = 0;

const filterStatus = ref('');
const filterPriority = ref('');
const keyword = ref('');
const treeKeyword = ref('');

const editorOpen = ref(false);
const executeOpen = ref(false);
const executing = ref(null);

const editForm = ref({ id: null, title: '', preconditions: '', history_id: '' });
/** ???????????????? + ???? */
const editStepRows = ref([{ step: '', expected: '' }]);
const inlineEditStepRows = ref([{ step: '', expected: '' }]);
const isSaving = ref(false);

const isRunning = ref(false);
const runStatus = ref('pass');
const runNotes = ref('');
const runAttachments = ref([]);
const runAttachInputRef = ref(null);
const isUploadingRunAttach = ref(false);
const { alertDialog, confirmDialog } = useUiDialog();
const executeStepRows = computed(() => {
  const steps = Array.isArray(executing.value?.steps) ? executing.value.steps : [];
  const per = Array.isArray(executing.value?.step_expected) ? executing.value.step_expected : [];
  const globalExp = String(executing.value?.expected || '').trim() || '-';
  if (!steps.length) return [{ idx: 1, step: '-', expected: globalExp }];
  return steps.map((s, i) => {
    const one = String(per[i] != null ? per[i] : '').trim();
    return { idx: i + 1, step: String(s || '-'), expected: one || globalExp };
  });
});

const caseToEditRows = (c) => {
  const steps = Array.isArray(c?.steps) ? c.steps.map((s) => String(s || '').trim()).filter(Boolean) : [];
  let per = Array.isArray(c?.step_expected) ? c.step_expected.map((x) => String(x ?? '')) : [];
  while (per.length < steps.length) per.push('');
  if (per.length > steps.length) per = per.slice(0, steps.length);
  const globalExp = String(c?.expected || '').trim();
  if (steps.length && per.every((e) => !String(e).trim())) {
    if (globalExp) per = steps.map(() => globalExp);
  } else if (steps.length > 1 && globalExp) {
    const parts = globalExp.split(/\n+/).map((s) => s.trim()).filter(Boolean);
    for (let i = 0; i < steps.length; i++) {
      if (!String(per[i] || '').trim() && parts[i]) per[i] = parts[i];
    }
  }
  if (!steps.length) return [{ step: '', expected: globalExp }];
  return steps.map((step, i) => ({ step, expected: String(per[i] ?? '') }));
};

const rowsToCasePayload = (rows) => {
  const pairs = (Array.isArray(rows) ? rows : [])
    .map((r) => ({
      s: String(r?.step || '').trim(),
      e: String(r?.expected || '').trim(),
    }))
    .filter((p) => p.s);
  const steps = pairs.map((p) => p.s);
  const step_expected = pairs.map((p) => p.e);
  const expected = step_expected.filter(Boolean).join('\n');
  return { steps, step_expected, expected };
};

const addEditStep = () => {
  editStepRows.value = [...editStepRows.value, { step: '', expected: '' }];
};

const removeEditStep = (ri) => {
  if (editStepRows.value.length <= 1) return;
  editStepRows.value = editStepRows.value.filter((_, i) => i !== ri);
};

const addInlineEditStep = () => {
  inlineEditStepRows.value = [...inlineEditStepRows.value, { step: '', expected: '' }];
};

const removeInlineEditStep = (ri) => {
  if (inlineEditStepRows.value.length <= 1) return;
  inlineEditStepRows.value = inlineEditStepRows.value.filter((_, i) => i !== ri);
};

const fetchHistory = async () => {
  const params = {};
  if (systemStore.systemId != null && systemStore.systemId !== '') params.system_id = systemStore.systemId;
  const data = await listHistory(params);
  history.value = (Array.isArray(data) ? data : []).map((r) => ({
    ...r,
    created_at: r.created_at || r.operation_time || '',
  }));
};

const fetchCases = async () => {
  const params = {};
  if (systemStore.systemId != null && systemStore.systemId !== '') params.system_id = systemStore.systemId;
  const data = await listCases(params);
  cases.value = Array.isArray(data) ? data : [];
};

const refreshAll = async () => {
  await Promise.all([fetchHistory(), fetchCases()]);
};

const activeScopeSystemId = computed(() => {
  const raw = systemStore.systemId;
  if (raw == null || raw === '') return null;
  const n = Number(raw);
  return Number.isNaN(n) ? null : n;
});

const historyFullById = computed(() => {
  const m = new Map();
  for (const h of Array.isArray(history.value) ? history.value : []) m.set(Number(h.id), h);
  return m;
});

const scopedHistory = computed(() => {
  const list = Array.isArray(history.value) ? history.value : [];
  const sid = activeScopeSystemId.value;
  return list.filter((h) => rowBelongsToSystemId(h, sid));
});

const scopedCases = computed(() => {
  const list = Array.isArray(cases.value) ? cases.value : [];
  const sid = activeScopeSystemId.value;
  const hm = historyFullById.value;
  return list.filter((c) => {
    if (sid == null) return true;
    const cn = parseRowSystemId(c);
    if (cn !== null) return cn === sid;
    const hid = Number(c?.history_id || 0);
    if (!hid) return false;
    const h = hm.get(hid);
    return h ? rowBelongsToSystemId(h, sid) : false;
  });
});

const breadcrumb = (menuStructure) => {
  return (Array.isArray(menuStructure) ? menuStructure : []).map((x) => x.name).filter(Boolean).join(' / ');
};

const treeRootsAll = computed(() => {
  const base = scopedHistory.value;
  const historyMap = new Map();
  for (const h of base) historyMap.set(Number(h.id), h);

  const caseList = scopedCases.value;
  const caseCountMap = new Map();
  const caseTotalBySk = new Map();
  for (const c of caseList) {
    const hid = Number(c?.history_id || 0);
    if (!hid) continue;
    const h = historyMap.get(hid);
    if (!h) continue;
    const sk = historySystemKey(h);
    caseTotalBySk.set(sk, (caseTotalBySk.get(sk) || 0) + 1);
    const ms = Array.isArray(h.menu_structure) ? h.menu_structure : [];
    const names = ms.map((x) => x?.name).filter(Boolean);
    let p = [];
    for (const name of names) {
      p = [...p, name];
      const k = `${sk}::${p.join('>>')}`;
      caseCountMap.set(k, (caseCountMap.get(k) || 0) + 1);
    }
  }

  const skSet = new Set(base.map((r) => historySystemKey(r)));
  const showLayer = skSet.size > 1;
  const labelMap = buildSystemLabelMap(base, registrySystems.value);
  const collapsed = collapsedKeys.value;
  const rootMap = new Map();

  const sortRec = (nodes) => {
    nodes.sort((a, b) => a.label.localeCompare(b.label));
    for (const n of nodes) sortRec(n.children);
  };

  if (!base.length) return [];

  if (showLayer) {
    const systemNodes = new Map();
    const menuNodeMap = new Map();
    for (const sk of skSet) {
      const lab = labelMap.get(sk);
      const sysKey = `sys:${sk}`;
      const node = {
        key: sysKey,
        label: lab,
        path: [lab],
        depth: 0,
        count: caseTotalBySk.get(sk) || 0,
        children: [],
        collapsed: collapsed.has(sysKey),
      };
      systemNodes.set(sk, node);
      rootMap.set(sysKey, node);
    }
    for (const r of base) {
      const sk = historySystemKey(r);
      const sysNode = systemNodes.get(sk);
      const ms = Array.isArray(r.menu_structure) ? r.menu_structure : [];
      const names = ms.map((x) => x.name).filter(Boolean);
      let path = [];
      let parent = sysNode;
      for (const name of names) {
        path = [...path, name];
        const mk = `${sk}::${path.join('>>')}`;
        let node = menuNodeMap.get(mk);
        if (!node) {
          const lab = labelMap.get(sk);
          node = {
            key: mk,
            label: name,
            path: [lab, ...path],
            depth: path.length,
            count: caseCountMap.get(mk) || 0,
            children: [],
            collapsed: collapsed.has(mk),
          };
          menuNodeMap.set(mk, node);
          if (!parent.children.find((c) => c.key === node.key)) parent.children.push(node);
        }
        parent = node;
      }
    }
    const roots = Array.from(rootMap.values());
    sortRec(roots);
    return roots;
  }

  const onlySk = [...skSet][0];
  const nodeMap = new Map();
  const ensureNode = (pathParts) => {
    const key = `${onlySk}::${pathParts.join('>>')}`;
    if (nodeMap.has(key)) return nodeMap.get(key);
    const node = {
      key,
      label: pathParts[pathParts.length - 1],
      depth: pathParts.length - 1,
      path: pathParts,
      count: caseCountMap.get(key) || 0,
      children: [],
      collapsed: collapsed.has(key),
    };
    nodeMap.set(key, node);
    return node;
  };

  for (const r of base) {
    const ms = Array.isArray(r.menu_structure) ? r.menu_structure : [];
    const names = ms.map((x) => x.name).filter(Boolean);
    let path = [];
    for (const name of names) {
      path = [...path, name];
      const node = ensureNode(path);
      node.collapsed = collapsed.has(node.key);
      if (path.length === 1) rootMap.set(node.key, node);
      else {
        const parent = ensureNode(path.slice(0, -1));
        if (!parent.children.find((c) => c.key === node.key)) parent.children.push(node);
      }
    }
  }

  const roots = Array.from(rootMap.values());
  sortRec(roots);
  return roots;
});

const filterTreeNodes = (nodes, kw) => {
  if (!kw) return nodes;
  const out = [];
  for (const node of nodes) {
    const children = filterTreeNodes(Array.isArray(node.children) ? node.children : [], kw);
    const labelHit = String(node.label || '').toLowerCase().includes(kw);
    const pathHit = Array.isArray(node.path) && node.path.join(' / ').toLowerCase().includes(kw);
    if (labelHit || pathHit || children.length > 0) {
      out.push({ ...node, children });
    }
  }
  return out;
};

const displayTreeRootsAll = computed(() => {
  const kw = String(treeKeyword.value || '').trim().toLowerCase();
  return filterTreeNodes(treeRootsAll.value, kw);
});

function toggleNode(key) {
  const s = new Set(collapsedKeys.value);
  if (s.has(key)) s.delete(key);
  else s.add(key);
  collapsedKeys.value = s;
}
function selectPath(path) {
  selectedPath.value = path;
}
function clearPath() {
  selectedPath.value = [];
  collapsedKeys.value = new Set();
}

watch(
  () => systemStore.systemId,
  () => {
    clearPath();
  },
);

const historyById = computed(() => {
  const m = new Map();
  for (const h of scopedHistory.value) m.set(Number(h.id), h);
  return m;
});

const showMenuSystemLayer = computed(() => {
  const s = new Set();
  for (const h of scopedHistory.value) s.add(historySystemKey(h));
  return s.size > 1;
});

const systemLabelByKey = computed(() => buildSystemLabelMap(scopedHistory.value, registrySystems.value));

const matchesSelectedPath = (h) => {
  if (!selectedPath.value.length) return true;
  const ms = Array.isArray(h?.menu_structure) ? h.menu_structure : [];
  const names = ms.map((x) => x?.name).filter(Boolean);
  if (showMenuSystemLayer.value) {
    const lab = systemLabelByKey.value.get(historySystemKey(h));
    if (selectedPath.value[0] !== lab) return false;
    const rest = selectedPath.value.slice(1);
    if (!rest.length) return true;
    for (let i = 0; i < rest.length; i++) if (names[i] !== rest[i]) return false;
    return true;
  }
  for (let i = 0; i < selectedPath.value.length; i++) if (names[i] !== selectedPath.value[i]) return false;
  return true;
};

const filteredHistoriesAll = computed(() => scopedHistory.value.filter(matchesSelectedPath));
const filteredHistoryCandidates = computed(() =>
  filteredHistoriesAll.value.filter((h) => String(h.vector_built_at || '').trim()),
);
const selectedHistoryRecord = computed(() => {
  const hid = Number(selectedHistoryId.value || 0);
  if (!hid) return null;
  return filteredHistoryCandidates.value.find((h) => Number(h.id) === hid) || null;
});

const selectHistoryForGenerate = (h) => {
  const hid = Number(h?.id || 0);
  if (!hid) return;
  selectedHistoryId.value = String(hid);
};

const filteredCasesByMenu = computed(() => {
  // Filter cases by selected menu path using history_id->history.menu_structure
  const list = scopedCases.value;
  return list.filter((c) => {
    const hid = c.history_id;
    if (!hid) return !selectedPath.value.length; // only show unbound cases when no menu filter
    const h = historyById.value.get(Number(hid));
    if (!h) return false;
    return matchesSelectedPath(h);
  });
});

const normalizeCasePriority = (raw) => {
  const s = String(raw || 'P2').trim().toUpperCase();
  return /^P[0-3]$/.test(s) ? s : 'P2';
};

const applySearchFilter = (list) => {
  let out = list.slice();
  if (filterStatus.value) out = out.filter((c) => c.status === filterStatus.value);
  if (filterPriority.value) {
    const want = filterPriority.value;
    out = out.filter((c) => normalizeCasePriority(c.priority) === want);
  }
  if (keyword.value.trim()) {
    const k = keyword.value.trim().toLowerCase();
    out = out.filter((c) => String(c.title || '').toLowerCase().includes(k));
  }
  return out;
};

const clearExecutionFilters = () => {
  filterStatus.value = '';
  filterPriority.value = '';
};

const previewList = computed(() => applySearchFilter(filteredCasesByMenu.value));
const libraryList = computed(() => applySearchFilter(filteredCasesByMenu.value));

const selectedHistoryCases = computed(() => {
  const hid = Number(selectedHistoryId.value || 0);
  if (!hid) return [];
  return scopedCases.value.filter((c) => Number(c.history_id || 0) === hid);
});
const selectedGeneratedCase = computed(() => {
  const cid = Number(selectedGeneratedCaseId.value || 0);
  if (!cid) return null;
  return selectedHistoryCases.value.find((c) => Number(c.id) === cid) || null;
});

watch(
  filteredHistoryCandidates,
  (list) => {
    const arr = Array.isArray(list) ? list : [];
    if (!arr.length) {
      selectedHistoryId.value = '';
      return;
    }
    const current = Number(selectedHistoryId.value || 0);
    const exists = arr.some((x) => Number(x.id) === current);
    if (!exists) selectedHistoryId.value = String(arr[0].id);
  },
  { immediate: true },
);

const hydrateInlineCaseEditor = (c) => {
  inlineCaseForm.value = {
    title: String(c?.title || ''),
    preconditions: String(c?.preconditions || ''),
  };
  inlineEditStepRows.value = caseToEditRows(c);
};

const selectGeneratedCase = (c) => {
  if (!c || c.id == null) return;
  selectedGeneratedCaseId.value = String(c.id);
  hydrateInlineCaseEditor(c);
  generatedPreviewOpen.value = true;
};

const resetInlineCaseEditor = () => {
  if (!selectedGeneratedCase.value) return;
  hydrateInlineCaseEditor(selectedGeneratedCase.value);
};

const closeGeneratedPreview = () => {
  generatedPreviewOpen.value = false;
};

watch(
  selectedHistoryCases,
  (list) => {
    const arr = Array.isArray(list) ? list : [];
    if (!arr.length) {
      selectedGeneratedCaseId.value = '';
      generatedPreviewOpen.value = false;
      inlineCaseForm.value = { title: '', preconditions: '' };
      inlineEditStepRows.value = [{ step: '', expected: '' }];
      return;
    }
    const current = Number(selectedGeneratedCaseId.value || 0);
    const hit = arr.find((x) => Number(x.id) === current);
    if (hit) {
      hydrateInlineCaseEditor(hit);
      return;
    }
    selectedGeneratedCaseId.value = String(arr[0].id);
    hydrateInlineCaseEditor(arr[0]);
  },
  { immediate: true },
);

const beep = () => {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const o = ctx.createOscillator();
    const g = ctx.createGain();
    o.type = 'sine';
    o.frequency.value = 880;
    g.gain.value = 0.05;
    o.connect(g);
    g.connect(ctx.destination);
    o.start();
    setTimeout(() => { o.stop(); ctx.close(); }, 120);
  } catch (_) {}
};

const roleLabel = (role) => {
  if (role === 'user') return '\u7528\u6237';
  if (role === 'assistant') return 'AI';
  return '\u7cfb\u7edf';
};

const pushGenerateLog = (role, text, phase = '\u6d41\u7a0b') => {
  const s = String(text || '').trim();
  if (!s) return;
  generateLogSeq += 1;
  generateLogs.value.push({
    id: `${Date.now()}-${generateLogSeq}`,
    role: role || 'system',
    phase: String(phase || '\u6d41\u7a0b'),
    text: s,
  });
};

const clearGenerateLogs = () => {
  generateLogs.value = [];
};

const cancelGeneratingCases = () => {
  if (!isGenerating.value) return;
  generatingCanceled.value = true;
  try {
    if (currentGenerateEventSource.value) {
      currentGenerateEventSource.value.close();
      currentGenerateEventSource.value = null;
    }
  } catch {
    // ignore
  }
  pushGenerateLog('system', '\u5df2\u53d6\u6d88\u672c\u6b21\u751f\u6210\u8bf7\u6c42\u3002', '\u6d41\u7a0b');
};

const runGeneratePhaseSse = ({ force = false, phase = '\u9996\u6b21\u751f\u6210' } = {}) =>
  new Promise((resolve, reject) => {
    const hid = Number(selectedHistoryId.value || 0);
    if (!hid) {
      reject(new Error('\u672a\u9009\u62e9\u622a\u56fe\u8bb0\u5f55'));
      return;
    }
    let url = `/api/cases/generate/sse?history_id=${hid}&force=${force ? 1 : 0}&phase=${encodeURIComponent(phase)}`;
    if (systemStore.systemId != null && systemStore.systemId !== '') url += `&system_id=${systemStore.systemId}`;
    url = sseUrlWithAuth(url);
    const es = new EventSource(url);
    currentGenerateEventSource.value = es;
    let done = false;

    es.addEventListener('phase', (ev) => {
      try {
        const d = JSON.parse(ev.data || '{}');
        pushGenerateLog('system', `\u5f00\u59cb\uff1a${d.phase || phase}`, d.phase || phase);
      } catch {
        pushGenerateLog('system', `\u5f00\u59cb\uff1a${phase}`, phase);
      }
    });

    es.addEventListener('log', (ev) => {
      try {
        const d = JSON.parse(ev.data || '{}');
        const msg = String(d.msg || '');
        if (msg.includes('\u89e3\u6790\u8865\u5f55\u4fe1\u606f') || msg.includes('\u5df2\u8bc6\u522b\u6309\u94ae')) return;
        pushGenerateLog('system', msg, d.phase || phase);
      } catch {
        // ignore
      }
    });

    es.addEventListener('scope', (ev) => {
      try {
        const d = JSON.parse(ev.data || '{}');
        const p = d.phase || phase;
        const st = String(d.scope_text || '').trim();
        const head = d.has_overall_analysis
          ? '\u3010\u7528\u4f8b\u751f\u6210\u8303\u56f4\u8bc4\u4f30\u3011\uff08\u5df2\u57fa\u4e8e\u603b\u4f53\u5206\u6790 / \u4e3b\u5206\u6790\u7d20\u6750\uff09'
          : '\u3010\u7528\u4f8b\u751f\u6210\u8303\u56f4\u8bc4\u4f30\u3011\uff08\u603b\u4f53\u5206\u6790\u672a\u586b\uff0c\u4f9d\u5206\u9879\u62fc\u63a5\u7d20\u6750\u63a8\u65ad\uff09';
        pushGenerateLog('assistant', st ? `${head}\n\n${st}` : head, p);
      } catch {
        // ignore
      }
    });

    es.addEventListener('dialog', (ev) => {
      try {
        const d = JSON.parse(ev.data || '{}');
        const p = d.phase || phase;
        if (d.event === 'ai_request') {
          const text = d.prompt_preview
            ? `\u63d0\u793a\u8bcd\u6458\u8981\uff1a\n${d.prompt_preview}`
            : (d.msg || '\u53d1\u9001 AI \u8bf7\u6c42');
          pushGenerateLog('user', text, p);
          return;
        }
        if (d.event === 'ai_response') {
          const text = d.response_preview
            ? `\u6a21\u578b\u56de\u590d\u6458\u8981\uff1a\n${d.response_preview}`
            : (d.msg || '\u6536\u5230 AI \u56de\u590d');
          pushGenerateLog('assistant', text, p);
          return;
        }
        pushGenerateLog('system', d.msg || '\u6536\u5230\u8fc7\u7a0b\u4e8b\u4ef6', p);
      } catch {
        // ignore
      }
    });

    es.addEventListener('need_confirm', (ev) => {
      try {
        const d = JSON.parse(ev.data || '{}');
        pushGenerateLog(
          'system',
          d.message || '\u68c0\u6d4b\u5230\u5df2\u6709\u7528\u4f8b\uff0c\u9700\u786e\u8ba4\u662f\u5426\u8986\u76d6\u63d2\u5165\u3002',
          d.phase || phase,
        );
      } catch {
        pushGenerateLog('system', '\u68c0\u6d4b\u5230\u5df2\u6709\u7528\u4f8b\uff0c\u9700\u786e\u8ba4\u662f\u5426\u8986\u76d6\u63d2\u5165\u3002', phase);
      }
    });

    es.addEventListener('error', (ev) => {
      try {
        const d = JSON.parse(ev.data || '{}');
        pushGenerateLog('system', `\u9519\u8bef\uff1a${d.error || '\u670d\u52a1\u7aef\u5f02\u5e38'}`, d.phase || phase);
      } catch {
        pushGenerateLog('system', '\u9519\u8bef\uff1a\u670d\u52a1\u7aef\u5f02\u5e38', phase);
      }
    });

    es.addEventListener('done', (ev) => {
      done = true;
      try {
        const d = JSON.parse(ev.data || '{}');
        if (d.ok) {
          const repl = Number(d.replaced_count || 0);
          const extra = repl ? `\uff0c\u66ff\u6362\u65e7\u7528\u4f8b ${repl} \u6761` : '';
          pushGenerateLog(
            'assistant',
            `\u672c\u9636\u6bb5\u5b8c\u6210\uff1a\u65b0\u589e ${Number(d.inserted_count || 0)} \u6761${extra}`,
            d.phase || phase,
          );
        }
        if (currentGenerateEventSource.value === es) currentGenerateEventSource.value = null;
        es.close();
        resolve(d);
      } catch (e) {
        if (currentGenerateEventSource.value === es) currentGenerateEventSource.value = null;
        es.close();
        reject(e);
      }
    });

    es.onerror = () => {
      if (done) return;
      if (currentGenerateEventSource.value === es) currentGenerateEventSource.value = null;
      es.close();
      if (generatingCanceled.value) {
        resolve({ ok: false, cancelled: true, phase });
        return;
      }
      reject(new Error('SSE \u8fde\u63a5\u5f02\u5e38\u6216\u670d\u52a1\u7aef\u6267\u884c\u5931\u8d25'));
    };
  });

const generateCases = async () => {
  if (!selectedHistoryId.value) return;
  isGenerating.value = true;
  generatingCanceled.value = false;
  clearGenerateLogs();
  const selected = filteredHistoryCandidates.value.find((x) => String(x.id) === String(selectedHistoryId.value));
  const moduleName = selected?.file_name || `\u622a\u56fe ${selectedHistoryId.value}`;
  pushGenerateLog('user', `\u8bf7\u4e3a\u300c${moduleName}\u300d\u751f\u6210\u6d4b\u8bd5\u7528\u4f8b\u3002`, '\u9996\u6b21\u751f\u6210');
  try {
    const first = await runGeneratePhaseSse({ force: false, phase: '\u9996\u6b21\u751f\u6210' });
    if (first?.cancelled) return;
    if (first?.need_confirm) {
      beep();
      isGenerating.value = false;
      await nextTick();
      const confirmed = await confirmDialog(
        first.message || '\u5df2\u751f\u6210\u8fc7\uff0c\u662f\u5426\u5220\u9664\u5e76\u91cd\u65b0\u751f\u6210\uff1f',
        { title: '\u8bf7\u786e\u8ba4\u64cd\u4f5c' },
      );
      pushGenerateLog(
        'user',
        confirmed
          ? '\u786e\u8ba4\uff1a\u6267\u884c\u4e8c\u6b21\u63d2\u5165\uff08\u8986\u76d6\u65e7\u7528\u4f8b\uff09'
          : '\u53d6\u6d88\uff1a\u4e0d\u6267\u884c\u4e8c\u6b21\u63d2\u5165',
        '\u4e8c\u6b21\u786e\u8ba4\u63d2\u5165',
      );
      if (!confirmed) {
        await alertDialog('\u4f60\u5df2\u53d6\u6d88\u63d2\u5165\uff0c\u5f53\u524d\u672a\u5199\u5165\u65b0\u7684\u751f\u6210\u7ed3\u679c\u3002');
        return;
      }
      isGenerating.value = true;
      const second = await runGeneratePhaseSse({ force: true, phase: '\u4e8c\u6b21\u786e\u8ba4\u63d2\u5165' });
      if (second?.cancelled) return;
      if (!second?.ok) {
        throw new Error(second?.error || '\u4e8c\u6b21\u63d2\u5165\u5931\u8d25');
      }
    } else if (!first?.ok) {
      throw new Error(first?.error || '\u751f\u6210\u5931\u8d25');
    }
    await Promise.all([fetchCases(), fetchHistory()]);
    filterStatus.value = '';
    keyword.value = '';
    if (!onlyExecution.value) activeTab.value = 'library';
    await alertDialog('\u5df2\u751f\u6210\u7528\u4f8b\uff08\u5df2\u5207\u5230\u7528\u4f8b\u5e93\uff09');
  } catch (e) {
    console.error(e);
    pushGenerateLog('system', `\u6d41\u7a0b\u7ec8\u6b62\uff1a${e.message || e}`, '\u6d41\u7a0b');
    await alertDialog(`\u751f\u6210\u5931\u8d25: ${e.message}`);
  } finally {
    currentGenerateEventSource.value = null;
    isGenerating.value = false;
    generatingCanceled.value = false;
  }
};

const statusTagClass = (s) => {
  if (s === 'pass') return 'tag-success';
  if (s === 'fail') return 'tag-danger';
  if (s === 'blocked') return 'tag-warning';
  return 'tag-info';
};

const priorityLabel = (p) => normalizeCasePriority(p);

const priorityTagClass = (p) => {
  const x = normalizeCasePriority(p);
  if (x === 'P0') return 'tag-danger';
  if (x === 'P1') return 'tag-warning';
  if (x === 'P2') return 'tag-info';
  return 'tag-priority-p3';
};

const executorDisplay = (c) => {
  const n = String(c?.executor_name || '').trim();
  if (n) return n;
  return CM.dash;
};

const normalizeRunAttachmentsFromCase = (c) => {
  const raw = c?.run_attachments;
  if (!Array.isArray(raw)) return [];
  const out = [];
  for (const it of raw) {
    if (typeof it === 'string') {
      const u = it.trim();
      if (u) out.push({ file_url: u, original_name: '', uploaded_at: '' });
      continue;
    }
    if (!it || typeof it !== 'object') continue;
    const fu = String(it.file_url || it.url || '').trim();
    if (!fu) continue;
    out.push({
      file_url: fu,
      original_name: String(it.original_name || it.name || '').slice(0, 256),
      uploaded_at: String(it.uploaded_at || it.created_at || '').slice(0, 64),
    });
  }
  return out;
};

const resolveAttachUrl = (fileUrl) => {
  const u = String(fileUrl || '');
  if (!u) return '';
  if (/^https?:\/\//i.test(u)) return u;
  let origin = '';
  try {
    origin =
      typeof import.meta !== 'undefined' && import.meta.env?.VITE_API_ORIGIN
        ? String(import.meta.env.VITE_API_ORIGIN).replace(/\/$/, '')
        : '';
  } catch {
    origin = '';
  }
  return origin ? `${origin}${u}` : u;
};

const triggerRunAttachPick = () => {
  try {
    runAttachInputRef.value?.click();
  } catch {
    // ignore
  }
};

const onRunAttachPicked = async (e) => {
  const input = e?.target;
  const files = input?.files ? Array.from(input.files) : [];
  if (input) input.value = '';
  if (!files.length) return;
  const maxExtra = 30 - runAttachments.value.length;
  if (maxExtra <= 0) {
    await alertDialog(CM.runAttachMaxTip);
    return;
  }
  const slice = files.slice(0, maxExtra);
  isUploadingRunAttach.value = true;
  try {
    for (const f of slice) {
      const data = await uploadAsset(f);
      runAttachments.value.push({
        file_url: data.file_url,
        original_name: data.original_name || f.name,
        uploaded_at: data.uploaded_at || '',
      });
    }
  } catch (err) {
    console.error(err);
    await alertDialog(err?.message || String(err));
  } finally {
    isUploadingRunAttach.value = false;
  }
};

const removeRunAttachment = (index) => {
  const next = runAttachments.value.filter((_, i) => i !== index);
  runAttachments.value = next;
};

const statusLabel = (s) => {
  if (s === 'pass') return '\u901a\u8fc7';
  if (s === 'fail') return '\u5931\u8d25';
  if (s === 'blocked') return '\u963b\u585e';
  if (s === 'draft') return '\u672a\u6267\u884c';
  return String(s || '\u672a\u6267\u884c');
};

const openCreateForSelected = () => {
  if (!selectedHistoryId.value) return;
  editorOpen.value = true;
  editForm.value = { id: null, title: '', preconditions: '', history_id: String(selectedHistoryId.value) };
  editStepRows.value = [{ step: '', expected: '' }];
};

const openEdit = (c) => {
  editorOpen.value = true;
  editForm.value = {
    id: c.id,
    title: c.title || '',
    preconditions: c.preconditions || '',
    history_id: c.history_id ? String(c.history_id) : '',
  };
  editStepRows.value = caseToEditRows(c);
};

const closeEditor = () => { editorOpen.value = false; };

const saveCase = async () => {
  isSaving.value = true;
  try {
    const { steps, step_expected, expected } = rowsToCasePayload(editStepRows.value);
    const payload = {
      title: editForm.value.title,
      preconditions: editForm.value.preconditions,
      steps,
      step_expected,
      expected,
      history_id: editForm.value.history_id ? Number(editForm.value.history_id) : null,
    };
    if (systemStore.systemId != null && systemStore.systemId !== '') payload.system_id = systemStore.systemId;

    if (editForm.value.id) {
      await updateCase(editForm.value.id, payload);
    } else {
      await createCase(payload);
    }
    await fetchCases();
    closeEditor();
    await alertDialog('\u4fdd\u5b58\u6210\u529f');
  } catch (e) {
    console.error(e);
    await alertDialog(`\u4fdd\u5b58\u5931\u8d25: ${e.message}`);
  } finally {
    isSaving.value = false;
  }
};

const saveSelectedGeneratedCase = async () => {
  const current = selectedGeneratedCase.value;
  if (!current || current.id == null) return;
  isInlineCaseSaving.value = true;
  try {
    const { steps, step_expected, expected } = rowsToCasePayload(inlineEditStepRows.value);
    const payload = {
      title: String(inlineCaseForm.value.title || '').trim(),
      preconditions: String(inlineCaseForm.value.preconditions || '').trim(),
      steps,
      step_expected,
      expected,
      history_id: current.history_id ? Number(current.history_id) : null,
    };
    await updateCase(current.id, payload);
    await fetchCases();
    await alertDialog('\u5f53\u524d\u7528\u4f8b\u5df2\u4fdd\u5b58');
  } catch (e) {
    console.error(e);
    await alertDialog(`\u4fdd\u5b58\u5931\u8d25: ${e.message}`);
  } finally {
    isInlineCaseSaving.value = false;
  }
};

const deleteCase = async (c) => {
  if (
    !(await confirmDialog('\u786e\u5b9a\u5220\u9664\u8be5\u7528\u4f8b\u5417\uff1f\n\u5220\u9664\u540e\u65e0\u6cd5\u6062\u590d\u3002', {
      title: '\u8bf7\u786e\u8ba4\u64cd\u4f5c',
      confirmText: '\u5220\u9664',
      cancelText: '\u53d6\u6d88',
    }))
  )
    return;
  await deleteCaseById(c.id);
  await fetchCases();
};

const openExecute = (c) => {
  executing.value = c;
  runStatus.value = c.status || 'pass';
  runNotes.value = c.run_notes || '';
  runAttachments.value = normalizeRunAttachmentsFromCase(c);
  executeOpen.value = true;
};
const closeExecute = () => {
  executeOpen.value = false;
  executing.value = null;
  runNotes.value = '';
  runAttachments.value = [];
};

const submitRun = async () => {
  if (!executing.value) return;
  isRunning.value = true;
  try {
    const now = new Date().toLocaleString();
    const exName = String(authStore.displayName || '').trim().slice(0, 128);
    const payload = {
      status: runStatus.value,
      run_notes: runNotes.value,
      last_run_at: now,
      executor_name: exName,
      run_attachments: runAttachments.value.map((a) => ({
        file_url: a.file_url,
        original_name: a.original_name || '',
        uploaded_at: a.uploaded_at || '',
      })),
    };
    const uid = authStore.user?.id;
    if (uid != null && uid !== '') {
      const n = Number(uid);
      if (!Number.isNaN(n)) payload.executor_id = n;
    }
    await updateCase(executing.value.id, payload);
    await fetchCases();
    closeExecute();
    await alertDialog('\u5df2\u8bb0\u5f55\u6267\u884c\u7ed3\u679c');
  } catch (e) {
    console.error(e);
    await alertDialog(`\u63d0\u4ea4\u5931\u8d25: ${e.message}`);
  } finally {
    isRunning.value = false;
  }
};

onMounted(async () => {
  try {
    try {
      registrySystems.value = await listSystems();
    } catch {
      registrySystems.value = [];
    }
    await refreshAll();
  } catch (e) {
    console.error(e);
  }
});

onUnmounted(() => {
  try {
    if (currentGenerateEventSource.value) currentGenerateEventSource.value.close();
  } catch {
    // ignore
  }
  currentGenerateEventSource.value = null;
});
</script>

<style scoped>
.case-mgmt {
  max-width: 100%;
  min-height: 0;
}

.case-mgmt-hero {
  margin-bottom: 16px;
}

.case-mgmt-page-header {
  margin-bottom: 14px;
  padding-bottom: 2px;
}

.zt-tabbar {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  padding-top: 4px;
  border-top: 1px solid #f0f0f0;
}

.zt-tabbar-spacer {
  flex: 1;
  min-width: 8px;
}
.zt-tab { padding: 8px 12px; border-radius: 8px; border: 1px solid #e6e6e6; background:#fff; cursor:pointer; }
.zt-tab.active { background: #1677ff; border-color: #1677ff; color:#fff; }

.zt-layout { display:grid; grid-template-columns: 320px 1fr; gap: 16px; margin-top: 12px; }
.zt-side { position: sticky; top: 12px; align-self: start; z-index: 2; }
.zt-tree { max-height: 520px; overflow:auto; border: 1px solid #eee; border-radius: 8px; padding: 8px; background: #fafafa; margin-top: 8px; }
.tree-search { margin-top: 8px; }
.selected-path-tip { margin-top: 6px; margin-bottom: 10px; padding: 8px 10px; border-radius: 8px; background: #f0f7ff; color:#1677ff; font-size:12px; border: 1px solid #d6e9ff; }

.zt-main { min-width: 0; }
.zt-title { font-weight: 800; font-size: 16px; }
.zt-metrics { display:grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; margin-top: 12px; }
.zt-metric { border:1px solid #eee; border-radius: 10px; padding: 10px; background:#fafafa; }
.zt-metric .k { color:#666; font-size: 12px; }
.zt-metric .v { font-weight: 800; font-size: 18px; margin-top: 6px; }

.zt-metrics--clickable .zt-metric {
  cursor: pointer;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
}
.zt-metrics--clickable .zt-metric:hover {
  border-color: #91caff;
  background: #f5faff;
}
.zt-metrics--clickable .zt-metric:focus-visible {
  outline: 2px solid #1677ff;
  outline-offset: 2px;
}
.zt-metric--active {
  border-color: #1677ff !important;
  background: #e6f4ff !important;
  box-shadow: 0 0 0 1px rgba(22, 119, 255, 0.25);
}

.exec-filter-block {
  margin-top: 14px;
}
.exec-filter-label {
  font-size: 12px;
  font-weight: 600;
  color: #666;
  margin-bottom: 8px;
}
.exec-pill-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.exec-pill {
  padding: 6px 12px;
  border-radius: 999px;
  border: 1px solid #e0e0e0;
  background: #fff;
  font-size: 13px;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease, color 0.15s ease;
}
.exec-pill:hover {
  border-color: #91caff;
  background: #f5faff;
}
.exec-pill--active {
  border-color: #1677ff;
  background: #1677ff;
  color: #fff;
}
.exec-pill--active.exec-pill--p0,
.exec-pill--active.exec-pill--p1,
.exec-pill--active.exec-pill--p2,
.exec-pill--active.exec-pill--p3 {
  color: #fff;
}
.exec-pill.exec-pill--p0:not(.exec-pill--active) {
  border-color: #ffccc7;
  color: #cf1322;
}
.exec-pill.exec-pill--p1:not(.exec-pill--active) {
  border-color: #ffe58f;
  color: #d48806;
}
.exec-pill.exec-pill--p2:not(.exec-pill--active) {
  border-color: #91d5ff;
  color: #1677ff;
}
.exec-pill.exec-pill--p3:not(.exec-pill--active) {
  border-color: #d9d9d9;
  color: #595959;
}
.exec-search {
  flex: 1;
  min-width: 180px;
  max-width: 420px;
}
.execute-attach-input {
  position: absolute;
  width: 0;
  height: 0;
  opacity: 0;
  pointer-events: none;
}
.execute-attachments {
  position: relative;
}
.execute-attach-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 10px;
}
.execute-attach-card {
  width: 140px;
  border: 1px solid #e8eaef;
  border-radius: 8px;
  overflow: hidden;
  background: #fafafa;
}
.execute-attach-thumb-wrap {
  display: block;
  aspect-ratio: 4 / 3;
  background: #f0f0f0;
}
.execute-attach-thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.execute-attach-meta {
  padding: 6px 8px;
  font-size: 11px;
}
.execute-attach-name {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #555;
}
.execute-attach-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  margin-top: 4px;
}
.execute-attach-actions a {
  font-size: 11px;
  color: #1677ff;
}
.execute-attach-rm {
  font-size: 11px;
  padding: 2px 8px;
}
.table--exec th,
.table--exec td {
  vertical-align: middle;
}

.cell-executor {
  font-size: 13px;
  color: #334155;
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.zt-filterbar { display:flex; gap: 8px; flex-wrap:wrap; margin-top: 12px; }
.zt-tablewrap { margin-top: 12px; max-height: 62vh; overflow:auto; border: 1px solid #eee; border-radius: 10px; background:#fff; }

.zt-panel { border:1px solid #eee; border-radius: 10px; padding: 12px; background:#fff; }
.zt-scroll { max-height: 56vh; overflow:auto; border: 1px solid #eee; border-radius: 10px; padding: 8px; background:#fafafa; }
.zt-item { border:1px solid #eee; border-radius: 10px; padding: 10px; background:#fff; margin-top: 8px; cursor:pointer; }
.zt-item.active { border-color:#1677ff; box-shadow: 0 0 0 2px rgba(22,119,255,0.15); }
.zt-item .t { font-weight: 700; }
.zt-item .s { color:#666; font-size: 12px; margin-top: 6px; }
.generate-main-col { min-width: 0; }
.case-preview-card {
  margin-top: 12px;
  border: 1px solid #e8eaef;
  border-radius: 10px;
  background: #fafcff;
  padding: 12px;
}
.case-preview-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  font-weight: 700;
}
.case-preview-actions {
  margin-top: 10px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.gen-chat-wrap {
  margin-top: 12px;
  border: 1px solid #e8eaef;
  border-radius: 10px;
  background: #fafbfc;
}
.gen-chat-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 12px;
  border-bottom: 1px solid #e8eaef;
  font-weight: 700;
  font-size: 13px;
}
.btn-mini {
  padding: 3px 8px;
  font-size: 12px;
}
.gen-chat-body {
  max-height: 280px;
  overflow: auto;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.gen-chat-empty {
  color: #999;
  font-size: 12px;
}
.gen-chat-item {
  border-radius: 8px;
  padding: 8px 10px;
  border: 1px solid #e4e7ed;
  background: #fff;
}
.gen-chat-item--user {
  border-color: #b7d8ff;
  background: #f3f8ff;
}
.gen-chat-item--assistant {
  border-color: #cdeec7;
  background: #f6fff4;
}
.gen-chat-meta {
  font-size: 11px;
  color: #666;
  margin-bottom: 6px;
}
.gen-chat-text {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  line-height: 1.45;
  font-family: inherit;
}

:deep(.tree-node) {
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:8px;
  padding:8px 10px;
  border-radius:8px;
  cursor:pointer;
  margin-top:4px;
  border:1px solid transparent;
}
:deep(.tree-node:hover) { background:#f5faff; border-color:#e6f2ff; }
:deep(.tree-node.active) {
  background:#e6f4ff;
  color:#1677ff;
  border-color:#91caff;
  box-shadow: 0 0 0 2px rgba(22,119,255,0.12);
}
:deep(.tree-node.prefixActive) {
  background:#f7fbff;
  border-color:#d6e9ff;
}
:deep(.tree-label) { display:flex; align-items:center; gap:6px; min-width:0; }
:deep(.tree-count) { color:#999; font-size:12px; }

.modal-mask { position: fixed; inset: 0; background: rgba(0,0,0,0.45); display:flex; align-items: center; justify-content: center; padding: 24px; z-index: 60; }
.modal { width: min(1000px, 100%); max-height: 80vh; overflow:auto; }
.execute-modal { max-height: 88vh; overflow: hidden; display:flex; flex-direction:column; }
.execute-head { flex: 0 0 auto; }
.execute-body { flex: 1 1 auto; overflow: auto; min-height: 0; padding-right: 2px; }
.execute-foot { flex: 0 0 auto; margin-top: 12px; padding-top: 8px; border-top: 1px solid #f0f0f0; }
.execute-title { white-space: normal; word-break: break-all; line-height: 1.5; }
.execute-conclusion { margin-top: 12px; border: 1px solid #eee; border-radius: 8px; background:#fafafa; padding: 12px; }
.execute-table td { vertical-align: top; line-height: 1.5; }

.editor-case-modal {
  width: min(1000px, 100%);
  max-height: 88vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  margin-bottom: 0;
  padding: 0;
  border-radius: 12px;
  box-shadow: 0 12px 48px rgba(15, 23, 42, 0.12), 0 0 1px rgba(15, 23, 42, 0.08);
  border: 1px solid #e8eaef;
}

.editor-case-head {
  flex: 0 0 auto;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 22px 16px;
  background: linear-gradient(180deg, #f8fafc 0%, #fff 100%);
  border-bottom: 1px solid #e8eaef;
}

.editor-case-head-main {
  min-width: 0;
}

.editor-case-title {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.02em;
  line-height: 1.3;
}

.editor-case-sub,
.editor-case-idline {
  margin: 6px 0 0;
  font-size: 13px;
  color: #64748b;
  line-height: 1.45;
}

.editor-case-close {
  flex-shrink: 0;
  border-radius: 8px;
  border-color: #e2e8f0;
  color: #475569;
}

.editor-case-body {
  flex: 1 1 auto;
  min-height: 0;
  overflow: auto;
  padding: 18px 22px 8px;
}

.editor-case-body .editor-field-tight {
  margin-bottom: 14px;
}

.editor-case-body .editor-field-muted .editor-label {
  color: #94a3b8;
}

.editor-label {
  display: block;
  margin-bottom: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #334155;
}

.editor-input {
  border-radius: 8px !important;
  border-color: #e2e8f0 !important;
  padding: 10px 12px !important;
  font-size: 14px;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.editor-input:focus {
  border-color: #1677ff !important;
  box-shadow: 0 0 0 3px rgba(22, 119, 255, 0.12) !important;
  outline: none;
}

.editor-textarea-pre {
  width: 100%;
  min-height: 88px;
  resize: vertical;
  padding: 10px 12px;
  font-size: 14px;
  line-height: 1.55;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.editor-textarea-pre:focus {
  border-color: #1677ff;
  box-shadow: 0 0 0 3px rgba(22, 119, 255, 0.12);
  outline: none;
}

.editor-steps-panel {
  margin-top: 4px;
  margin-bottom: 18px;
  padding: 14px 14px 16px;
  background: #f8fafc;
  border: 1px solid #e8eaef;
  border-radius: 12px;
}

.editor-steps-panel-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}

.editor-steps-panel-title {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.editor-steps-panel-tip {
  font-size: 12px;
  color: #64748b;
}

.editor-steps-wrap {
  max-height: 44vh;
  margin-top: 0;
  border-radius: 10px;
  overflow: auto;
  border: 1px solid #e2e8f0;
  background: #fff;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.8);
}

.editor-steps-table {
  margin: 0;
  border-collapse: separate;
  border-spacing: 0;
}

.editor-steps-table thead th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: #f1f5f9;
  color: #475569;
  font-size: 12px;
  font-weight: 600;
  padding: 10px 12px;
  border-bottom: 1px solid #e2e8f0;
  white-space: nowrap;
}

.editor-th-index {
  width: 56px;
  text-align: center;
}

.editor-th-actions {
  width: 84px;
  text-align: center;
}

.editor-step-row {
  transition: background 0.12s ease;
}

.editor-step-row:hover {
  background: #f8fafc;
}

.editor-step-row td {
  padding: 12px 12px;
  border-bottom: 1px solid #f1f5f9;
  vertical-align: top;
}

.editor-step-row:last-child td {
  border-bottom: none;
}

.editor-step-idx-cell {
  text-align: center;
  width: 56px;
}

.editor-step-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 28px;
  height: 28px;
  padding: 0 8px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  color: #1677ff;
  background: #e6f4ff;
  border: 1px solid #bae0ff;
}

.editor-step-cell {
  min-width: 0;
}

.editor-step-ta {
  width: 100%;
  min-height: 56px;
  resize: vertical;
  box-sizing: border-box;
  font-size: 13px;
  line-height: 1.55;
  padding: 8px 10px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.editor-step-ta:hover {
  border-color: #cbd5e1;
}

.editor-step-ta:focus {
  border-color: #1677ff;
  box-shadow: 0 0 0 3px rgba(22, 119, 255, 0.1);
  outline: none;
}

.editor-step-actions {
  text-align: center;
  width: 84px;
}

.btn-editor-remove {
  padding: 6px 10px;
  font-size: 12px;
  border-radius: 8px;
  color: #b91c1c;
  background: #fff;
  border: 1px solid #fecaca;
}

.btn-editor-remove:hover:not(:disabled) {
  background: #fef2f2;
  border-color: #f87171;
}

.btn-editor-remove:disabled {
  opacity: 0.45;
}

.editor-add-step {
  margin-top: 12px;
  border-radius: 8px;
  border: 1px dashed #94a3b8;
  color: #334155;
  background: #fff;
  padding: 8px 16px;
  font-size: 13px;
}

.editor-add-step:hover:not(:disabled) {
  border-color: #1677ff;
  color: #1677ff;
  background: #f0f7ff;
}

.editor-case-foot {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 22px 20px;
  border-top: 1px solid #e8eaef;
  background: #fafbfc;
}

.editor-case-foot--wrap {
  flex-wrap: wrap;
}

.editor-case-foot .btn {
  border-radius: 8px;
  padding: 9px 18px;
}

@media (max-width: 980px) {
  .zt-layout { grid-template-columns: 1fr; }
  .zt-side { position: static; }
  .zt-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
