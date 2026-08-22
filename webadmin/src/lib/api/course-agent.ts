import { apiFetch, apiFetchForm, readEnvelope, ApiClientError } from './client'
import { isDevMock } from '@/lib/is-dev-mock'
import type {
  AttachmentExtractedText,
  CourseAgentConfig,
  CourseAgentKnowledgeBase,
  CourseAgentLeadDetail,
  CourseAgentLeadSummary,
  CourseAgentModelProfile,
  CourseAgentSession,
  CourseAgentSessionSummary,
  CourseAgentSummary,
  CourseAgentTraceEvent,
  AdminSessionDetail,
  AdminUserSessionGroup,
  CourseMaterialDocument,
  CreateCourseAgentInput,
} from '@/features/course-agent/data/types'
import {
  mockCreateCourseAgent,
  mockDeleteCourseAgent,
  mockCreateCourseAgentSession,
  mockCreateKnowledgeBase,
  mockCreateModel,
  mockDeleteKnowledgeBase,
  mockDeleteModel,
  mockDeleteMaterialDocument,
  mockGetAttachmentExtractedText,
  mockGetCourseAgent,
  mockGetKnowledgeBase,
  mockGetPublicAgentConfig,
  mockListCourseAgents,
  mockListMaterialDocuments,
  mockListModels,
  mockListPlatformKnowledgeBases,
  mockListPlatformModels,
  mockListCourseAgentSessions,
  mockGetCourseAgentSession,
  mockResetCourseAgentSession,
  mockDeleteCourseAgentSession,
  mockSendCourseAgentMessage,
  mockUpdateCourseAgent,
  mockUpdateKnowledgeBase,
  mockUpdateModel,
  mockActivateModel,
} from '@/features/course-agent/mock/course-agent-handlers'

export async function listCourseAgents(): Promise<CourseAgentSummary[]> {
  if (isDevMock()) return mockListCourseAgents()
  const res = await apiFetch('GET', '/api/v1/course-agents')
  return readEnvelope<CourseAgentSummary[]>(res)
}

export async function createCourseAgent(
  body: CreateCourseAgentInput
): Promise<CourseAgentConfig> {
  if (isDevMock()) return mockCreateCourseAgent(body)
  const res = await apiFetch('POST', '/api/v1/course-agents', body)
  return readEnvelope<CourseAgentConfig>(res)
}

export async function deleteCourseAgent(
  agentId: string
): Promise<{ message: string }> {
  if (isDevMock()) return mockDeleteCourseAgent(agentId)
  const res = await apiFetch('DELETE', `/api/v1/course-agents/${agentId}`)
  return readEnvelope<{ message: string }>(res)
}

export async function getCourseAgent(agentId: string): Promise<CourseAgentConfig> {
  if (isDevMock()) return mockGetCourseAgent(agentId)
  const res = await apiFetch('GET', `/api/v1/course-agents/${agentId}`)
  return readEnvelope<CourseAgentConfig>(res)
}

export async function updateCourseAgent(
  agentId: string,
  patch: Partial<CourseAgentConfig>
): Promise<CourseAgentConfig> {
  if (isDevMock()) return mockUpdateCourseAgent(agentId, patch)
  const res = await apiFetch('PATCH', `/api/v1/course-agents/${agentId}`, patch)
  return readEnvelope<CourseAgentConfig>(res)
}

export async function setDefaultCourseAgent(
  agentId: string
): Promise<CourseAgentConfig> {
  if (isDevMock()) return mockUpdateCourseAgent(agentId, { isDefault: true })
  const res = await apiFetch(
    'POST',
    `/api/v1/course-agents/${agentId}/set-default`
  )
  return readEnvelope<CourseAgentConfig>(res)
}

export async function runCourseAgentSchedule(
  agentId: string
): Promise<CourseAgentConfig> {
  if (isDevMock()) {
    const { mockRunCourseAgentSchedule } = await import(
      '@/features/course-agent/mock/course-agent-handlers'
    )
    return mockRunCourseAgentSchedule(agentId)
  }
  const res = await apiFetch(
    'POST',
    `/api/v1/course-agents/${agentId}/schedule/run`
  )
  return readEnvelope<CourseAgentConfig>(res)
}

