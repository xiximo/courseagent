import type {
  AttachmentChunks,
  AttachmentExtractedText,
  ChunkSearchResult,
  CourseAgentConfig,
  CourseAgentKnowledgeBase,
  CourseAgentModelProfile,
  CourseAgentSession,
  CourseAgentSummary,
  CourseMaterialDocument,
  CreateCourseAgentInput,
} from '../data/types'
import {
  createInitialSessionState,
  createWelcomeMessage,
  processCourseAgentMessage,
} from '../lib/state-machine'
import { withMockDelay } from '@/lib/is-dev-mock'
import { ApiClientError } from '@/lib/api/client'

const MOCK_AGENTS: CourseAgentConfig[] = [
  {
    agentId: 'agt_summer_camp',
    name: '暑期 AI 课程顾问',
    description: '面向学生/家长、教师与机构的暑期咨询 Agent，基于素材 A/B/C 分库问答。',
    status: 'active',
    agentType: 'workflow',
    model: {
      provider: 'deepseek',
      stream: false,
      modelName: 'deepseek-chat',
      endpointId: '',
      apiKey: '',
      baseUrl: 'https://ark.cn-beijing.volces.com/api/v3',
    },
    stateMachine: [
      { id: 'welcome', label: '欢迎分流', description: '说明服务范围，提供三大入口', enabled: true },
      { id: 'identity', label: '身份澄清', description: '未澄清身份前不得推荐班型', enabled: true },
      { id: 'constraints', label: '约束采集', description: '城市、日期、形式、目标', enabled: true },
      { id: 'recommend', label: '班型推荐', description: '推荐 1—2 个真实班型', enabled: true },
      { id: 'qa', label: '详情追问', description: '关联当前班型 RAG 问答', enabled: true },
      { id: 'enroll', label: '报名引导', description: '仅提供资料中已有报名方式', enabled: true },
    ],
    knowledgeBases: [],
    embed: {
      embedKey: 'emb_demo_7x9k2m',
      allowedOrigins: ['https://example.com', 'http://localhost:5173'],
      theme: 'light',
      position: 'bottom-right',
    },
    conversation: {
      welcomeMessage:
        '您好！我是 AI 课程顾问，可为您提供学生夏令营、教师培训或 OPC 平台服务咨询。',
      systemPrompt: '',
      menuButtons: ['学生课程', '教师培训', '平台服务'],
      resetMessage: '已为您重新开始。',
      emptyInputMessage: '请输入您的问题。',
      tooLongMessage: '输入过长，请精简后重新发送（限 500 字）。',
      outOfScopeMessage: '抱歉，我仅提供课程与平台服务咨询。',
    },
    isDefault: true,
    updatedAt: '2026-07-20T08:00:00Z',
  },
  {
    agentId: 'agt_teacher_only',
    name: '教师研修顾问（草稿）',
    description: '仅教师培训场景的试验 Agent。',
    status: 'draft',
    agentType: 'basic',
    model: {
      provider: 'openai',
      stream: false,
      modelName: 'gpt-4o-mini',
      endpointId: '',
      apiKey: '',
      baseUrl: 'https://ark.cn-beijing.volces.com/api/v3',
    },
    stateMachine: [],
    knowledgeBases: [],
    embed: {
      embedKey: 'emb_draft_teacher',
      allowedOrigins: [],
      theme: 'light',
      position: 'inline',
    },
    conversation: {
      welcomeMessage: '您好，我是教师研修顾问。',
      systemPrompt: '',
      menuButtons: ['教师培训'],
      resetMessage: '已重置。',
      emptyInputMessage: '请输入问题。',
      tooLongMessage: '输入过长。',
      outOfScopeMessage: '超出服务范围。',
    },
    updatedAt: '2026-07-18T12:00:00Z',
  },
]

const sessions = new Map<string, CourseAgentSession>()
const previewSessions = new Map<string, CourseAgentSession>()

const mockDocuments = new Map<string, CourseMaterialDocument[]>()

/** 平台级知识库（与 Agent 解耦） */
let PLATFORM_KNOWLEDGE_BASES: CourseAgentKnowledgeBase[] = MOCK_AGENTS.flatMap(
  (agent) => agent.knowledgeBases
)

