# Course Agent 运行时规格：节点契约 + 执行循环

> 版本：v0.1（设计规格，不绑定现有画布实现）  
> 原则：**画布是运行时唯一控制面**；用户交互必须遵循图定义的规则。  
> 目标：在满足 `需求.md` 身份门禁、资料边界、动态 LLM 生成的前提下，形成可配置、可观测、可验收的顾问 Agent。

---

## 1. 设计目标与非目标

### 1.1 目标

1. **所见即所运行**：修改图上的节点/边/条件/绑库，不改代码即可改变对话行为。
2. **控制与生成分离**：门禁、槽位计数、跳转由确定性规则执行；班型事实、理由、报名信息仅由「检索范围内的资料 + LLM」生成。
3. **资料硬隔离**：任一时刻最多一个 `activeKnowledgeBaseId`；禁止跨身份库检索与兜底。
4. **状态显式**：不依赖「把整段聊天塞进模型」作为唯一记忆；图读写同一份 `SessionState`。
5. **可验收**：每轮可追溯当前节点、出边、KB、命中 chunk、引用。

### 1.2 非目标（v0.1）

- 通用多智能体编排、任意插件市场。
- 开放域 ReAct 在澄清/采集阶段随便调工具。
- 用三套完整子图复制「推荐→追问→报名」（应用 **Scope 策略**，而不是复制整条顾问流程）。

---

## 2. 核心对象

### 2.1 SessionState（工作记忆）

每轮用户消息处理前后，引擎读写同一对象。字段均为显式，禁止用「隐式上下文」代替。

```ts
type Role = "student" | "teacher" | "org"
type RoleStatus = "unknown" | "confirmed"

interface SessionState {
  /** 当前停留的节点 ID */
  currentNodeId: string

  /** 身份 */
  role: Role | null
  roleStatus: RoleStatus

  /** 约束槽位；未填为 null/缺省 */
  constraints: {
    city?: string | null
    date?: string | null
    format?: string | null   // online | offline | either 等，由 SlotFill 配置枚举
    goal?: string | null
  }

  /** 推荐与多轮继承 */
  recommendedCourses: string[]
  lockedCourse: string | null

  /** 知识范围：仅当 roleStatus=confirmed 且经过 Scope 节点后写入 */
  activeKnowledgeBaseId: string | null

  /** 最近一次生成使用的检索痕迹（可观测，可截断存储） */
  lastRetrieval?: {
    knowledgeBaseId: string
    chunkIds: string[]
    query: string
  }

  /** 会话控制标志 */
  flags: {
    awaitingInput: boolean
    lastError?: string | null
  }
}
```

**不变量**

- `roleStatus !== "confirmed"` ⇒ `activeKnowledgeBaseId` 必须为 `null`，且任何节点不得执行检索。
- `lockedCourse` 仅在推荐成功或用户点名班型后设置；「重新开始」必须清空 `constraints / recommendedCourses / lockedCourse / lastRetrieval`，并按图回到入口（见 SessionControl）。
- 机构路径（`role=org`）不得写入学生/教师班型到 `recommendedCourses`（由 Recommend 节点策略约束）。

### 2.2 WorkflowGraph（画布定义）

```ts
interface WorkflowGraph {
  version: "1"
  entryNodeId: string
  nodes: Node[]
  edges: Edge[]
  /** 图级默认：输入长度上限等 */
  policies: {
    maxInputChars: number          // 需求默认 500
    minConstraintsForRecommend: number  // 需求默认 2
  }
}
```

### 2.3 Edge（边）

```ts
interface Edge {
  id: string
  source: string
  target: string
  /** 优先级：同起点多条边时，按 priority 升序匹配，命中第一条即走 */
  priority: number
  /** 条件；缺省表示 always */
  when?: EdgeCondition
  /** 可选：走这条边时写入的确定性补丁（如点击「学生课程」） */
  apply?: StatePatch
}

type EdgeCondition =
  | { type: "always" }
  | { type: "quick_action"; action: string }
  | { type: "role_eq"; role: Role }
  | { type: "role_status"; status: RoleStatus }
  | { type: "constraints_ready"; min: number }  // 有效槽位数 >= min
  | { type: "intent"; intent: Intent }          // 由上一节点输出的结构化意图
  | { type: "state_flag"; path: string; equals: unknown }
  | { type: "and" | "or"; items: EdgeCondition[] }
  | { type: "not"; item: EdgeCondition }

type Intent =
  | "choose_role"
  | "provide_constraint"
  | "ask_recommend"
  | "ask_detail"
  | "ask_enroll"
  | "restart"
  | "list_courses"
  | "out_of_scope"
  | "empty"
  | "too_long"
  | "other"
```

