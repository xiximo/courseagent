import { useCallback, useEffect, useState } from 'react'
import { Link } from '@tanstack/react-router'
import { getKnowledgeBase } from '@/lib/api/course-agent'
import { ApiClientError } from '@/lib/api/client'
import { AppErrorAlert } from '@/components/app-error-alert'
import { Button } from '@/components/ui/button'
import { useAppPermissions } from '@/hooks/use-app-permissions'
import { KnowledgeBaseDetail } from '../components/knowledge-base-detail'
import type { CourseAgentKnowledgeBase } from '../data/types'

type AgentKnowledgeDetailPageProps = {
  kbId: string
}

export function AgentKnowledgeDetailPage({ kbId }: AgentKnowledgeDetailPageProps) {
  const { can } = useAppPermissions()
  const canConfig = can('course_agent_config')
  const [knowledgeBase, setKnowledgeBase] = useState<CourseAgentKnowledgeBase | null>(
    null
  )
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string>()

  const reload = useCallback(async () => {
    setLoading(true)
    setError(undefined)
    try {
      setKnowledgeBase(await getKnowledgeBase(kbId))
    } catch (e) {
      setKnowledgeBase(null)
      setError(e instanceof ApiClientError ? e.message : '加载知识库失败')
    } finally {
      setLoading(false)
    }
  }, [kbId])

  useEffect(() => {
    void reload()
  }, [reload])

  if (loading) {
    return <p className='text-muted-foreground'>加载中…</p>
  }

  if (error || !knowledgeBase) {
    return (
      <div className='space-y-4 py-8 text-center'>
        {error ? <AppErrorAlert message={error} /> : (
          <p className='text-muted-foreground'>未找到该知识库</p>
        )}
        <Button asChild variant='outline'>
          <Link to='/admin/knowledge'>返回列表</Link>
        </Button>
      </div>
    )
  }

  return (
    <KnowledgeBaseDetail
      knowledgeBase={knowledgeBase}
      readOnly={!canConfig}
      onKnowledgeBaseUpdated={setKnowledgeBase}
      onKnowledgeBaseDeleted={() => {
        // 删除后由详情组件自行导航回列表
      }}
    />
  )
}