/** 平台级模型（与 Agent 解耦）；不自动种子默认模型 */
let PLATFORM_MODELS: CourseAgentModelProfile[] = []

function findPlatformKb(kbId: string): CourseAgentKnowledgeBase {
  const kb = PLATFORM_KNOWLEDGE_BASES.find((item) => item.id === kbId)
  if (!kb) throw new ApiClientError('NOT_FOUND', '知识库不存在')
  return kb
}

function findPlatformModel(modelId: string): CourseAgentModelProfile {
  const model = PLATFORM_MODELS.find((item) => item.id === modelId)
  if (!model) throw new ApiClientError('NOT_FOUND', '模型配置不存在')
  return model
}

function maskSecret(secret: string): string {
  if (!secret) return ''
  if (secret.length <= 4) return '****'
  return `${secret.slice(0, 2)}****${secret.slice(-2)}`
}

function maskProfile(profile: CourseAgentModelProfile): CourseAgentModelProfile {
  const key = profile.apiKey ?? ''
  return {
    ...profile,
    apiKeyConfigured: Boolean(key),
    apiKey: key ? maskSecret(key) : '',
  }
}

function runtimeFromProfile(profile: CourseAgentModelProfile) {
  return {
    provider: profile.provider,
    stream: profile.stream,
    modelName: profile.modelName,
    endpointId: profile.endpointId,
    apiKey: '',
    apiKeyConfigured: profile.apiKeyConfigured ?? Boolean(profile.apiKey),
    baseUrl: profile.baseUrl,
  }
}

function ensureAgentModels(agent: CourseAgentConfig): CourseAgentConfig {
  const models = agent.models ?? []
  const activeId = agent.activeModelId ?? models.find((m) => m.isActive)?.id ?? models[0]?.id
  const active = models.find((m) => m.id === activeId) ?? models[0]
  return {
    ...agent,
    activeModelId: active?.id,
    model: active ? runtimeFromProfile(active) : agent.model,
    models,
  }
}

function findAgent(agentId: string): CourseAgentConfig {
  const index = MOCK_AGENTS.findIndex((a) => a.agentId === agentId)
  if (index < 0) {
    throw new ApiClientError('NOT_FOUND', `Agent ${agentId} 不存在`)
  }
  const normalized = ensureAgentModels(MOCK_AGENTS[index]!)
  MOCK_AGENTS[index] = normalized
  return normalized
}

export async function mockListCourseAgents(): Promise<CourseAgentSummary[]> {
  return withMockDelay(
    MOCK_AGENTS.map(
      ({
        agentId,
        name,
        description,
        status,
        agentType,
        isDefault,
        updatedAt,
      }) => ({
        agentId,
        name,
        description,
        status,
        agentType,
        isDefault: Boolean(isDefault),
        updatedAt,
      })
    )
  )
}