**规则**：边条件只读 `SessionState` + 本轮 `TurnInput`（及上一节点的 `NodeOutput`），不得在匹配阶段调 LLM/检索。

### 2.4 TurnInput / NodeOutput

```ts
interface TurnInput {
  text: string
  quickAction?: string | null
  /** 引擎预处理 */
  meta: {
    isEmpty: boolean
    tooLong: boolean
    charCount: number
  }
}

interface NodeOutput {
  /** 对用户可见的消息；null 表示本节点静默（仅改状态后立即跳转） */
  messages: AssistantMessage[]
  /** 供出边匹配的意图（可选） */
  intent?: Intent
  /** 是否结束本轮（等待用户下一句）；false 则引擎在同轮内继续沿边执行下一节点 */
  waitForUser: boolean
  /** 结构化补丁（已与节点契约校验） */
  statePatch?: StatePatch
  /** 追踪 */
  trace: NodeTrace
}

interface AssistantMessage {
  content: string
  citations?: Citation[]   // 仅检索生成类节点允许非空
  quickActions?: string[]
}

interface Citation {
  document: string
  chapter: string
  attachmentId?: string
  chunkId?: string
}
```

---

## 3. 执行循环（Runtime Loop）

### 3.1 会话创建

1. 加载 Agent 的 `WorkflowGraph`，校验图（见 §6）。
2. 初始化 `SessionState`：`currentNodeId = entryNodeId`，其余为空/默认。
3. **自动执行**入口节点一次（通常 `Entry` 发出欢迎语，`waitForUser=true`）。

### 3.2 每轮用户输入

```
onUserTurn(input):
  preprocess(input) → TurnInput
  // 全局短路（也可建模为挂在入口的高优先级边；规格上允许引擎级策略）
  if input.meta.isEmpty → 固定提示，不推进节点，return
  if input.meta.tooLong → 固定提示，不推进节点，return

  loopBudget = MAX_AUTO_HOPS  // 建议 8，防环
  while loopBudget-- > 0:
    node = graph.nodes[state.currentNodeId]
    output = execute(node, state, input)   // 见各节点契约
    apply(output.statePatch) to state
    emit output.messages
    record output.trace

    if output.waitForUser:
      return

    edge = selectEdge(node.id, state, input, output)
    if edge is null:
      emit 安全兜底（「暂时无法继续，请重新开始」）
      return
    apply(edge.apply) to state
    state.currentNodeId = edge.target
    // 同轮继续：下一节点若需要「本轮用户原文」，仍可读同一 TurnInput
    // 若下一节点是纯模板跳转，可忽略 text

  emit 错误（超过自动跳转上限）
```

### 3.3 关键语义

| 概念 | 含义 |
|------|------|
| **停留（wait）** | 节点产出对用户话术并等待下一句；`currentNodeId` 不变或已更新到自身/下一等待节点 |
| **同轮穿行（auto-hop）** | `waitForUser=false`，按边立刻进下一节点（例如 Scope 绑定后立刻进 Recommend） |
| **边优先于模型自觉** | 模型不得直接改 `currentNodeId`；只能通过 `intent` + 边条件间接跳转 |

### 3.4 出边选择

对 `source = 当前节点` 的边按 `priority` 升序求值，**第一条** `when` 为真的边胜出。  
若存在 `quickAction`，优先匹配 `quick_action` 类条件（仍受 priority 约束）。  
禁止「模型返回 next_node_id」。

---

## 4. 节点类型与契约

每个节点必须声明：

- **读**：允许读取的状态字段  
- **写**：允许写入的状态字段  
- **工具**：是否允许 LLM / 是否允许检索  
- **输出**：消息是否允许带 citations  
- **完成条件**：何时 `waitForUser`、产出何种 `intent`

### 4.1 `entry` — 欢迎与分流（配置型）