export async function getPublicAttachmentExtractedText(
  attachmentId: string
): Promise<AttachmentExtractedText> {
  if (isDevMock()) {
    return mockGetAttachmentExtractedText(attachmentId)
  }
  const res = await apiFetch(
    'GET',
    `/api/v1/course-agent/attachments/${attachmentId}/extracted-text`
  )
  return readEnvelope(res)
}

export async function createCourseAgentSession(
  agentId: string
): Promise<CourseAgentSession> {
  if (isDevMock()) return mockCreateCourseAgentSession(agentId)
  const res = await apiFetch(
    'POST',
    `/api/v1/course-agents/${agentId}/sessions`
  )
  return readEnvelope<CourseAgentSession>(res)
}

export async function listCourseAgentSessions(
  agentId: string
): Promise<CourseAgentSessionSummary[]> {
  if (isDevMock()) return mockListCourseAgentSessions(agentId)
  const res = await apiFetch(
    'GET',
    `/api/v1/course-agents/${agentId}/sessions`
  )
  return readEnvelope<CourseAgentSessionSummary[]>(res)
}

export async function getCourseAgentSession(
  sessionId: string
): Promise<CourseAgentSession> {
  if (isDevMock()) return mockGetCourseAgentSession(sessionId)
  const res = await apiFetch(
    'GET',
    `/api/v1/course-agent/sessions/${sessionId}`
  )
  return readEnvelope<CourseAgentSession>(res)
}

export async function deleteCourseAgentSession(
  sessionId: string
): Promise<{ message: string }> {
  if (isDevMock()) return mockDeleteCourseAgentSession(sessionId)
  const res = await apiFetch(
    'DELETE',
    `/api/v1/course-agent/sessions/${sessionId}`
  )
  return readEnvelope<{ message: string }>(res)
}

export async function sendCourseAgentMessage(
  sessionId: string,
  content: string
): Promise<CourseAgentSession> {
  if (isDevMock()) return mockSendCourseAgentMessage(sessionId, content)
  const res = await apiFetch(
    'POST',
    `/api/v1/course-agent/sessions/${sessionId}/messages`,
    { content }
  )
  return readEnvelope<CourseAgentSession>(res)
}

export async function sendCourseAgentMessageStream(
  sessionId: string,
  content: string,
  handlers: {
    onDelta?: (text: string) => void
    onTrace?: (event: CourseAgentTraceEvent) => void
    onDone?: (session: CourseAgentSession) => void
  }
): Promise<CourseAgentSession> {
  if (isDevMock()) {
    handlers.onTrace?.({
      id: `trace-turn-${Date.now()}`,
      type: 'turn',
      title: '开始处理用户问题',
      detail: content,
      status: 'running',
      createdAt: new Date().toISOString(),
    })
    handlers.onTrace?.({
      id: `trace-think-${Date.now()}`,
      type: 'thinking',
      title: '第 1 轮：模型规划中',
      status: 'done',
      createdAt: new Date().toISOString(),
    })
    const session = await mockSendCourseAgentMessage(sessionId, content)
    const last = [...session.messages].reverse().find((m) => m.role === 'assistant')
    if (last?.content) handlers.onDelta?.(last.content)
    handlers.onTrace?.({
      id: `trace-reply-${Date.now()}`,
      type: 'reply',
      title: '回答完成',
      status: 'done',
      createdAt: new Date().toISOString(),
    })
    handlers.onDone?.(session)
    return session
  }

  let doneSession: CourseAgentSession | null = null
  const { postSse } = await import('./sse')
  await postSse(
    `/api/v1/course-agent/sessions/${sessionId}/messages/stream`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    },
    {
      onDelta: (data) => {
        if (data.text) handlers.onDelta?.(data.text)
      },
      onTrace: (data) => {
        const event = data as CourseAgentTraceEvent
        if (event?.id && event?.title) handlers.onTrace?.(event)
      },
      onDone: (data) => {
        doneSession = data as CourseAgentSession
        handlers.onDone?.(doneSession)
      },
    }
  )
  if (!doneSession) {
    throw new ApiClientError('STREAM_INCOMPLETE', '流式回复未正常结束')
  }
  return doneSession
}

