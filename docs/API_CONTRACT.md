# API Contract

本文件定义当前项目的后端接口契约（请求方式、请求体、响应结构、错误语义），用于前后端联调与后续迭代约束。

## Base 信息

- 开发环境后端地址：`http://127.0.0.1:5000`
- 统一响应编码：`application/json; charset=utf-8`
- 推荐请求方式：`POST`（读取/新增/修改/删除均可用 POST 风格接口）
- 兼容说明：部分历史 `GET/PUT/DELETE` 端点仍可使用，但新开发建议走本文件中的 POST 接口。

## 通用错误语义

- `400`：请求参数不正确
- `404`：目标资源不存在
- `409`：数据冲突（如文件名重复）
- `5xx`：服务端异常

响应示例：

```json
{ "error": "错误信息" }
```

---

## 1) History（截图历史）

### 1.1 列表

- `POST /api/history/list`
- 请求体（可选）：

```json
{ "id": 12 }
```

- 响应：`HistoryRecord[]`

### 1.2 详情

- `POST /api/history/detail`
- 请求体：

```json
{ "id": 12 }
```

- 响应：`HistoryRecord`

### 1.3 新建

- `POST /api/history/create`
- 请求体：

```json
{
  "file_name": "系统A_一级_二级_三级_弹窗.png",
  "file_url": "/uploads/xxx.png",
  "system_name": "系统A",
  "menu_structure": [{ "level": 1, "name": "一级" }]
}
```

- 响应：`HistoryRecord`

### 1.4 更新

- `POST /api/history/update`
- 请求体（最小）：

```json
{ "id": 12, "analysis": "..." }
```

- 支持字段：`file_name`、`menu_structure`、`analysis`、`analysis_style`、`analysis_content`、`analysis_interaction`、`analysis_data`、`analysis_style_table`、`manual`
- 响应：更新后的 `HistoryRecord`

### 1.5 删除

- `POST /api/history/delete`
- 请求体：

```json
{ "id": 12 }
```

- 响应：

```json
{ "message": "History record deleted successfully" }
```

---

## 2) Cases（测试用例）

### 2.1 列表

- `POST /api/cases/list`
- 请求体（可选）：

```json
{ "history_id": 12 }
```

- 响应：`CaseRecord[]`

### 2.2 详情

- `POST /api/cases/detail`
- 请求体：

```json
{ "id": 101 }
```

- 响应：`CaseRecord`

### 2.3 新建

- `POST /api/cases/create`
- 请求体：

```json
{
  "history_id": 12,
  "title": "登录成功路径",
  "preconditions": "已登录",
  "steps": ["打开页面", "点击按钮"],
  "expected": "操作成功",
  "status": "draft"
}
```

- 响应：新建后的 `CaseRecord`

### 2.4 更新

- `POST /api/cases/update`
- 请求体：

```json
{
  "id": 101,
  "status": "pass",
  "run_notes": "执行通过",
  "last_run_at": "2026-03-24 12:00:00"
}
```

- 响应：更新后的 `CaseRecord`

### 2.5 删除

- `POST /api/cases/delete`
- 请求体：

```json
{ "id": 101 }
```

- 响应：

```json
{ "message": "Case deleted successfully" }
```

---

## 3) 上传与分析

### 3.1 上传截图

- `POST /api/upload`
- Content-Type：`multipart/form-data`
- 表单字段：`file`

响应：`HistoryRecord`（新增记录）

### 3.2 生成分析文本（历史兼容 GET）

- `GET /api/analyze/{history_id}`

响应：

```json
{ "id": 12, "analysis": "..." }
```

### 3.3 OCR 补录建议（历史兼容 GET）

- `GET /api/ocr/manual/{history_id}`

响应重点字段：

- `manual_draft`
- `field_hints`

---

## 4) 需求分析/向量库（POST）

以下为规范端点（与历史端点兼容）：

- `POST /api/requirement/analysis/generate`
- `POST /api/requirement/vector/analyze`
- `POST /api/requirement/network/build`
- `POST /api/requirement/network/search`

### 4.1 需求库生成

- `POST /api/requirement/analysis/generate`
- Query 参数可选：`force=1`、`history_id=12`
- 响应：

```json
{ "ok": true, "total": 1, "generated": 1, "errors": [] }
```

### 4.2 向量分析文本

- `POST /api/requirement/vector/analyze`
- 请求体：

```json
{ "history_id": 12 }
```

- 响应：

```json
{ "ok": true, "history_id": 12, "analysis_result": "..." }
```

### 4.3 构建需求网络

- `POST /api/requirement/network/build`
- 请求体：

```json
{
  "history_id": 12,
  "force": 1,
  "analysis_result_text": "...",
  "unit_limit": 0,
  "embedding_model": ""
}
```

### 4.4 检索需求网络

- `POST /api/requirement/network/search`
- 请求体：

```json
{ "query": "查询条件校验", "top_k": 8, "unit_type": "element", "history_id": 12 }
```

---

## 5) SSE 端点（保持 GET）

当前 SSE 使用 `EventSource`，按浏览器限制仍采用 GET：

- `/api/requirement-analysis/generate/sse`
- `/api/cases/generate/sse`

如需统一为 POST + 流式，可后续升级为 `fetch + ReadableStream`。

---

## 6) 核心数据结构（摘要）

### HistoryRecord

- `id: number`
- `file_name: string`
- `file_url: string`
- `system_name: string`
- `menu_structure: { level: number, name: string }[]`
- `analysis*` 系列字段（文本/结构化）
- `manual: object`

### CaseRecord

- `id: number`
- `history_id: number | null`
- `title: string`
- `preconditions: string`
- `steps: string[]`
- `expected: string`
- `status: "draft" | "pass" | "fail" | "blocked"`
- `run_notes: string`
- `last_run_at: string`