| 项 | 契约 |
|----|------|
| 目的 | 说明服务范围；提供三入口快捷操作；可选弱提示 |
| 读 | 无硬依赖 |
| 写 | 默认不写 role（除非边 `apply` 在用户点击时写入） |
| LLM | 禁止 |
| 检索 | 禁止 |
| citations | 禁止 |
| 配置 | `welcomeText`，`quickActions[]`（如：学生课程 / 教师培训 / 平台服务） |
| 行为 | 发出欢迎语；`waitForUser=true`；`intent` 可由点击映射为 `choose_role` |
| 典型出边 | 点击某入口 → `apply: { role, roleStatus: confirmed }` → `identity` 或直接 `scope`；自然语言未点选 → `identity` |

**说明**：点击入口用边的 `apply` **确定性写身份**，避免与后续澄清抢权。若产品要求「点了仍需口头确认」，则点击只写 `role` 候选、`roleStatus=unknown`，由 `identity` 确认。

### 4.2 `identity` — 身份澄清

| 项 | 契约 |
|----|------|
| 目的 | 在 `roleStatus=confirmed` 前不得进入任何检索/推荐节点 |
| 读 | `role`, `roleStatus` |
| 写 | `role`, `roleStatus` |
| LLM | **允许**（轻量分类 + 追问话术）；输出必须结构化 |
| 检索 | **禁止** |
| citations | 禁止 |
| 结构化输出 | `{ role?: Role, confirmed: boolean, reply: string, intent: Intent }` |
| 行为 | `confirmed=true` 才写 `roleStatus=confirmed`；否则追问并 `waitForUser=true` |
| 出边示例 | `role_status=confirmed` → `slot_fill` 或 `scope`；`out_of_scope` → `boundary` |

### 4.3 `slot_fill` — 约束采集

| 项 | 契约 |
|----|------|
| 目的 | 填充 `constraints`；由**规则**判断是否达到 `minConstraintsForRecommend` |
| 读 | `role`, `constraints`, policies |
| 写 | `constraints` 各槽 |
| LLM | **允许**（仅抽槽 + 决定下一追问句）；禁止编造课程事实 |
| 检索 | **禁止** |
| citations | 禁止 |
| 配置 | `slots[]`（name/prompt/required）、`askOneMissingAtATime: boolean` |
| 结构化输出 | `{ patch: Partial<constraints>, reply: string, intent }` |
| 引擎职责 | 合并 patch 后计算有效槽位数；**不得**因模型说「可以推荐了」就跳转 |
| 出边示例 | `constraints_ready` → 下一节点；未就绪 → 自环等待；用户直接追问细节且未推荐 → 可先 `intent=ask_detail` 但边应拦回采集或提示先推荐 |

### 4.4 `scope` — 知识范围绑定（三角色绑库落点）

| 项 | 契约 |
|----|------|
| 目的 | 按 `role` 设置唯一 `activeKnowledgeBaseId` |
| 读 | `role`, `roleStatus` |
| 写 | `activeKnowledgeBaseId` |
| LLM | 禁止 |
| 检索 | 禁止（本节点只绑定，不搜） |
| 配置 | `binding: { student: kbId, teacher: kbId, org: kbId }` |
| 行为 | 若对应 kb 未配置 → 固定错误话术，`waitForUser=true`，不进入生成节点；成功则 `waitForUser=false`，同轮 hop 到生成节点 |
| 不变量 | 离开本节点后，后续检索节点 **只能** 使用 `state.activeKnowledgeBaseId`，忽略其它绑定 |

**画布表达**：可画成三个分支框，每个框只配置一个 kb；运行时仍是同一个 `scope` 节点或三个 `scope` 节点按 `role_eq` 边进入——语义等价，推荐 **一个 scope 节点 + binding 映射**，减少复制。

### 4.5 `rag_recommend` — 推荐生成

| 项 | 契约 |
|----|------|
| 目的 | 基于当前库资料推荐 1–2 个真实班型，理由逐条对应约束 |
| 读 | `role`, `constraints`, `activeKnowledgeBaseId` |
| 写 | `recommendedCourses`, `lockedCourse`（若只推 1 个可直接锁；推 2 个则待用户选择再锁，或锁第一个并允许改选） |
| LLM | **必须** |
| 检索 | **必须**，且仅限 `activeKnowledgeBaseId` |
| citations | **必须**来自本次 hits；禁止写死文档名 |
| 前置断言 | `roleStatus=confirmed` 且 `activeKnowledgeBaseId≠null` 且有效约束 ≥ 阈值；`role=org` 时本节点应改为「平台服务介绍」策略或使用独立 `rag_platform`（见 4.8） |
| 失败 | hits 空或模型无法在资料中找到班型 → 明确资料不足/人工；`citations=[]` |
| `waitForUser` | true |
| 出边 | 用户追问 → `rag_qa`；报名 → `rag_enroll`；重来 → `session_control` |

