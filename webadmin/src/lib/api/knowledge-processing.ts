import { apiFetch, readEnvelope } from './client'
import { isDevMock } from '@/lib/is-dev-mock'
import type {
  AttachmentChunks,
  AttachmentExtractedText,
  ChunkSearchMode,
  ChunkSearchResult,
} from '@/features/course-agent/data/types'
import {
  mockGetAttachmentChunks,
  mockGetAttachmentExtractedText,
  mockSearchKnowledgeChunks,
} from '@/features/course-agent/mock/course-agent-handlers'

export async function getAttachmentExtractedText(
  attachmentId: string
): Promise<AttachmentExtractedText> {
  if (isDevMock()) return mockGetAttachmentExtractedText(attachmentId)
  const res = await apiFetch(
    'GET',
    `/api/v1/qibiao/processing/attachments/${attachmentId}/extracted-text`
  )
  return readEnvelope<AttachmentExtractedText>(res)
}

export async function getAttachmentChunks(
  attachmentId: string
): Promise<AttachmentChunks> {
  if (isDevMock()) return mockGetAttachmentChunks(attachmentId)
  const res = await apiFetch(
    'GET',
    `/api/v1/qibiao/processing/attachments/${attachmentId}/chunks`
  )
  return readEnvelope<AttachmentChunks>(res)
}

export async function searchKnowledgeChunks(body: {
  query: string
  mode?: ChunkSearchMode
  topK?: number
  standardId?: string
  attachmentId?: string
}): Promise<ChunkSearchResult> {
  if (isDevMock()) return mockSearchKnowledgeChunks(body)
  const res = await apiFetch('POST', '/api/v1/qibiao/indexing/search/chunks', {
    query: body.query,
    mode: body.mode ?? 'hybrid',
    topK: body.topK ?? 10,
    standardId: body.standardId,
    attachmentId: body.attachmentId,
  })
  return readEnvelope<ChunkSearchResult>(res)
}