function buildMockAgentConfig(body: CreateCourseAgentInput): CourseAgentConfig {
  const agentId = `agt_${Date.now().toString(36)}`
  const base: CourseAgentConfig = {
    agentId,
    name: body.name,
    description: body.description ?? '',
    status: 'draft',
    agentType: body.agentType,
    model: {
      provider: 'doubao',
      stream: false,
      modelName: 'doubao-seed-2-0-pro-260215',
      endpointId: '',
      apiKey: '',
      baseUrl: 'https://ark.cn-beijing.volces.com/api/v3',
    },
    stateMachine:
      body.agentType === 'workflow'
        ? [
            { id: 'welcome', label: '欢迎分流', description: '说明服务范围', enabled: true },
            { id: 'identity', label: '身份澄清', description: '澄清用户身份', enabled: true },
            { id: 'constraints', label: '约束采集', description: '采集约束条件', enabled: true },
            { id: 'recommend', label: '班型推荐', description: '推荐班型', enabled: true },
            { id: 'qa', label: '详情追问', description: 'RAG 问答', enabled: true },
            { id: 'enroll', label: '报名引导', description: '报名引导', enabled: true },
          ]
        : body.agentType === 'autonomous'
          ? [
              {
                id: 'welcome',
                label: '自主对话',
                description: 'LLM 自主规划多轮回复',
                enabled: true,
              },
            ]
          : [],
    knowledgeBases: [],
    embed: {
      embedKey: `emb_${Date.now().toString(36)}`,
      allowedOrigins: ['http://localhost:5173', 'http://localhost:5174'],
      theme: 'light',
      position: 'bottom-right',
    },
    conversation: {
      welcomeMessage:
        body.agentType === 'basic'
          ? `您好！我是${body.name}，可直接向我提问。`
          : body.agentType === 'autonomous'
            ? `您好！我是${body.name}，将自主理解您的需求并给出建议。`
            : `您好！我是${body.name}，请问需要哪类帮助？`,
      systemPrompt: '',
      menuButtons:
        body.agentType === 'workflow'
          ? ['学生课程', '教师培训', '平台服务']
          : [],
      resetMessage: '已为您重新开始。',
      emptyInputMessage: '请输入您的问题。',
      tooLongMessage: '输入过长，请精简后重新发送（限 500 字）。',
      outOfScopeMessage: '抱歉，我仅提供课程与平台服务咨询。',
    },
    updatedAt: new Date().toISOString(),
  }
  return ensureAgentModels({
    ...base,
    models: [],
    boundModelIds: [],
  })
}

export async function mockCreateCourseAgent(
  body: CreateCourseAgentInput
): Promise<CourseAgentConfig> {
  const agent = buildMockAgentConfig(body)
  if (!MOCK_AGENTS.some((a) => a.isDefault)) {
    agent.isDefault = true
  }
  MOCK_AGENTS.unshift(agent)
  return withMockDelay(agent)
}

export async function mockDeleteCourseAgent(
  agentId: string
): Promise<{ message: string }> {
  const idx = MOCK_AGENTS.findIndex((a) => a.agentId === agentId)
  if (idx < 0) throw new ApiClientError('NOT_FOUND', 'Agent 不存在')
  const wasDefault = Boolean(MOCK_AGENTS[idx]?.isDefault)
  MOCK_AGENTS.splice(idx, 1)
  if (wasDefault && MOCK_AGENTS[0]) {
    MOCK_AGENTS[0] = { ...MOCK_AGENTS[0], isDefault: true }
  }
  return withMockDelay({ message: 'Agent 已删除' })
}

function withMaskedModels(agent: CourseAgentConfig): CourseAgentConfig {
  return {
    ...agent,
    models: (agent.models ?? []).map(maskProfile),
  }
}

export async function mockGetCourseAgent(agentId: string): Promise<CourseAgentConfig> {
  return withMockDelay(withMaskedModels(findAgent(agentId)))
}

export async function mockListModels(
  agentId: string
): Promise<CourseAgentModelProfile[]> {
  const agent = withMaskedModels(findAgent(agentId))
  return withMockDelay(agent.models ?? [])
}

export async function mockListPlatformKnowledgeBases(): Promise<
  CourseAgentKnowledgeBase[]
> {
  return withMockDelay([...PLATFORM_KNOWLEDGE_BASES])
}

export async function mockGetKnowledgeBase(
  kbId: string
): Promise<CourseAgentKnowledgeBase> {
  return withMockDelay(findPlatformKb(kbId))
}

export async function mockListPlatformModels(): Promise<
  CourseAgentModelProfile[]
> {
  return withMockDelay(PLATFORM_MODELS.map(maskProfile))
}

export async function mockUpdateCourseAgent(
  agentId: string,
  patch: Partial<CourseAgentConfig>
): Promise<CourseAgentConfig> {
  const idx = MOCK_AGENTS.findIndex((a) => a.agentId === agentId)
  if (idx < 0) throw new ApiClientError('NOT_FOUND', 'Agent 不存在')
  if (patch.isDefault === true) {
    for (let i = 0; i < MOCK_AGENTS.length; i += 1) {
      MOCK_AGENTS[i] = {
        ...MOCK_AGENTS[i]!,
        isDefault: i === idx,
        updatedAt: new Date().toISOString(),
      }
    }
  } else {
    MOCK_AGENTS[idx] = {
      ...MOCK_AGENTS[idx]!,
      ...patch,
      agentId,
      updatedAt: new Date().toISOString(),
    }
  }
  return withMockDelay(MOCK_AGENTS[idx]!)
}

