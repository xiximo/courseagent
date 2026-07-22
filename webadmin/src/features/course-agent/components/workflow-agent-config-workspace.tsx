import { useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'
import { ApiClientError } from '@/lib/api/client'
import {
  listPlatformKnowledgeBases,
  listPlatformModels,
  updateCourseAgent,
} from '@/lib/api/course-agent'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { AgentPreviewPanel } from './agent-preview-panel'
import {
  WorkflowCanvas,
  type CanvasSelection,
} from './workflow/workflow-canvas'
import { WorkflowNodeInspector } from './workflow/workflow-node-inspector'
import { WorkflowEdgeInspector } from './workflow/workflow-edge-inspector'
import type {
  CourseAgentConfig,
  CourseAgentKnowledgeBase,
  CourseAgentModelProfile,
} from '../data/types'
import {
  collectBoundKnowledgeBaseIds,
  createDefaultWorkflowGraph,
  getEntryWelcome,
  normalizeWorkflowGraph,
  updateSpecEdge,
  updateSpecNode,
  workflowGraphToStateMachine,
  type WorkflowGraph,
} from '../lib/workflow-graph'

type WorkflowAgentConfigWorkspaceProps = {
  config: CourseAgentConfig
  canConfig: boolean
  onSaved: (config: CourseAgentConfig) => void
}

export function WorkflowAgentConfigWorkspace({
  config,
  canConfig,
  onSaved,
}: WorkflowAgentConfigWorkspaceProps) {
  const [name, setName] = useState(config.name)
  const [temperature, setTemperature] = useState(config.temperature ?? 0.3)
  const [modelIds, setModelIds] = useState<string[]>(config.boundModelIds ?? [])
  const [catalogKbs, setCatalogKbs] = useState<CourseAgentKnowledgeBase[]>([])
  const [catalogModels, setCatalogModels] = useState<CourseAgentModelProfile[]>(
    []
  )
  const [graph, setGraph] = useState<WorkflowGraph>(() =>
    normalizeWorkflowGraph(config.workflowGraph)
  )
  const [selection, setSelection] = useState<CanvasSelection>({
    kind: 'node',
    id: normalizeWorkflowGraph(config.workflowGraph).entryNodeId || 'n_entry',
  })
  const [saving, setSaving] = useState(false)
  const [rightTab, setRightTab] = useState('inspect')

  useEffect(() => {
    setName(config.name)
    setTemperature(config.temperature ?? 0.3)
    setModelIds(config.boundModelIds ?? [])
    const next = normalizeWorkflowGraph(config.workflowGraph)
    setGraph(next)
    setSelection({ kind: 'node', id: next.entryNodeId })
  }, [config])

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const [kbs, models] = await Promise.all([
          listPlatformKnowledgeBases(),
          listPlatformModels(),
        ])
        if (!cancelled) {
          setCatalogKbs(kbs)
          setCatalogModels(models)
        }
      } catch (e) {
        if (!cancelled) {
          toast.error(e instanceof ApiClientError ? e.message : '加载资源目录失败')
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const selectedNode = useMemo(() => {
    if (selection?.kind !== 'node') return null
    return graph.nodes.find((n) => n.id === selection.id) ?? null
  }, [graph.nodes, selection])

  const selectedEdge = useMemo(() => {
    if (selection?.kind !== 'edge') return null
    return graph.edges.find((e) => e.id === selection.id) ?? null
  }, [graph.edges, selection])

  const handleSave = async () => {
    const trimmed = name.trim()
    if (!trimmed) {
      toast.error('请输入 Agent 名称')
      return
    }
    setSaving(true)
    try {
      const entry = getEntryWelcome(graph)
      const boundKnowledgeBaseIds = collectBoundKnowledgeBaseIds(graph)
      const stateMachine = workflowGraphToStateMachine(graph)
      const updated = await updateCourseAgent(config.agentId, {
        name: trimmed,
        temperature,
        boundKnowledgeBaseIds,
        boundModelIds: modelIds,
        stateMachine: stateMachine as CourseAgentConfig['stateMachine'],
        workflowGraph: graph,
        conversation: {
          ...config.conversation,
          welcomeMessage: entry.welcomeMessage,
          menuButtons: entry.menuButtons,
        },
      })
      onSaved(updated)
      toast.success('流程配置已保存')
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const readOnly = !canConfig

  return (
    <div className='flex min-h-0 flex-1 flex-col gap-3'>
      <div className='flex flex-wrap items-end justify-between gap-3 rounded-xl border bg-card p-3'>
        <div className='grid flex-1 gap-3 sm:grid-cols-2 lg:grid-cols-5'>
          <div className='space-y-1.5 sm:col-span-2'>
            <Label htmlFor='wf-agent-name'>Agent 名称</Label>
            <Input
              id='wf-agent-name'
              value={name}
              disabled={readOnly}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className='space-y-1.5'>
            <Label htmlFor='wf-temp'>Temperature</Label>
            <Input
              id='wf-temp'
              type='number'
              min={0}
              max={2}
              step={0.1}
              value={temperature}
              disabled={readOnly}
              onChange={(e) => setTemperature(Number(e.target.value))}
            />
          </div>
          <div className='space-y-1.5'>
            <Label htmlFor='wf-max-chars'>最大输入字数</Label>
            <Input
              id='wf-max-chars'
              type='number'
              min={1}
              value={graph.policies.maxInputChars}
              disabled={readOnly}
              onChange={(e) =>
                setGraph((g) => ({
                  ...g,
                  policies: {
                    ...g.policies,
                    maxInputChars: Number(e.target.value) || 500,
                  },
                }))
              }
            />
          </div>
          <div className='space-y-1.5'>
            <Label htmlFor='wf-min-slots'>推荐最少约束数</Label>
            <Input
              id='wf-min-slots'
              type='number'
              min={1}
              value={graph.policies.minConstraintsForRecommend}
              disabled={readOnly}
              onChange={(e) =>
                setGraph((g) => ({
                  ...g,
                  policies: {
                    ...g.policies,
                    minConstraintsForRecommend: Number(e.target.value) || 2,
                  },
                }))
              }
            />
          </div>
        </div>
        <div className='flex gap-2'>
          <Button
            type='button'
            variant='outline'
            disabled={readOnly}
            onClick={() => {
              setGraph(createDefaultWorkflowGraph())
              setSelection({ kind: 'node', id: 'n_entry' })
              toast.message('已重置为默认顾问拓扑，保存后生效')
            }}
          >
            重置默认图
          </Button>
          <Button
            disabled={readOnly || saving}
            onClick={() => void handleSave()}
          >
            {saving ? '保存中…' : '保存流程'}
          </Button>
        </div>
      </div>

      <div className='grid min-h-0 flex-1 gap-3 xl:grid-cols-[minmax(0,1fr)_380px]'>
        <WorkflowCanvas
          graph={graph}
          selection={selection}
          readOnly={readOnly}
          onGraphChange={setGraph}
          onSelectionChange={setSelection}
        />

        <div className='flex min-h-0 flex-col rounded-xl border bg-card'>
          <Tabs
            value={rightTab}
            onValueChange={setRightTab}
            className='flex min-h-0 flex-1 flex-col'
          >
            <TabsList className='m-3 grid grid-cols-3'>
              <TabsTrigger value='inspect'>配置</TabsTrigger>
              <TabsTrigger value='bind'>模型</TabsTrigger>
              <TabsTrigger value='preview'>预览</TabsTrigger>
            </TabsList>

            <TabsContent value='inspect' className='min-h-0 flex-1 px-3 pb-3'>
              <ScrollArea className='h-[calc(100vh-300px)] pr-3'>
                {selectedNode ? (
                  <WorkflowNodeInspector
                    node={selectedNode}
                    readOnly={readOnly}
                    knowledgeBases={catalogKbs}
                    isEntry={selectedNode.id === graph.entryNodeId}
                    onSetAsEntry={() =>
                      setGraph((g) => ({
                        ...g,
                        entryNodeId: selectedNode.id,
                      }))
                    }
                    onChange={(patch) =>
                      setGraph((g) =>
                        updateSpecNode(g, selectedNode.id, patch)
                      )
                    }
                  />
                ) : selectedEdge ? (
                  <WorkflowEdgeInspector
                    edge={selectedEdge}
                    readOnly={readOnly}
                    onChange={(patch) =>
                      setGraph((g) => updateSpecEdge(g, selectedEdge.id, patch))
                    }
                  />
                ) : (
                  <p className='text-muted-foreground text-sm'>
                    点击节点编辑契约配置；点击边编辑条件、优先级与
                    apply 补丁。知识库请在「知识范围」节点按角色绑定。
                  </p>
                )}
              </ScrollArea>
            </TabsContent>

            <TabsContent value='bind' className='min-h-0 flex-1 px-3 pb-3'>
              <ScrollArea className='h-[calc(100vh-300px)] pr-3'>
                <div className='space-y-5'>
                  <div className='rounded-lg border border-dashed p-3 text-xs text-muted-foreground'>
                    知识库已改为在画布「知识范围（scope）」节点按
                    student / teacher / org
                    分别绑定，不再使用全局多选混检。
                  </div>
                  <div className='space-y-2'>
                    <Label>绑定模型（可多选）</Label>
                    <div className='space-y-2 rounded-lg border p-3'>
                      {catalogModels.length === 0 ? (
                        <p className='text-muted-foreground text-xs'>暂无模型</p>
                      ) : (
                        catalogModels.map((model) => (
                          <label
                            key={model.id}
                            className='flex items-start gap-2 text-sm'
                          >
                            <Checkbox
                              checked={modelIds.includes(model.id)}
                              disabled={readOnly}
                              onCheckedChange={(v) => {
                                setModelIds((list) =>
                                  v === true
                                    ? [...list, model.id]
                                    : list.filter((x) => x !== model.id)
                                )
                              }}
                            />
                            <span>
                              <span className='font-medium'>{model.name}</span>
                              <span className='text-muted-foreground mt-0.5 block text-xs'>
                                {model.provider} · {model.modelName}
                              </span>
                            </span>
                          </label>
                        ))
                      )}
                    </div>
                  </div>
                </div>
              </ScrollArea>
            </TabsContent>

            <TabsContent value='preview' className='min-h-0 flex-1 px-2 pb-2'>
              <div className='mb-2 flex justify-end'>
                <Button size='sm' variant='outline' asChild>
                  <a
                    href={`/admin/course-agents/${config.agentId}/preview`}
                    target='_blank'
                    rel='noreferrer'
                  >
                    打开独立预览页
                  </a>
                </Button>
              </div>
              <div className='h-[calc(100vh-340px)] overflow-hidden rounded-lg border'>
                <AgentPreviewPanel
                  agentId={config.agentId}
                  agentName={name || config.name}
                  menuButtons={getEntryWelcome(graph).menuButtons}
                />
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  )
}
