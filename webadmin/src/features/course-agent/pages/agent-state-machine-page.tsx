import { StateMachinePanel } from '../components/state-machine-panel'
import { useAgentConfig } from '../context/agent-config-context'

export function AgentStateMachinePage() {
  const { config, canConfig } = useAgentConfig()
  if (!config) return null

  return (
    <div className='space-y-4'>
      <div>
        <h2 className='text-lg font-semibold'>状态机</h2>
        <p className='text-muted-foreground text-sm'>
          七步对话流程与门禁规则（身份澄清 → 约束采集 → 推荐 → 问答 → 报名）
        </p>
      </div>
      <StateMachinePanel steps={config.stateMachine} readOnly={!canConfig} />
    </div>
  )
}