### 4.6 `rag_qa` — 详情追问

| 项 | 契约 |
|----|------|
| 目的 | 针对 `lockedCourse`（或用户点名班型）回答费用/时间/地点/师资/大纲/物资等 |
| 读 | `lockedCourse`, `recommendedCourses`, `activeKnowledgeBaseId`, 历史轮次由引擎提供摘要 |
| 写 | 可更新 `lockedCourse`（若用户改口点名另一推荐班） |
| LLM | 必须 |
| 检索 | 必须；query = `lockedCourse + userText`（及约束） |
| citations | 必须来自 hits |
| 前置 | 无 `lockedCourse` 且无法从输入解析班型 → 追问聚焦哪一个班，不检索编造 |
| 多轮 | 连续追问不更换 KB、不丢 `lockedCourse`（除非 SessionControl） |

### 4.7 `rag_enroll` — 报名引导

| 项 | 契约 |
|----|------|
| 目的 | 仅提供资料中已有报名方式 |
| 读 | `lockedCourse`, `activeKnowledgeBaseId` |
| 写 | 无必须写字段 |
| LLM | 必须 |
| 检索 | 必须（报名/联系方式相关 query） |
| 禁止 | 虚构链接、电话、余位、截止状态 |
| 无资料 | 说明需人工确认 |

### 4.8 `rag_platform` — 机构/平台（可选独立节点）

与 `rag_recommend` 同族，但策略为：介绍 OPC 平台/会员/合作；**禁止**输出学生/教师班型推荐列表。  
绑定库为素材 C。可用 `role_eq=org` 边进入，避免机构走「班型推荐」节点。

### 4.9 `session_control` — 会话控制

| 项 | 契约 |
|----|------|
| 目的 | 取消/重来/查看所有课程/回菜单 |
| LLM | 默认禁止（列表班型名若需资料，允许一次「目录检索」，仍限 `activeKnowledgeBaseId`；未确认身份则只回入口菜单） |
| 写 | `restart`：清空约束/推荐/锁定/检索痕迹/`activeKnowledgeBaseId`，`role` 策略可配置（清或不清），`currentNodeId` 经边回到 `entry` |
| `list_courses` | 仅列当前身份资料中的班型名 + 引用；不得带费用细节也可，细节应交 `rag_qa` |

### 4.10 `boundary` — 服务边界 / 异常模板

| 项 | 契约 |
|----|------|
| 目的 | 天气等无关问题、跨资料价格混淆提示、模型失败提示 |
| LLM | 禁止（固定模板） |
| 检索 | 禁止 |
| 配置 | 各场景文案 + 返回菜单 quickActions |
| 行为 | 提示后 `waitForUser=true` 或边回 `entry`/`identity` |

### 4.11 （可选）`react_qa` — 仅限分支内追问

若需要多步工具调用，**仅**允许替换 `rag_qa`（或作为其子实现），且工具白名单为：

- `search_active_kb(query)` → 强制使用 `activeKnowledgeBaseId`
- `get_locked_course()`
- `set_locked_course(name)`（name 必须落在推荐列表或检索命中白名单）

**禁止**在 `identity` / `slot_fill` 使用 ReAct。

---

## 5. 推荐参考拓扑（逻辑图，非 UI）

```text
                    ┌─────────┐
                    │  entry  │
                    └────┬────┘
           点击写 role / 自然语言
                    ┌────▼────┐
                    │identity │◄──── 未确认自环
                    └────┬────┘
                   confirmed
                    ┌────▼────┐
                    │slot_fill│◄──── 约束不足自环
                    └────┬────┘
                constraints_ready
                    ┌────▼────┐
                    │  scope  │  binding: A/B/C
                    └────┬────┘
           ┌─────────────┼─────────────┐
           │ role=student│ role=teacher│ role=org
           ▼             ▼             ▼
     rag_recommend  rag_recommend  rag_platform
           │             │             │
           └──────┬──────┘             │
                  ▼                    ▼
               rag_qa ◄──────────（平台追问可复用或独立）
                  ▼
             rag_enroll
                  │
           session_control / boundary 可从多点接入
```

