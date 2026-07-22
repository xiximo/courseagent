import type { CourseAgentKnowledgeBase, CourseAgentRole } from '../data/types'

export const ROLE_LABEL: Record<CourseAgentRole, string> = {
  student: '学生 / 家长',
  teacher: '教师',
  org: '机构 / 平台',
}

export const STATUS_LABEL = {
  ready: '就绪',
  indexing: '索引中',
  error: '异常',
} as const

export const STATUS_VARIANT = {
  ready: 'default',
  indexing: 'secondary',
  error: 'destructive',
} as const

export const PARSE_STATUS_LABEL = {
  pending: '待处理',
  parsed: '已解析',
  failed: '失败',
  skipped: '已跳过',
} as const

export function formatFileSize(bytes?: number): string {
  if (bytes == null || bytes <= 0) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function knowledgeBaseRoleLabel(
  role?: CourseAgentKnowledgeBase['role']
): string | null {
  if (!role) return null
  return ROLE_LABEL[role as CourseAgentRole] ?? null
}

export function findKnowledgeBase(
  knowledgeBases: CourseAgentKnowledgeBase[],
  kbId: string
): CourseAgentKnowledgeBase | undefined {
  return knowledgeBases.find((kb) => kb.id === kbId)
}