export async function mockCreateCourseAgentSession(
  agentId: string
): Promise<CourseAgentSession> {
  findAgent(agentId)
  const id = `cas-${Date.now()}`
  const session: CourseAgentSession = {
    id,
    agentId,
    title: '新对话',
    messages: [createWelcomeMessage()],
    state: createInitialSessionState(),
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  }
  sessions.set(id, session)
  return withMockDelay(session, 400)
}

export async function mockCreatePreviewSession(
  agentId: string
): Promise<CourseAgentSession> {
  findAgent(agentId)
  const id = `cap-${Date.now()}`
  const session: CourseAgentSession = {
    id,
    agentId,
    title: '对话预览',
    messages: [createWelcomeMessage()],
    state: { ...createInitialSessionState(), step: 'preview' },
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  }
  previewSessions.set(id, session)
  return withMockDelay(session, 400)
}

async function mockPreviewReply(content: string): Promise<string> {
  const search = await mockSearchKnowledgeChunks({ query: content, mode: 'hybrid' })
  const hits = search.hits.slice(0, 2)
  if (hits.length === 0) {
    return '现有资料中未找到相关信息。请先在知识库上传文档并完成索引。'
  }
  const summary = hits.map((h) => h.content).join(' ')
  return `根据知识库资料：${summary}`
}

export async function mockSendPreviewMessage(
  sessionId: string,
  content: string
): Promise<CourseAgentSession> {
  const session = previewSessions.get(sessionId)
  if (!session) throw new ApiClientError('NOT_FOUND', '会话不存在')

  const trimmed = content.trim()
  if (!trimmed) throw new ApiClientError('EMPTY_INPUT', '请输入您的问题。')

  const now = new Date().toISOString()
  const userMsg = {
    id: `msg-u-${Date.now()}`,
    role: 'user' as const,
    content: trimmed,
    createdAt: now,
  }

  const search = await mockSearchKnowledgeChunks({ query: trimmed, mode: 'hybrid' })
  const citations = search.hits.slice(0, 2).map((hit) => ({
    document: hit.fileName ?? '资料',
    chapter: hit.positionLabel ?? '相关章节',
    attachmentId: hit.attachmentId,
    chunkId: hit.chunkId,
  }))
  const reply = await mockPreviewReply(trimmed)
  const assistantMsg = {
    id: `msg-a-${Date.now()}`,
    role: 'assistant' as const,
    content: reply,
    createdAt: new Date().toISOString(),
    citations,
  }

  const updated: CourseAgentSession = {
    ...session,
    title: session.title === '对话预览' && trimmed.length <= 40 ? trimmed : session.title,
    messages: [...session.messages, userMsg, assistantMsg],
    updatedAt: new Date().toISOString(),
  }
  previewSessions.set(sessionId, updated)
  return withMockDelay(updated, 800)
}

export async function mockResetPreviewSession(
  sessionId: string
): Promise<CourseAgentSession> {
  const session = previewSessions.get(sessionId)
  if (!session) throw new ApiClientError('NOT_FOUND', '会话不存在')
  const updated: CourseAgentSession = {
    ...session,
    title: '对话预览',
    messages: [createWelcomeMessage()],
    updatedAt: new Date().toISOString(),
  }
  previewSessions.set(sessionId, updated)
  return withMockDelay(updated, 400)
}

export async function mockSendCourseAgentMessage(
  sessionId: string,
  content: string
): Promise<CourseAgentSession> {
  const session = sessions.get(sessionId)
  if (!session) throw new ApiClientError('NOT_FOUND', '会话不存在')
  const updated = processCourseAgentMessage(session, content)
  sessions.set(sessionId, updated)
  return withMockDelay(updated, 800)
}

export async function mockResetCourseAgentSession(
  sessionId: string
): Promise<CourseAgentSession> {
  return mockSendCourseAgentMessage(sessionId, '重新开始')
}

