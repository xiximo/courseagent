# AI 教育顾问 SaaS（CourseAgent）

CourseAgent 是一套可演示的 **AI 教育顾问 SaaS MVP**：在已有 RAG 知识库、多轮对话与 Admin 后台之上，补齐课程 Function Calling Skill、订阅套餐、模拟支付、用量控制与用量看板。教育机构可授权使用同一套对话与资料管理能力。

本仓库同时保留文档解析 / 向量检索基础设施。

## 技术栈

- **后端**：Python 3.11+、FastAPI、SQLAlchemy、PostgreSQL
- **检索**：Docling/PyMuPDF 解析 → 结构切片 → `bge-small-zh-v1.5` Embedding → FAISS / Milvus Lite 混合检索
- **对话**：豆包（火山方舟）LLM；Harness ReAct + OpenAI 风格 Function Calling
- **前端**：React、Vite、TanStack Router、shadcn/ui、recharts
- **部署**：Docker Compose（Postgres + Backend + Web + 可选 Caddy HTTPS）

## 核心能力

1. **RAG 知识库**：上传 PDF → 文本提取 → 可配置切片（大小 / 重叠）→ 向量化 → 检索回答并标注「文档名称 + 章节标题」。知识库外问题统一回复「该问题不在我的知识范围内」。
2. **Agent Skill**：`query_course_detail`（按班型名称查时间/地点/费用/师资/大纲）、`recommend_courses`（按城市 + 时间偏好推荐 1–2 个班型）。参数缺失或目录未命中时降级提示，不编造。
3. **商业化演示**：免费版 50 次对话/月，含知识库与基础型 Agent；专业版无限对话并开放 Harness Agent。升级走 Stripe 测试收银台。
4. **Admin**：课程资料上传/删除/重建索引、对话记录（脱敏 + 时间筛选）、用量统计看板。

## 安装与运行（本地）

### 前置条件

- PostgreSQL（默认库名 `course`，账号见环境变量）
- Node.js 20+、Python 3.11+
- 可选：本机 `backend/models/bge-small-zh-v1.5` 向量模型目录
- 对话需配置豆包 `DOUBAO_API_KEY` / `DOUBAO_ENDPOINT_ID`

### 后端

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # 按需修改 DATABASE_URL 与 LLM 密钥
uvicorn app.main:app --reload --port 8080
```

首次启动会自动建表、写入默认管理员 `admin` / `admin123`（专业版），以及画像演示用户（免费版，密码见用户管理页）。

### 前端

```bash
cd webadmin
npm install
copy .env.example .env   # 默认代理到 http://127.0.0.1:8080
npm run dev
```

浏览器打开 Vite 提示的地址（通常 `http://localhost:5173`），使用管理员或演示用户登录。

### Docker Compose 一键部署

详见 [deploy/README.md](deploy/README.md)。在 `deploy/` 下复制环境文件后执行：

```bash
cd deploy
cp .env.example .env
cp backend.env.example backend.env
docker compose up -d --build
```

评审环境可在约 15 分钟内拉起 Postgres、后端、前端。生产域名与 HTTPS 由 Caddy 处理。

## 环境变量说明

关键项（完整列表见 `backend/.env.example`、`deploy/backend.env.example`）：

| 变量 | 含义 |
| --- | --- |
| `DATABASE_URL` | PostgreSQL 连接串 |
| `JWT_SECRET` | 登录令牌密钥 |
| `INIT_ADMIN_USERNAME` / `INIT_ADMIN_PASSWORD` | 初始管理员 |
| `DOUBAO_API_KEY` / `DOUBAO_ENDPOINT_ID` / `DOUBAO_BASE_URL` | LLM |
| `EMBEDDING_ENABLED` / `EMBEDDING_MODEL` / `EMBEDDING_VECTOR_STORE` | 向量索引 |
| `CHUNK_MAX_CHARS` / `CHUNK_OVERLAP_CHARS` | RAG 切片大小与重叠 |
| `INDEX_AUTO_ON_CHUNK` | 切片后是否自动建索引 |
| `DOCLING_WORKER_*` | 扫描件 PDF 可选解析 Worker |
| `CORS_ORIGINS` | 前端来源 |

## RAG 设计说明

链路：PDF/DOCX/MD → `parser.py` / `pdf_converter.py` 抽 Markdown → `chunker.py` 按章节/条款切分，超长段落按 `CHUNK_MAX_CHARS` 与 `CHUNK_OVERLAP_CHARS` 滑窗 → Embedding 写入 FAISS 或 Milvus Lite → `hybrid_search`（向量 + 关键词）→ `rag.py` 组装上下文，引用取 `display_name` + `position_label`。

文档更新后走 `material_service` pipeline（重新抽取、切片、按附件替换向量）。Admin 也可手动 Reindex。无命中时 Agent 使用固定拒答句，避免编造。

## Agent Skill 设计说明

两个 Skill 以 OpenAI `type: function` 注册到 Harness ReAct：

- **query_course_detail**：必填 `course_name`；返回班型完整字段。缺失参数或目录不存在时返回 `SKILL_FALLBACK`，模型应请用户补充或说明未找到。
- **recommend_courses**：必填 `city`、`time_preference`；返回 1–2 个班型及理由。约束过窄时降级，不编造班型。

班型数据在 `course_catalog.py`（北京/上海线下班、线上直播班、暑期集训班、周末研修班）。资料性问答仍走知识库检索工具。

## 支付流程说明

1. 用户打开「套餐与用量」，对比免费版与专业版。
2. 点击「立即升级」创建 `billing_order`（pending）。
3. 「去 Stripe 测试支付」创建 Checkout Session，跳转 Stripe 托管收银台。
4. 用测试卡 `4242 4242 4242 4242` 付款后，回跳 `/api/v1/billing/stripe/return`，后端向 Stripe 查询 Session 并履约。
5. 订单置为 paid，同租户账号升级为 `pro`。
6. 免费版发送对话时累计 `usage_monthly.chat_count`，达到 50 次返回「已用完，请升级」。

请在 [Stripe Dashboard](https://dashboard.stripe.com/apikeys) 复制测试模式 `sk_test_` 写入 `backend/.env` 的 `STRIPE_SECRET_KEY`。不要提交密钥或账号密码。未配置密钥时仍可用「本地模拟支付」。默认管理员为专业版。

## 演示脚本（约 3 分钟，供录屏）

1. 管理员登录 → 知识库上传/查看 3 份 PDF，说明解析与索引。
2. 对话页问知识库内问题，展示引用（文档名 + 章节）；再问库外问题，确认拒答句。
3. 问「北京线下班详情」「我在上海，只有周末有空」，展示两条 Skill。
4. 用免费演示账号对话至额度提示（或直接说明 50 次上限），进入套餐页走 Stripe 测试支付升级。
5. Admin 查看脱敏会话记录、时间筛选与用量看板。

## AI 辅助代码标注

本轮 SaaS MVP 中，以下模块由 AI 辅助编写并经人工对齐测试单：

- `backend/app/course_agent/course_catalog.py`、`course_skills.py`
- `backend/app/services/billing.py`、`routers/billing.py`、`db/models/billing.py`
- `webadmin/src/features/billing/`、`webadmin/src/features/usage/`
- 根目录 README、`docs/saas-mvp-architecture.md`、`docs/测试记录表.md`

既有 RAG 解析/切片/索引、对话 SSE、知识库 Admin 为原仓库能力，本轮主要做 Skill 接入、切片配置、拒答统一、套餐门控与文档补齐。
