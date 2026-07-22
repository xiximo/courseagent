import { EmbedConfigPanel } from '../components/embed-config-panel'
import { useAgentConfig } from '../context/agent-config-context'
import { updateCourseAgent } from '@/lib/api/course-agent'
import type { CourseAgentEmbedConfig } from '../data/types'

export function AgentEmbedPage() {
  const { config, canConfig, setConfig } = useAgentConfig()
  if (!config) return null

  const handleSave = async (embed: CourseAgentEmbedConfig) => {
    const updated = await updateCourseAgent(config.agentId, { embed })
    setConfig(updated)
  }

  return (
    <div className='space-y-4'>
      <div>
        <h2 className='text-lg font-semibold'>接入配置</h2>
        <p className='text-muted-foreground text-sm'>
          嵌入密钥、域名白名单与公开对话页接入代码
        </p>
      </div>
      <EmbedConfigPanel
        agentId={config.agentId}
        embed={config.embed}
        readOnly={!canConfig}
        onSave={handleSave}
      />
    </div>
  )
}