export async function mockGetPublicAgentConfig(agentId: string) {
  const agent = findAgent(agentId)
  return withMockDelay({
    agentId: agent.agentId,
    name: agent.name,
    welcomeMessage: agent.conversation.welcomeMessage,
    menuButtons: agent.conversation.menuButtons,
    theme: agent.embed.theme,
  })
}

export function getMockEmbedSnippet(agentId: string): string {
  const agent = MOCK_AGENTS.find((a) => a.agentId === agentId)
  const key = agent?.embed.embedKey ?? 'emb_xxx'
  return `<script
  src="${typeof window !== 'undefined' ? window.location.origin : 'https://chat.example.com'}/course-agent-widget.v1.js"
  data-agent-id="${agentId}"
  data-embed-key="${key}"
  data-mode="bubble"
  data-theme="light"
  async
></script>`
}

export function getMockPublicChatUrl(agentId: string): string {
  const base =
    typeof window !== 'undefined' ? window.location.origin : 'http://localhost:5173'
  return `${base}/chat/${agentId}`
}

export async function mockCreateKnowledgeBase(body: {
  name: string
  description?: string
}): Promise<CourseAgentKnowledgeBase> {
  const materialLabel = `material_${Date.now().toString(36)}`
  const kb: CourseAgentKnowledgeBase = {
    id: `kb_${Date.now().toString(36)}`,
    name: body.name,
    description: body.description ?? '',
    materialLabel,
    documentCount: 0,
    chunkCount: 0,
    lastIndexedAt: new Date().toISOString(),
    status: 'ready',
  }
  PLATFORM_KNOWLEDGE_BASES = [kb, ...PLATFORM_KNOWLEDGE_BASES]
  mockDocuments.set(materialLabel, [])
  return withMockDelay(kb)
}

export async function mockUpdateKnowledgeBase(
  kbId: string,
  body: { name: string; description?: string }
): Promise<CourseAgentKnowledgeBase> {
  const index = PLATFORM_KNOWLEDGE_BASES.findIndex((kb) => kb.id === kbId)
  if (index < 0) throw new ApiClientError('NOT_FOUND', '知识库不存在')
  const updated: CourseAgentKnowledgeBase = {
    ...PLATFORM_KNOWLEDGE_BASES[index]!,
    name: body.name,
    description: body.description ?? '',
  }
  PLATFORM_KNOWLEDGE_BASES = [
    ...PLATFORM_KNOWLEDGE_BASES.slice(0, index),
    updated,
    ...PLATFORM_KNOWLEDGE_BASES.slice(index + 1),
  ]
  return withMockDelay(updated)
}

export async function mockDeleteKnowledgeBase(
  kbId: string
): Promise<{ message: string }> {
  const kb = findPlatformKb(kbId)
  PLATFORM_KNOWLEDGE_BASES = PLATFORM_KNOWLEDGE_BASES.filter(
    (item) => item.id !== kbId
  )
  mockDocuments.delete(kb.materialLabel)
  return withMockDelay({ message: '知识库已删除' })
}

export async function mockCreateModel(body: {
  name: string
  description?: string
  provider?: string
  stream?: boolean
  modelName?: string
  endpointId?: string
  apiKey?: string
  baseUrl?: string
  setAsActive?: boolean
}): Promise<CourseAgentModelProfile> {
  const setActive = body.setAsActive || PLATFORM_MODELS.length === 0
  const profile: CourseAgentModelProfile = {
    id: `mdl_${Date.now().toString(36)}`,
    name: body.name,
    description: body.description ?? '',
    provider: body.provider ?? 'doubao',
    stream: body.stream ?? false,
    modelName: body.modelName ?? 'doubao-seed-2-0-pro-260215',
    endpointId: body.endpointId ?? '',
    apiKey: body.apiKey?.trim() ?? '',
    baseUrl: body.baseUrl ?? 'https://ark.cn-beijing.volces.com/api/v3',
    isActive: setActive,
  }
  PLATFORM_MODELS = setActive
    ? [profile, ...PLATFORM_MODELS.map((m) => ({ ...m, isActive: false }))]
    : [profile, ...PLATFORM_MODELS]
  return withMockDelay(maskProfile(profile))
}

