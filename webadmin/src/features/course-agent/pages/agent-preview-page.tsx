import { AgentPreviewPanel } from '../components/agent-preview-panel'
import { useAgentConfig } from '../context/agent-config-context'

export function AgentPreviewPage() {
  const { config } = useAgentConfig()
  if (!config) return null

  return (
    <AgentPreviewPanel
      agentId={config.agentId}
      agentName={config.name}
      menuButtons={config.conversation.menuButtons}
    />
  )
}
