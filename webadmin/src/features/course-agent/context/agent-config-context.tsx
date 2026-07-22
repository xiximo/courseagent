import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { toast } from 'sonner'
import { ApiClientError } from '@/lib/api/client'
import { getCourseAgent, updateCourseAgent } from '@/lib/api/course-agent'
import type { CourseAgentConfig } from '../data/types'

type AgentConfigContextValue = {
  agentId: string
  config: CourseAgentConfig | null
  loading: boolean
  error?: string
  saving: boolean
  canConfig: boolean
  setConfig: React.Dispatch<React.SetStateAction<CourseAgentConfig | null>>
  reload: () => Promise<void>
  save: (patch: Partial<CourseAgentConfig>) => Promise<boolean>
}

const AgentConfigContext = createContext<AgentConfigContextValue | null>(null)

type AgentConfigProviderProps = {
  agentId: string
  canConfig: boolean
  children: ReactNode
}

export function AgentConfigProvider({
  agentId,
  canConfig,
  children,
}: AgentConfigProviderProps) {
  const [config, setConfig] = useState<CourseAgentConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string>()
  const [saving, setSaving] = useState(false)

  const reload = useCallback(async () => {
    setLoading(true)
    setError(undefined)
    try {
      setConfig(await getCourseAgent(agentId))
    } catch (e) {
      setError(e instanceof ApiClientError ? e.message : '加载失败')
      setConfig(null)
    } finally {
      setLoading(false)
    }
  }, [agentId])

  useEffect(() => {
    void reload()
  }, [reload])

  const save = useCallback(
    async (patch: Partial<CourseAgentConfig>) => {
      if (!canConfig) return false
      setSaving(true)
      try {
        const updated = await updateCourseAgent(agentId, patch)
        setConfig(updated)
        toast.success('配置已保存')
        return true
      } catch (e) {
        toast.error(e instanceof ApiClientError ? e.message : '保存失败')
        return false
      } finally {
        setSaving(false)
      }
    },
    [agentId, canConfig]
  )

  const value = useMemo(
    () => ({
      agentId,
      config,
      loading,
      error,
      saving,
      canConfig,
      setConfig,
      reload,
      save,
    }),
    [agentId, config, loading, error, saving, canConfig, reload, save]
  )

  return (
    <AgentConfigContext.Provider value={value}>
      {children}
    </AgentConfigContext.Provider>
  )
}

export function useAgentConfig() {
  const ctx = useContext(AgentConfigContext)
  if (!ctx) {
    throw new Error('useAgentConfig must be used within AgentConfigProvider')
  }
  return ctx
}