export async function mockUpdateModel(
  modelId: string,
  body: {
    name?: string
    description?: string
    provider?: string
    stream?: boolean
    modelName?: string
    endpointId?: string
    apiKey?: string
    baseUrl?: string
    setAsActive?: boolean
  }
): Promise<CourseAgentModelProfile> {
  const index = PLATFORM_MODELS.findIndex((m) => m.id === modelId)
  if (index < 0) throw new ApiClientError('NOT_FOUND', '模型配置不存在')
  const current = PLATFORM_MODELS[index]!
  const updated: CourseAgentModelProfile = {
    ...current,
    ...(body.name !== undefined ? { name: body.name } : {}),
    ...(body.description !== undefined ? { description: body.description } : {}),
    ...(body.provider !== undefined ? { provider: body.provider } : {}),
    ...(body.stream !== undefined ? { stream: body.stream } : {}),
    ...(body.modelName !== undefined ? { modelName: body.modelName } : {}),
    ...(body.endpointId !== undefined ? { endpointId: body.endpointId } : {}),
    ...(body.baseUrl !== undefined ? { baseUrl: body.baseUrl } : {}),
    ...(body.apiKey?.trim() ? { apiKey: body.apiKey.trim() } : {}),
    isActive: body.setAsActive ? true : current.isActive,
  }
  PLATFORM_MODELS = PLATFORM_MODELS.map((m, i) => {
    if (i === index) return updated
    if (body.setAsActive) return { ...m, isActive: false }
    return m
  })
  return withMockDelay(maskProfile(updated))
}

export async function mockDeleteModel(
  modelId: string
): Promise<{ message: string }> {
  findPlatformModel(modelId)
  const next = PLATFORM_MODELS.filter((m) => m.id !== modelId)
  if (next.length > 0 && !next.some((m) => m.isActive)) {
    next[0] = { ...next[0]!, isActive: true }
  }
  PLATFORM_MODELS = next
  return withMockDelay({ message: '模型配置已删除' })
}

export async function mockActivateModel(
  modelId: string
): Promise<CourseAgentModelProfile> {
  const target = findPlatformModel(modelId)
  PLATFORM_MODELS = PLATFORM_MODELS.map((m) => ({
    ...m,
    isActive: m.id === modelId,
  }))
  return withMockDelay(maskProfile({ ...target, isActive: true }))
}

export async function mockListMaterialDocuments(
  kbId: string
): Promise<CourseMaterialDocument[]> {
  const kb = findPlatformKb(kbId)
  return withMockDelay(mockDocuments.get(kb.materialLabel) ?? [])
}

export async function mockDeleteMaterialDocument(
  kbId: string,
  attachmentId: string
): Promise<{
  materialLabel: string
  knowledgeBase: CourseAgentKnowledgeBase
  message: string
}> {
  const kb = findPlatformKb(kbId)
  const materialLabel = kb.materialLabel
  const docs = mockDocuments.get(materialLabel) ?? []
  const nextDocs = docs.filter((doc) => doc.id !== attachmentId)
  if (nextDocs.length === docs.length) {
    throw new ApiClientError('NOT_FOUND', '文档不存在')
  }
  mockDocuments.set(materialLabel, nextDocs)

  const removedChunks = docs
    .filter((doc) => doc.id === attachmentId)
    .reduce((sum, doc) => sum + doc.chunkCount, 0)

  const index = PLATFORM_KNOWLEDGE_BASES.findIndex((item) => item.id === kbId)
  const updated: CourseAgentKnowledgeBase = {
    ...kb,
    documentCount: Math.max(0, kb.documentCount - 1),
    chunkCount: Math.max(0, kb.chunkCount - removedChunks),
    lastIndexedAt: new Date().toISOString(),
    status: nextDocs.length === 0 ? 'ready' : kb.status,
  }
  PLATFORM_KNOWLEDGE_BASES = [
    ...PLATFORM_KNOWLEDGE_BASES.slice(0, index),
    updated,
    ...PLATFORM_KNOWLEDGE_BASES.slice(index + 1),
  ]
  return withMockDelay({
    materialLabel,
    knowledgeBase: updated,
    message: '文档已删除',
  })
}

