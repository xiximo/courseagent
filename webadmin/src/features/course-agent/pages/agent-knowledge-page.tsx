import { useCallback, useEffect, useState } from 'react'
import { getBillingMe } from '@/lib/api/billing'
import { listPlatformKnowledgeBases } from '@/lib/api/course-agent'
import { ApiClientError } from '@/lib/api/client'
import { AppErrorAlert } from '@/components/app-error-alert'
import { useIsPlatformConsole } from '@/lib/auth/console-paths'
import { useAppPermissions } from '@/hooks/use-app-permissions'
import { KnowledgeBaseList } from '../components/knowledge-base-list'
import type { CourseAgentKnowledgeBase } from '../data/types'

export function AgentKnowledgePage() {
  const { can } = useAppPermissions()
  const canConfig = can('course_agent_config')
  const platform = useIsPlatformConsole()
  const [knowledgeBases, setKnowledgeBases] = useState<CourseAgentKnowledgeBase[]>(
    []
  )
  const [createDisabled, setCreateDisabled] = useState(false)
  const [createHint, setCreateHint] = useState<string>()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string>()

  const reload = useCallback(async () => {
    setLoading(true)
    setError(undefined)
    try {
      const [rows, mine] = await Promise.all([
        listPlatformKnowledgeBases(),
        platform ? Promise.resolve(null) : getBillingMe().catch(() => null),
      ])
      setKnowledgeBases(rows)
      if (mine && mine.canCreateKnowledgeBase === false) {
        setCreateDisabled(true)
        setCreateHint('免费版仅可创建 1 个知识库，升级专业版后不限数量')
      } else {
        setCreateDisabled(false)
        setCreateHint(undefined)
      }
    } catch (e) {
      setError(e instanceof ApiClientError ? e.message : '加载知识库失败')
      setKnowledgeBases([])
    } finally {
      setLoading(false)
    }
  }, [platform])
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
    <div className='space-y-4'>
    <KnowledgeBaseList
      knowledgeBases={knowledgeBases}
      readOnly={!canConfig}
      createDisabled={createDisabled}
      createHint={createHint}
      onCreated={(kb) => {
        setKnowledgeBases((prev) => [kb, ...prev])
        if (!platform) {
          void getBillingMe()
            .then((mine) => {
              if (mine.canCreateKnowledgeBase === false) {
                setCreateDisabled(true)
                setCreateHint('免费版仅可创建 1 个知识库，升级专业版后不限数量')
              }
            })
            .catch(() => undefined)
        }
      }}
      onUpdated={(kb) =>
        setKnowledgeBases((prev) =>
          prev.map((item) => (item.id === kb.id ? kb : item))
        )
      }
      onDeleted={(kbId) =>
        setKnowledgeBases((prev) => prev.filter((item) => item.id !== kbId))
      }
    />
    </div>
  )
}
