# LLM Case System

## 项目结构

```
LLM/
├── src/                # 前端代码
│   ├── components/     # 前端组件
│   ├── App.vue         # 主应用组件
│   └── main.js         # 应用入口
├── backend/                    # Python 后端（标准库）
│   ├── simple_server.py
│   └── llm_vision.py           # 可选：DashScope 多模态「深度分析」
│   └── legacy_flask/          # 旧版 Flask+MySQL 程序（保留以备参考）
│       ├── app.py
│       ├── models.py
│       └── create_database.py
├── uploads/            # 上传文件存储目录
├── data/               # 持久化数据（未用 MySQL 时：history.json、cases.json）
├── scripts/            # 启动/维护脚本
│   ├── run_server.bat
├── tests/              # 后端/环境测试脚本
├── package.json        # 前端项目配置
└── README.md           # 项目说明
```

## 后端服务器启动方法

### 使用 Python 标准库服务器（推荐）

1. 打开命令提示符（CMD）
2. 导航到项目目录：
   ```
   cd C:\Users\Administrator\Documents\trae_projects\LLM
   ```
3. 启动服务器：
   ```
   python backend\simple_server.py
   ```
4. 服务器将在 http://localhost:5000 上运行

## 系统记录（用于后续 LLM 测试用例）

- 上传截图成功后，后端会在 `data/history.json` 中持久化一条“系统记录”，并把文件保存到 `uploads/`。
- 文件名解析规则：`系统名称_一级菜单_二级菜单_三级菜单_弹窗.png`（下划线分隔，扩展名可为 png/jpg/webp）
- 你可以在前端的“历史记录”里对系统记录进行 **查看 / 编辑 / 删除**。

## 前端启动方法

1. 打开命令提示符（CMD）
2. 导航到项目目录：
   ```
   cd C:\Users\Administrator\Documents\trae_projects\LLM
   ```
3. 安装依赖：
   ```
   npm install
   ```
4. 启动开发服务器：
   ```
   npm run dev
   ```
5. 在浏览器中打开 http://localhost:3000

## 开发环境推荐启动顺序

1. 先启动后端（任选其一）：
   - `python backend\simple_server.py`
2. 再启动前端：`npm run dev`

## 数据存储（MySQL 与 JSON）

- **未配置 MySQL**：数据仅存于前端可见的 `data/history.json`、`data/cases.json` 与 `uploads/`。
- **配置 MySQL**：在 `config.local.json` 中增加 `mysql` 段（参见 `config.local.example.json`），后端会自动创建本地库 **`llm_case_system`** 及表 **`screenshot_history`**、**`test_cases`**，并将系统记录与用例持久化到 MySQL。
- 建库建表也可单独执行：`python scripts/init_mysql_db.py`（需先配置 `config.local.json` 中的 `mysql`）。

## 目录约定
- 后端默认走 `backend/simple_server.py`，数据落地到 `data/`（或 MySQL 的 `llm_case_system`）与 `uploads/`。
- 旧版 Flask+MySQL 代码已归档到 `backend/legacy_flask/`，当前不启用。
- 启动脚本统一在 `scripts/`，测试脚本在 `tests/`。

## 功能说明

### 后端API

- `GET /` - 服务器状态检查
- `POST /api/upload` - 文件上传接口
- `GET /api/history` - 获取历史记录
- `DELETE /api/history/:id` - 删除历史记录
- `GET /uploads/:filename` - 访问上传的文件

### 前端功能

- 文件上传（支持拖拽）
- 文件名解析生成菜单结构
- 历史记录管理
- 菜单结构预览

## 常见问题解决

### 上传提示后端未运行

1. 检查后端服务器是否已启动
2. 确认服务器运行在 http://localhost:5000
3. 检查防火墙是否阻止了端口访问
4. 尝试使用不同的浏览器

### 文件上传失败

1. 确保文件格式为 .png/.jpg/.webp
2. 确保文件大小不超过 10MB
3. 检查上传目录是否有写入权限
4. 查看服务器日志了解具体错误

### 菜单结构解析错误

确保文件名格式正确：`系统名称_一级菜单_二级菜单_三级菜单_弹窗.png`

## 技术栈

- 前端：Vue 3, Vite
- 后端：Python 标准库 + 可选 MySQL（mysql-connector-python）
- 文件存储：本地 `uploads/`；结构化数据：`data/*.json` 或 MySQL `llm_case_system`

## 注意事项

- 本项目为开发环境，生产环境请配置适当的安全措施
- 上传的文件将存储在 `uploads` 目录中
- 若需使用 MySQL，复制 `config.local.example.json` 为 `config.local.json` 并填写 `mysql` 与 `ocr` 等配置
- **`/api/analyze/{id}` 默认启用 OCR**（依赖 `config.local.json` 的 `ocr` 配置）；若仅需模板分析、不调 OCR，可请求 `?use_ocr=0`
- **分析质量**：在 `config.local.json` 增加 `analysis.llm_vision`（见 `config.local.example.json`），设置 **`enabled: true`** 后，`/api/analyze` 会在「模板 + OCR」之外追加 **多模态深度分析**（默认模型 `qwen-vl-plus`，与 OCR 所用模型独立）。`api_key` 可留空以复用 `ocr.dashscope.api_key`；单次请求可用 `?use_llm=1` 强制开启、`?use_llm=0` 强制关闭
