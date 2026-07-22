export type CourseAgentStep =
  | 'welcome'
  | 'identity'
  | 'constraints'
  | 'recommend'
  | 'qa'
  | 'enroll'
  | 'preview'

export type CourseAgentRole = 'student' | 'teacher' | 'org'

export type CourseAgentStatus = 'active' | 'disabled' | 'draft'

export type CourseAgentType = 'basic' | 'workflow' | 'autonomous'

export type CourseAgentConstraints = {
  city?: string
  date?: string
  format?: 'online' | 'offline'
  goal?: string
}

export type CourseAgentCitation = {
  document: string
  chapter: string
  attachmentId?: string
  chunkId?: string
}

export type CourseAgentMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  createdAt: string
  citations?: CourseAgentCitation[]
  quickActions?: string[]
}

export type CourseAgentSessionState = {
  step: CourseAgentStep
  role: CourseAgentRole | null
  constraints: CourseAgentConstraints
  recommendedCourses: string[]
  lockedCourse?: string
}

export type CourseAgentSession = {
  id: string
  agentId: string
  title: string
  messages: CourseAgentMessage[]
  state: CourseAgentSessionState
  createdAt: string
  updatedAt: string
}

export type CourseAgentModelConfig = {
  provider: string
  stream: boolean
  modelName: string
  endpointId: string
  apiKey: string
  apiKeyConfigured?: boolean
  baseUrl: string
}

export type CourseAgentModelProfile = CourseAgentModelConfig & {
  id: string
  name: string
  description?: string
  isActive?: boolean
}

export type CourseAgentStateStep = {
  id: CourseAgentStep
  label: string
  description: string
  enabled: boolean
  template?: string
}

/** 工作流画布存盘结构（对齐 docs/workflow-graph.schema.json） */
export type WorkflowGraphPayload = {
  version?: '1' | string
  entryNodeId?: string
  policies?: {
    maxInputChars?: number
    minConstraintsForRecommend?: number
  }
  nodes: Array<{
    id: string
    type?: string
    name?: string
    ui?: { x?: number; y?: number }
    config?: Record<string, unknown>
    position?: { x: number; y: number }
    data?: Record<string, unknown>
    [key: string]: unknown
  }>
  edges: Array<{
    id: string
    source: string
    target: string
    priority?: number
    when?: Record<string, unknown>
    apply?: Record<string, unknown>
    label?: string
    [key: string]: unknown
  }>
  meta?: Record<string, unknown>
  viewport?: { x: number; y: number; zoom: number }
}

export type CourseAgentKnowledgeBase = {
  id: string
  role?: CourseAgentRole | ''
  name: string
  materialLabel: string
  description?: string
  standardId?: string
  documentCount: number
  chunkCount: number
  lastIndexedAt: string
  status: 'ready' | 'indexing' | 'error'
}

export type CourseMaterialDocument = {
  id: string
  fileName: string
  fileType: string
  fileSize?: number
  parseStatus: 'pending' | 'parsed' | 'failed' | 'skipped'
  chunkCount: number
  indexedChunkCount: number
  uploadedAt: string
  failureReason?: string
}

export type ExtractedFigureAsset = {
  fileName: string
  previewUrl: string
  storageKey?: string
  pageNo?: number
  captions?: string[]
}

export type AttachmentExtractedText = {
  attachmentId: string
  fileName: string
  fileType: string
  content: string
  contentFormat: 'markdown' | 'plain'
  charCount: number
  parseEngine?: string
  parseQuality?: string
  hasTables: boolean
  hasFigures: boolean
  pageCount?: number
  figureAssets?: ExtractedFigureAsset[]
  extractedAt?: string
}

export type TextChunk = {
  id: string
  chunkIndex: number
  chunkType: string
  docRole: string
  content: string
  positionLabel?: string
  clauseLevel?: string
  pageStart?: number
  pageEnd?: number
  tokenCount?: number
}

export type AttachmentChunks = {
  attachmentId: string
  fileName: string
  total: number
  byType: Record<string, number>
  chunks: TextChunk[]
}

export type ChunkSearchMode = 'keyword' | 'semantic' | 'hybrid'

export type ChunkSearchHit = {
  chunkId: string
  attachmentId: string
  standardId: string
  chunkType?: string
  docRole?: string
  positionLabel?: string
  content?: string
  score?: number
  source?: string
  fileName?: string
}

export type ChunkSearchResult = {
  query: string
  mode: ChunkSearchMode
  elapsedSec: number
  hits: ChunkSearchHit[]
}

export type CourseAgentEmbedConfig = {
  embedKey: string
  allowedOrigins: string[]
  theme: 'light' | 'dark'
  position: 'bottom-right' | 'inline'
}

export type CourseAgentConversationConfig = {
  welcomeMessage: string
  /** 基础型 Agent 的系统提示词；空则使用后端默认 */
  systemPrompt?: string
  menuButtons: string[]
  resetMessage: string
  emptyInputMessage: string
  tooLongMessage: string
  outOfScopeMessage: string
}

export type CourseAgentConfig = {
  agentId: string
  name: string
  description: string
  status: CourseAgentStatus
  agentType: CourseAgentType
  isDefault?: boolean
  temperature?: number
  boundKnowledgeBaseIds?: string[]
  boundModelIds?: string[]
  model: CourseAgentModelConfig
  activeModelId?: string
  models?: CourseAgentModelProfile[]
  stateMachine: CourseAgentStateStep[]
  workflowGraph?: WorkflowGraphPayload | null
  knowledgeBases: CourseAgentKnowledgeBase[]
  embed: CourseAgentEmbedConfig
  conversation: CourseAgentConversationConfig
  updatedAt: string
}

export type CourseAgentSummary = Pick<
  CourseAgentConfig,
  'agentId' | 'name' | 'description' | 'status' | 'agentType' | 'updatedAt'
> & {
  isDefault?: boolean
}

export type CreateCourseAgentInput = {
  name: string
  description?: string
  agentType: CourseAgentType
}

export type CourseAgentAdminTab =
  | 'overview'
  | 'model'
  | 'state-machine'
  | 'knowledge'
  | 'conversation'
  | 'embed'
  | 'sessions'
  | 'leads'

export type CourseAgentLeadProfile = {
  role?: string | null
  constraints?: Record<string, string | undefined>
  recommendedCourses?: string[]
  lockedCourse?: string | null
  step?: string
}

export type CourseAgentLeadSummary = {
  id: string
  agentId: string
  agentName: string
  sessionId: string
  consultationIndex: number
  status: 'open' | 'closed' | string
  clientIp?: string | null
  role?: string | null
  profile: CourseAgentLeadProfile
  title: string
  messageCount: number
  startedAt: string
  endedAt?: string | null
}

export type CourseAgentLeadDetail = CourseAgentLeadSummary & {
  userAgent?: string | null
  origin?: string | null
  messages: CourseAgentMessage[]
}