export async function resetCourseAgentSession(
  sessionId: string
): Promise<CourseAgentSession> {
  if (isDevMock()) return mockResetCourseAgentSession(sessionId)
  const res = await apiFetch(
    'POST',
    `/api/v1/course-agent/sessions/${sessionId}/reset`
  )
  return readEnvelope<CourseAgentSession>(res)
}

export type PublicAgentConfig = {
  agentId: string
  name: string
  welcomeMessage: string
  menuButtons: string[]
  theme: 'light' | 'dark'
}

export async function getPublicAgentConfig(
  agentId: string
): Promise<PublicAgentConfig> {
  if (isDevMock()) return mockGetPublicAgentConfig(agentId)
  const res = await apiFetch(
    'GET',
    `/api/v1/course-agents/${agentId}/public-config`
  )
  return readEnvelope<PublicAgentConfig>(res)
}

export type CourseMaterialActionResult = {
  materialLabel: string
  knowledgeBase: CourseAgentKnowledgeBase
  message: string
}

export async function uploadCourseMaterial(
  kbId: string,
  file: File
): Promise<CourseMaterialActionResult> {
  const form = new FormData()
  form.append('file', file)
  const res = await apiFetchForm(
    'POST',
    `/api/v1/platform/knowledge-bases/${kbId}/upload`,
    form
  )
  return readEnvelope<CourseMaterialActionResult>(res)
}

export async function reindexCourseMaterial(
  kbId: string
): Promise<CourseMaterialActionResult> {
  const res = await apiFetch(
    'POST',
    `/api/v1/platform/knowledge-bases/${kbId}/reindex`
  )
  return readEnvelope<CourseMaterialActionResult>(res)
}

export async function createKnowledgeBase(body: {
  name: string
  description?: string
}): Promise<CourseAgentKnowledgeBase> {
  if (isDevMock()) return mockCreateKnowledgeBase(body)
  const res = await apiFetch('POST', '/api/v1/platform/knowledge-bases', body)
  return readEnvelope<CourseAgentKnowledgeBase>(res)
}

export async function getKnowledgeBase(
  kbId: string
): Promise<CourseAgentKnowledgeBase> {
  if (isDevMock()) return mockGetKnowledgeBase(kbId)
  const res = await apiFetch('GET', `/api/v1/platform/knowledge-bases/${kbId}`)
  return readEnvelope<CourseAgentKnowledgeBase>(res)
}

export async function updateKnowledgeBase(
  kbId: string,
  body: { name: string; description?: string }
): Promise<CourseAgentKnowledgeBase> {
  if (isDevMock()) return mockUpdateKnowledgeBase(kbId, body)
  const res = await apiFetch(
    'PATCH',
    `/api/v1/platform/knowledge-bases/${kbId}`,
    body
  )
  return readEnvelope<CourseAgentKnowledgeBase>(res)
}

export async function deleteKnowledgeBase(
  kbId: string
): Promise<{ message: string }> {
  if (isDevMock()) return mockDeleteKnowledgeBase(kbId)
  const res = await apiFetch(
    'DELETE',
    `/api/v1/platform/knowledge-bases/${kbId}`
  )
  return readEnvelope<{ message: string }>(res)
}

export async function listPlatformKnowledgeBases(): Promise<
  CourseAgentKnowledgeBase[]
> {
  if (isDevMock()) return mockListPlatformKnowledgeBases()
  const res = await apiFetch('GET', '/api/v1/platform/knowledge-bases')
  return readEnvelope<CourseAgentKnowledgeBase[]>(res)
}

export async function listPlatformModels(): Promise<CourseAgentModelProfile[]> {
  if (isDevMock()) return mockListPlatformModels()
  const res = await apiFetch('GET', '/api/v1/platform/models')
  return readEnvelope<CourseAgentModelProfile[]>(res)
}

export async function listModels(
  agentId: string
): Promise<CourseAgentModelProfile[]> {
  if (isDevMock()) return mockListModels(agentId)
  const res = await apiFetch('GET', `/api/v1/course-agents/${agentId}/models`)
  return readEnvelope<CourseAgentModelProfile[]>(res)
}

