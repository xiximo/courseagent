import { Button } from '@/components/ui/button'
import { ConversationConfigPanel } from '../components/conversation-config-panel'
import { useAgentConfig } from '../context/agent-config-context'

export function AgentConversationPage() {
  const { config, canConfig, saving, setConfig, save } = useAgentConfig()
  if (!config) return null

  return (
    <div className='space-y-4'>
      <div>
        <h2 className='text-lg font-semibold'>对话体验</h2>
        <p className='text-muted-foreground text-sm'>
          欢迎语、菜单按钮与异常提示文案
        </p>
      </div>
      <ConversationConfigPanel
        config={config.conversation}
        readOnly={!canConfig}
        onChange={(conversation) => setConfig({ ...config, conversation })}
      />
      {canConfig ? (
        <Button
          disabled={saving}
          onClick={() => void save({ conversation: config.conversation })}
        >
          {saving ? '保存中…' : '保存对话配置'}
        </Button>
      ) : null}
    </div>
  )
}