export async function mockGetAttachmentExtractedText(
  attachmentId: string
): Promise<AttachmentExtractedText> {
  const doc = [...mockDocuments.values()]
    .flat()
    .find((item) => item.id === attachmentId)
  return withMockDelay({
    attachmentId,
    fileName: doc?.fileName ?? '示例文档.pdf',
    fileType: doc?.fileType ?? 'pdf',
    content:
      '## 第一章 课程介绍\n\n暑期 AI 课程面向 8—14 岁学生，线下班位于北京、上海。\n\n## 第二章 费用说明\n\n| 项目 | 说明 |\n| --- | --- |\n| 地点 | 北京、上海 |\n| 费用 | 请咨询招生老师，资料中未列明具体金额 |\n\n线下班费用请咨询招生老师，资料中未列明具体金额。',
    contentFormat: 'markdown',
    charCount: 120,
    parseEngine: 'docling-mock',
    parseQuality: 'ocr',
    hasTables: true,
    hasFigures: false,
    pageCount: 2,
    figureAssets: [],
    extractedAt: new Date().toISOString(),
  })
}

export async function mockGetAttachmentChunks(
  attachmentId: string
): Promise<AttachmentChunks> {
  const doc = [...mockDocuments.values()]
    .flat()
    .find((item) => item.id === attachmentId)
  return withMockDelay({
    attachmentId,
    fileName: doc?.fileName ?? '示例文档.pdf',
    total: 3,
    byType: { clause: 3 },
    chunks: [
      {
        id: `${attachmentId}-c1`,
        chunkIndex: 0,
        chunkType: 'clause',
        docRole: 'body',
        content: '暑期 AI 课程面向 8—14 岁学生，线下班位于北京、上海。',
        positionLabel: '第一章',
        pageStart: 1,
        pageEnd: 1,
        tokenCount: 32,
      },
      {
        id: `${attachmentId}-c2`,
        chunkIndex: 1,
        chunkType: 'clause',
        docRole: 'body',
        content: '线下班费用请咨询招生老师，资料中未列明具体金额。',
        positionLabel: '第二章',
        pageStart: 2,
        pageEnd: 2,
        tokenCount: 24,
      },
      {
        id: `${attachmentId}-c3`,
        chunkIndex: 2,
        chunkType: 'clause',
        docRole: 'body',
        content: '报名需提前准备身份证件与近期照片。',
        positionLabel: '第三章',
        pageStart: 2,
        pageEnd: 2,
        tokenCount: 18,
      },
    ],
  })
}

export async function mockSearchKnowledgeChunks(body: {
  query: string
  mode?: string
  standardId?: string
}): Promise<ChunkSearchResult> {
  const q = body.query.toLowerCase()
  const hits = [
    {
      chunkId: 'mock-chunk-1',
      attachmentId: 'doc-1',
      standardId: body.standardId ?? 'mock-standard',
      fileName: '夏令营手册.pdf',
      chunkType: 'clause',
      docRole: 'body',
      positionLabel: '第二章 · 费用说明',
      content: '线下班费用请咨询招生老师，资料中未列明具体金额。',
      score: q.includes('费用') || q.includes('钱') ? 0.92 : 0.61,
      source: body.mode ?? 'hybrid',
    },
    {
      chunkId: 'mock-chunk-2',
      attachmentId: 'doc-1',
      standardId: body.standardId ?? 'mock-standard',
      chunkType: 'clause',
      docRole: 'body',
      positionLabel: '第一章 · 课程介绍',
      content: '暑期 AI 课程面向 8—14 岁学生，线下班位于北京、上海。',
      score: 0.55,
      source: body.mode ?? 'hybrid',
      fileName: '夏令营手册.pdf',
    },
  ]
  return withMockDelay({
    query: body.query,
    mode: (body.mode as ChunkSearchResult['mode']) ?? 'hybrid',
    elapsedSec: 0.18,
    hits,
  })
}