export async function createModel(body: {
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
  if (isDevMock()) return mockCreateModel(body)
  const res = await apiFetch('POST', '/api/v1/platform/models', body)
  return readEnvelope<CourseAgentModelProfile>(res)
}

export async function updateModel(
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
  if (isDevMock()) return mockUpdateModel(modelId, body)
  const res = await apiFetch('PATCH', `/api/v1/platform/models/${modelId}`, body)
  return readEnvelope<CourseAgentModelProfile>(res)
}

export async function deleteModel(
  modelId: string
): Promise<{ message: string }> {
  if (isDevMock()) return mockDeleteModel(modelId)
  const res = await apiFetch('DELETE', `/api/v1/platform/models/${modelId}`)
  return readEnvelope<{ message: string }>(res)
}

export async function activateModel(
  modelId: string
): Promise<CourseAgentModelProfile> {
  if (isDevMock()) return mockActivateModel(modelId)
  const res = await apiFetch(
    'POST',
    `/api/v1/platform/models/${modelId}/activate`
  )
  return readEnvelope<CourseAgentModelProfile>(res)
}

export async function listMaterialDocuments(
  kbId: string
): Promise<CourseMaterialDocument[]> {
  if (isDevMock()) return mockListMaterialDocuments(kbId)
  const res = await apiFetch(
    'GET',
    `/api/v1/platform/knowledge-bases/${kbId}/documents`
  )
  return readEnvelope<CourseMaterialDocument[]>(res)
}

export async function deleteMaterialDocument(
  kbId: string,
  attachmentId: string
): Promise<CourseMaterialActionResult> {
  if (isDevMock()) {
    return mockDeleteMaterialDocument(kbId, attachmentId)
  }
  const res = await apiFetch(
    'DELETE',
    `/api/v1/platform/knowledge-bases/${kbId}/documents/${attachmentId}`
  )
  return readEnvelope<CourseMaterialActionResult>(res)
}

export async function listCourseAgentLeads(params?: {
  agentId?: string
  limit?: number
  offset?: number
}): Promise<CourseAgentLeadSummary[]> {
  const query = new URLSearchParams()
  if (params?.agentId) query.set('agent_id', params.agentId)
  if (params?.limit != null) query.set('limit', String(params.limit))
  if (params?.offset != null) query.set('offset', String(params.offset))
  const qs = query.toString()
  const res = await apiFetch(
    'GET',
    `/api/v1/course-agent/leads${qs ? `?${qs}` : ''}`
  )
  return readEnvelope<CourseAgentLeadSummary[]>(res)
}

export async function listAdminSessionRecords(params?: {
  agentId?: string
}): Promise<AdminUserSessionGroup[]> {
  const query = new URLSearchParams()
  if (params?.agentId) query.set('agent_id', params.agentId)
  const qs = query.toString()
  const res = await apiFetch(
    'GET',
    `/api/v1/course-agent/session-records${qs ? `?${qs}` : ''}`
  )
  return readEnvelope<AdminUserSessionGroup[]>(res)
}

export async function getAdminSessionRecord(
  sessionId: string
): Promise<AdminSessionDetail> {
  const res = await apiFetch(
    'GET',
    `/api/v1/course-agent/session-records/${sessionId}`
  )
  return readEnvelope<AdminSessionDetail>(res)
}

export async function deleteAdminSessionRecord(
  sessionId: string
): Promise<{ message?: string }> {
  const res = await apiFetch(
    'DELETE',
    `/api/v1/course-agent/session-records/${sessionId}`
  )
  return readEnvelope<{ message?: string }>(res)
}

export async function getCourseAgentLead(
  leadId: string
): Promise<CourseAgentLeadDetail> {
  const res = await apiFetch('GET', `/api/v1/course-agent/leads/${leadId}`)
  return readEnvelope<CourseAgentLeadDetail>(res)
}

export async function deleteCourseAgentLead(
  leadId: string
): Promise<{ message: string }> {
  const res = await apiFetch('DELETE', `/api/v1/course-agent/leads/${leadId}`)
  return readEnvelope<{ message: string }>(res)
}
