import { useCallback, useEffect, useState } from 'react'
import { listPlatformKnowledgeBases } from '@/lib/api/course-agent'
import { ApiClientError } from '@/lib/api/client'
import { AppErrorAlert } from '@/components/app-error-alert'
import { useAppPermissions } from '@/hooks/use-app-permissions'
import { KnowledgeBaseList } from '../components/knowledge-base-list'
import type { CourseAgentKnowledgeBase } from '../data/types'

export function AgentKnowledgePage() {
  const { can } = useAppPermissions()
  const canConfig = can('course_agent_config')
  const [knowledgeBases, setKnowledgeBases] = useState<CourseAgentKnowledgeBase[]>(
    []
  )
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string>()

  const reload = useCallback(async () => {
    setLoading(true)
    setError(undefined)
    try {
      setKnowledgeBases(await listPlatformKnowledgeBases())
    } catch (e) {
      setError(e instanceof ApiClientError ? e.message : '加载知识库失败')
      setKnowledgeBases([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void reload()
  }, [reload])

  if (loading) {
    return <p className='text-muted-foreground'>加载中…</p>
  }

  if (error) {
    return <AppErrorAlert message={error} />
  }

  return (
    <KnowledgeBaseList
      knowledgeBases={knowledgeBases}
      readOnly={!canConfig}
      onCreated={(kb) => setKnowledgeBases((prev) => [kb, ...prev])}
      onUpdated={(kb) =>
        setKnowledgeBases((prev) =>
          prev.map((item) => (item.id === kb.id ? kb : item))
        )
      }
      onDeleted={(kbId) =>
        setKnowledgeBases((prev) => prev.filter((item) => item.id !== kbId))
      }
    />
  )
}