说明：学生/教师可共用同一 `rag_recommend` 节点定义（策略随 role），机构走 `rag_platform`，避免错误推荐班型。

---

## 6. 图校验（保存/发布时）

引擎在保存或启用 Agent 时必须校验：

1. 存在唯一 `entryNodeId`，且可从 entry 到达所有非死节点（或显式标记的可选节点）。
2. 任意 `rag_*` 节点的所有入路边径上，必须经过 `scope`（或等价写入 `activeKnowledgeBaseId` 的节点），且路径上存在 `identity` 确认。
3. `scope.binding` 三个角色至少配置评测所需角色；缺失角色的边不得指向 `rag_*`。
4. 不存在「未确认身份却可到达检索节点」的路径。
5. `slot_fill` 到 `rag_recommend` 的边必须带 `constraints_ready`（或等价）。
6. 无边条件死环且无 `waitForUser` 出口（防止空转）。
7. 节点写字段不得超出契约白名单。

校验失败 → Agent 不得 `active` 对外。

---

## 7. 全局输入与异常策略

| 条件 | 行为 |
|------|------|
| 空输入 | 固定提示重新输入；不执行节点 LLM；不跳转 |
| 超过 `maxInputChars` | 提示精简；不跳转 |
| 特殊符号 | 不崩溃；按文本交给当前等待节点；节点内做安全截断 |
| 模型异常 | 进入 `boundary` 或节点内固定「稍后重试」；状态不损坏；可继续 |
| 跨资料问题（如在学生库问会员价） | 生成节点 system 约束 + 可选 `intent=out_of_scope` 边到 `boundary`；**不得**改绑到素材 C 偷偷回答 |

---

## 8. 可观测性（每轮必记）

```ts
interface NodeTrace {
  nodeId: string
  nodeType: string
  startedAt: string
  endedAt: string
  edgeIdTaken?: string
  stateSnapshot: Pick<SessionState,
    "role" | "roleStatus" | "constraints" | "lockedCourse" | "activeKnowledgeBaseId">
  retrieval?: { kbId: string; query: string; chunkIds: string[] }
  llm?: { model: string; ok: boolean; error?: string }
}
```

管理端预览与正式会话共用同一执行器；区别仅在鉴权与 Agent `status` 门禁。

---

## 9. 与需求七步的映射

| 需求步骤 | 规格节点 |
|----------|----------|
| 1 欢迎与分流 | `entry` + 边 `apply` |
| 2 身份澄清 | `identity` |
| 3 约束采集 | `slot_fill` |
| 4 推荐 | `scope` → `rag_recommend` |
| 5 详情追问 | `rag_qa`（可选 `react_qa`） |
| 6 报名引导 | `rag_enroll` |
| 7 会话控制 | `session_control` + `boundary` |

---

## 10. 实现分期建议（规格落地顺序）

1. **Schema + 校验器 + 执行循环空壳**（节点先只实现 `entry` / `boundary` / `session_control`）。  
2. **`identity` + `slot_fill`**（结构化 LLM，无检索）。  
3. **`scope` + `rag_*`**（单库检索、真实引用、删硬编码班型答案）。  
4. **管理端画布**按本规格重做节点面板（绑定 A/B/C、边条件、话术）。  
5. **验收用例集**挂到 trace 回放。

---

## 11. 验收标准（规格本身）

本规格落地后，应满足：

1. 改 `scope.binding.student` 指向另一已索引库 → 学生推荐内容随之变化，教师/机构不变。  
2. 删掉「身份确认 → scope」的边 → 发布校验失败。  
3. 对话中任意推荐/问答回复的 citations.chunkId 能在当轮 trace.retrieval.chunkIds 中找到。  
4. 代码中不存在按关键词返回整段固定课程费用/时间的答案路径（模板节点除外）。  

---

## 附录：机器可读定义

| 文件 | 说明 |
|------|------|
| [workflow-graph.schema.json](./workflow-graph.schema.json) | WorkflowGraph JSON Schema（draft 2020-12） |
| [workflow-graph.example.json](./workflow-graph.example.json) | 默认顾问拓扑样例（含 A/B/C 绑库占位符） |

---

## 修订记录

| 版本 | 说明 |
|------|------|
| v0.1 | 初稿：节点契约、状态、边条件、执行循环、图校验；不对照旧画布 |
| v0.1.1 | 增补 JSON Schema 与样例图 |)
