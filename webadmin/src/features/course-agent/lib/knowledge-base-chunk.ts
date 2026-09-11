export type KnowledgeChunkMode = 'size' | 'chapter'

export const DEFAULT_CHUNK_MAX_CHARS = 1800
export const DEFAULT_CHUNK_OVERLAP_CHARS = 200

export function normalizeChunkMode(mode?: string): KnowledgeChunkMode {
  return mode === 'chapter' ? 'chapter' : 'size'
}

export function chunkModeLabel(mode?: string) {
  return normalizeChunkMode(mode) === 'chapter' ? '按章节' : '按大小与重叠'
}

export function chunkSettingSummary(kb: {
  chunkMode?: string
  chunkMaxChars?: number
  chunkOverlapChars?: number
}) {
  if (normalizeChunkMode(kb.chunkMode) === 'chapter') {
    return '按章节切片'
  }
  const size = kb.chunkMaxChars || DEFAULT_CHUNK_MAX_CHARS
  const overlap = kb.chunkOverlapChars ?? DEFAULT_CHUNK_OVERLAP_CHARS
  return `按大小 ${size} / 重叠 ${overlap}`
}
