import { useCallback, useEffect, useState } from 'react'
import { listPlatformModels } from '@/lib/api/course-agent'
import { ApiClientError } from '@/lib/api/client'
import { useAppPermissions } from '@/hooks/use-app-permissions'
import { ModelList } from '../components/model-list'
import type { CourseAgentModelProfile } from '../data/types'

export function AgentModelPage() {
  const { can } = useAppPermissions()
  const canConfig = can('course_agent_config')
  const [models, setModels] = useState<CourseAgentModelProfile[]>([])
  const [loadingModels, setLoadingModels] = useState(true)
  const [modelsError, setModelsError] = useState<string>()

  const loadModels = useCallback(async () => {
    setLoadingModels(true)
    setModelsError(undefined)
    try {
      setModels(await listPlatformModels())
    } catch (e) {
      setModelsError(e instanceof ApiClientError ? e.message : '加载模型列表失败')
      setModels([])
    } finally {
      setLoadingModels(false)
    }
  }, [])

  useEffect(() => {
    void loadModels()
  }, [loadModels])

  const activeModelId =
    models.find((m) => m.isActive)?.id ?? models[0]?.id

  if (loadingModels && models.length === 0) {
    return <p className='text-muted-foreground text-sm'>加载模型配置…</p>
  }

  if (modelsError) {
    return <p className='text-destructive text-sm'>{modelsError}</p>
  }

  return (
    <ModelList
      models={models}
      activeModelId={activeModelId}
      readOnly={!canConfig}
      onCreated={(model) => {
        setModels((prev) => {
          const next = [model, ...prev]
          if (model.isActive) {
            return next.map((item) =>
              item.id === model.id ? item : { ...item, isActive: false }
            )
          }
          return next
        })
      }}
      onUpdated={(model) => {
        setModels((prev) =>
          prev.map((item) => {
            if (item.id === model.id) return model
            if (model.isActive) return { ...item, isActive: false }
            return item
          })
        )
      }}
      onDeleted={(modelId) => {
        setModels((prev) => prev.filter((item) => item.id !== modelId))
      }}
      onActivated={(model) => {
        setModels((prev) =>
          prev.map((item) => ({
            ...item,
            isActive: item.id === model.id,
          }))
        )
      }}
    />
  )
}
