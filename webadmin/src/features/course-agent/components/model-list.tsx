import { useState } from 'react'

import { Bot, Check, LayoutGrid, List, Pencil, Plus, Trash2 } from 'lucide-react'

import { toast } from 'sonner'

import {
  activateModel,
  createModel,
  deleteModel,
  updateModel,
} from '@/lib/api/course-agent'
import { ApiClientError } from '@/lib/api/client'
import { ConfirmDialog } from '@/components/confirm-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'

import type { CourseAgentModelProfile } from '../data/types'

type ViewMode = 'card' | 'list'

type ModelFormState = {
  name: string
  description: string
  provider: string
  stream: boolean
  modelName: string
  endpointId: string
  apiKey: string
  baseUrl: string
  setAsActive: boolean
}

const DEFAULT_FORM: ModelFormState = {
  name: '',
  description: '',
  provider: 'doubao',
  stream: false,
  modelName: 'doubao-seed-2-0-pro-260215',
  endpointId: '',
  apiKey: '',
  baseUrl: 'https://ark.cn-beijing.volces.com/api/v3',
  setAsActive: false,
}

const PROVIDER_LABEL: Record<string, string> = {
  deepseek: 'DeepSeek',
  openai: 'OpenAI',
  qwen: '通义千问',
  doubao: '豆包',
}

type ModelListProps = {
  models: CourseAgentModelProfile[]
  activeModelId?: string
  readOnly?: boolean
  onCreated: (model: CourseAgentModelProfile) => void
  onUpdated: (model: CourseAgentModelProfile) => void
  onDeleted: (modelId: string) => void
  onActivated: (model: CourseAgentModelProfile) => void
}

export function ModelList({
  models,
  activeModelId,
  readOnly,
  onCreated,
  onUpdated,
  onDeleted,
  onActivated,
}: ModelListProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('card')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingModel, setEditingModel] = useState<CourseAgentModelProfile | null>(
    null
  )
  const [deleteTarget, setDeleteTarget] = useState<CourseAgentModelProfile | null>(
    null
  )
  const [submitting, setSubmitting] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [activatingId, setActivatingId] = useState<string | null>(null)
  const [form, setForm] = useState<ModelFormState>(DEFAULT_FORM)

  const resetForm = () => {
    setForm(DEFAULT_FORM)
    setEditingModel(null)
  }

  const openCreateDialog = () => {
    resetForm()
    setForm({ ...DEFAULT_FORM, setAsActive: models.length === 0 })
    setDialogOpen(true)
  }

  const openEditDialog = (model: CourseAgentModelProfile) => {
    setEditingModel(model)
    setForm({
      name: model.name,
      description: model.description ?? '',
      provider: model.provider,
      stream: model.stream,
      modelName: model.modelName,
      endpointId: model.endpointId,
      apiKey: '',
      baseUrl: model.baseUrl,
      setAsActive: model.id === activeModelId,
    })
    setDialogOpen(true)
  }

  const handleDialogOpenChange = (open: boolean) => {
    setDialogOpen(open)
    if (!open) resetForm()
  }

  const buildPayload = () => {
    const trimmed = form.name.trim()
    const payload = {
      name: trimmed,
      description: form.description.trim(),
      provider: form.provider,
      stream: form.stream,
      modelName: form.modelName.trim(),
      endpointId: form.endpointId.trim(),
      baseUrl: form.baseUrl.trim(),
      setAsActive: form.setAsActive,
    }
    if (form.apiKey.trim()) {
      return { ...payload, apiKey: form.apiKey.trim() }
    }
    return payload
  }

  const handleSubmit = async () => {
    const trimmed = form.name.trim()
    if (!trimmed) {
      toast.error('请输入模型配置名称')
      return
    }
    setSubmitting(true)
    try {
      const payload = buildPayload()
      if (editingModel) {
        const model = await updateModel(editingModel.id, payload)
        onUpdated(model)
        if (form.setAsActive) onActivated(model)
        toast.success('模型配置已更新')
      } else {
        const model = await createModel(payload)
        onCreated(model)
        if (form.setAsActive || models.length === 0) onActivated(model)
        toast.success('模型配置已创建')
      }
      setDialogOpen(false)
      resetForm()
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : '操作失败')
    } finally {
      setSubmitting(false)
    }
  }

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      const result = await deleteModel(deleteTarget.id)
      onDeleted(deleteTarget.id)
      setDeleteTarget(null)
      toast.success(result.message || '模型配置已删除')
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : '删除失败')
    } finally {
      setDeleting(false)
    }
  }

  const handleActivate = async (model: CourseAgentModelProfile) => {
    if (model.id === activeModelId) return
    setActivatingId(model.id)
    try {
      const activated = await activateModel(model.id)
      onActivated(activated)
      toast.success(`已启用「${activated.name}」`)
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : '启用失败')
    } finally {
      setActivatingId(null)
    }
  }

  const renderDoubaoFields = () => (
    <div className='space-y-4 rounded-lg border bg-muted/20 p-4'>
      <div>
        <p className='text-sm font-medium'>豆包模型配置</p>
        <p className='text-muted-foreground mt-1 text-xs'>
          API Key 存入数据库，接口返回脱敏值；留空则回落到环境变量或平台 LLM 配置
        </p>
      </div>
      <div className='grid gap-4 sm:grid-cols-2'>
        <div className='space-y-2 sm:col-span-2'>
          <Label htmlFor='model-name-id'>模型名称 (DOUBAO_MODEL_NAME)</Label>
          <Input
            id='model-name-id'
            value={form.modelName}
            onChange={(e) => setForm({ ...form, modelName: e.target.value })}
            placeholder='doubao-seed-2-0-pro-260215'
          />
        </div>
        <div className='space-y-2 sm:col-span-2'>
          <Label htmlFor='endpoint-id'>Endpoint ID (DOUBAO_ENDPOINT_ID)</Label>
          <Input
            id='endpoint-id'
            value={form.endpointId}
            onChange={(e) => setForm({ ...form, endpointId: e.target.value })}
            placeholder='ep-m-xxxxxxxx'
          />
        </div>
        <div className='space-y-2 sm:col-span-2'>
          <Label htmlFor='api-key'>API Key (DOUBAO_API_KEY)</Label>
          <Input
            id='api-key'
            type='password'
            value={form.apiKey}
            onChange={(e) => setForm({ ...form, apiKey: e.target.value })}
            placeholder={
              editingModel?.apiKeyConfigured
                ? '已配置，输入新值可覆盖'
                : '留空则使用环境变量'
            }
            autoComplete='off'
          />
          {editingModel?.apiKeyConfigured && !form.apiKey ? (
            <p className='text-muted-foreground text-xs'>
              当前：{editingModel.apiKey || '已配置'}
            </p>
          ) : null}
        </div>
        <div className='space-y-2 sm:col-span-2'>
          <Label htmlFor='base-url'>Base URL (DOUBAO_BASE_URL)</Label>
          <Input
            id='base-url'
            value={form.baseUrl}
            onChange={(e) => setForm({ ...form, baseUrl: e.target.value })}
            placeholder='https://ark.cn-beijing.volces.com/api/v3'
          />
        </div>
      </div>
    </div>
  )

  const renderModelForm = () => (
    <div className='space-y-4 py-2'>
      <div className='space-y-2'>
        <Label htmlFor='profile-name'>名称</Label>
        <Input
          id='profile-name'
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          placeholder='例如：主对话模型'
        />
      </div>
      <div className='space-y-2'>
        <Label htmlFor='profile-desc'>描述（可选）</Label>
        <Textarea
          id='profile-desc'
          value={form.description}
          onChange={(e) => setForm({ ...form, description: e.target.value })}
          placeholder='简要说明该模型用途'
          rows={2}
        />
      </div>
      <div className='space-y-2'>
        <Label>提供商</Label>
        <Select
          value={form.provider}
          onValueChange={(v) => setForm({ ...form, provider: v })}
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value='doubao'>豆包</SelectItem>
            <SelectItem value='deepseek'>DeepSeek</SelectItem>
            <SelectItem value='openai'>OpenAI</SelectItem>
            <SelectItem value='qwen'>通义千问</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className='flex items-center justify-between rounded-lg border p-3'>
        <div>
          <p className='text-sm font-medium'>流式输出</p>
          <p className='text-muted-foreground text-xs'>
            启用后调用豆包流式接口聚合回复（后续可对接前端逐字展示）
          </p>
        </div>
        <Switch
          checked={form.stream}
          onCheckedChange={(stream) => setForm({ ...form, stream })}
        />
      </div>
      {form.provider === 'doubao' ? renderDoubaoFields() : null}
      <label className='flex items-center gap-2 text-sm'>
        <input
          type='checkbox'
          className='size-4 rounded border'
          checked={form.setAsActive}
          onChange={(e) => setForm({ ...form, setAsActive: e.target.checked })}
        />
        设为当前启用模型
      </label>
    </div>
  )

  const isActive = (id: string) => id === activeModelId

  return (
    <div className='space-y-4'>
      <div className='flex flex-wrap items-start justify-between gap-3'>
        <div>
          <h2 className='text-lg font-semibold'>模型配置</h2>
          <p className='text-muted-foreground text-sm'>
            管理 LLM 连接与豆包参数；密钥存于数据库，不回显明文
          </p>
        </div>
        <div className='flex flex-wrap items-center gap-2'>
          <div className='bg-muted flex rounded-md p-0.5'>
            <Button
              type='button'
              size='sm'
              variant={viewMode === 'card' ? 'secondary' : 'ghost'}
              className='h-8 px-2.5'
              onClick={() => setViewMode('card')}
            >
              <LayoutGrid className='size-4' />
            </Button>
            <Button
              type='button'
              size='sm'
              variant={viewMode === 'list' ? 'secondary' : 'ghost'}
              className='h-8 px-2.5'
              onClick={() => setViewMode('list')}
            >
              <List className='size-4' />
            </Button>
          </div>
          <Button
            type='button'
            size='sm'
            disabled={readOnly}
            onClick={openCreateDialog}
          >
            <Plus className='mr-1 size-4' />
            新建模型
          </Button>
        </div>
      </div>

      {models.length === 0 ? (
        <Card>
          <CardContent className='text-muted-foreground py-12 text-center text-sm'>
            暂无模型配置，点击「新建模型」开始
          </CardContent>
        </Card>
      ) : viewMode === 'card' ? (
        <div className='grid gap-4 sm:grid-cols-2 xl:grid-cols-3'>
          {models.map((model) => (
            <Card key={model.id} className='flex h-full flex-col'>
              <CardHeader className='pb-3'>
                <div className='flex items-start gap-3'>
                  <div className='bg-primary/10 text-primary flex size-10 shrink-0 items-center justify-center rounded-lg'>
                    <Bot className='size-5' />
                  </div>
                  <div className='min-w-0 flex-1'>
                    <CardTitle className='line-clamp-1 text-base'>
                      {model.name}
                    </CardTitle>
                    <CardDescription className='mt-1 line-clamp-2'>
                      {model.description || '未填写描述'}
                    </CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent className='space-y-3 pt-0'>
                <div className='flex flex-wrap gap-2'>
                  <Badge variant='outline'>
                    {PROVIDER_LABEL[model.provider] ?? model.provider}
                  </Badge>
                  {model.stream ? (
                    <Badge variant='outline'>流式</Badge>
                  ) : null}
                  {isActive(model.id) ? (
                    <Badge>当前启用</Badge>
                  ) : (
                    <Badge variant='secondary'>未启用</Badge>
                  )}
                </div>
                <p className='text-muted-foreground text-sm'>
                  {model.modelName || '—'}
                  {model.endpointId ? ` · ${model.endpointId}` : ''}
                </p>
                <p className='text-muted-foreground text-xs'>
                  API Key：{model.apiKeyConfigured ? model.apiKey || '已配置' : '未配置（使用环境变量）'}
                </p>
              </CardContent>
              <CardFooter className='mt-auto flex flex-wrap gap-2 pt-0'>
                {!isActive(model.id) ? (
                  <Button
                    type='button'
                    size='sm'
                    disabled={readOnly || activatingId === model.id}
                    onClick={() => void handleActivate(model)}
                  >
                    <Check className='mr-1 size-3.5' />
                    {activatingId === model.id ? '启用中…' : '启用'}
                  </Button>
                ) : null}
                <Button
                  type='button'
                  size='sm'
                  variant='outline'
                  disabled={readOnly}
                  onClick={() => openEditDialog(model)}
                >
                  <Pencil className='mr-1 size-3.5' />
                  编辑
                </Button>
                <Button
                  type='button'
                  size='sm'
                  variant='outline'
                  className='text-destructive hover:text-destructive'
                  disabled={readOnly}
                  onClick={() => setDeleteTarget(model)}
                >
                  <Trash2 className='mr-1 size-3.5' />
                  删除
                </Button>
              </CardFooter>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className='p-0'>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>名称</TableHead>
                  <TableHead>提供商 / 模型</TableHead>
                  <TableHead>豆包连接</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead className='text-right'>操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {models.map((model) => (
                  <TableRow key={model.id}>
                    <TableCell>
                      <div>
                        <p className='font-medium'>{model.name}</p>
                        {model.description ? (
                          <p className='text-muted-foreground line-clamp-1 text-xs'>
                            {model.description}
                          </p>
                        ) : null}
                      </div>
                    </TableCell>
                    <TableCell>
                      <p>{PROVIDER_LABEL[model.provider] ?? model.provider}</p>
                      <p className='text-muted-foreground text-xs'>
                        {model.modelName || '—'}
                      </p>
                    </TableCell>
                    <TableCell className='text-muted-foreground text-sm'>
                      <p className='line-clamp-1'>{model.endpointId || '—'}</p>
                      <p className='text-xs'>
                        {model.stream ? '流式 · ' : ''}
                        Key {model.apiKeyConfigured ? '已配置' : '环境变量'}
                      </p>
                    </TableCell>
                    <TableCell>
                      {isActive(model.id) ? (
                        <Badge>当前启用</Badge>
                      ) : (
                        <Badge variant='secondary'>未启用</Badge>
                      )}
                    </TableCell>
                    <TableCell className='text-right'>
                      <div className='flex justify-end gap-1'>
                        {!isActive(model.id) ? (
                          <Button
                            type='button'
                            size='sm'
                            variant='outline'
                            disabled={readOnly || activatingId === model.id}
                            onClick={() => void handleActivate(model)}
                          >
                            {activatingId === model.id ? '启用中…' : '启用'}
                          </Button>
                        ) : null}
                        <Button
                          type='button'
                          size='sm'
                          variant='ghost'
                          disabled={readOnly}
                          onClick={() => openEditDialog(model)}
                        >
                          编辑
                        </Button>
                        <Button
                          type='button'
                          size='sm'
                          variant='ghost'
                          className='text-destructive hover:text-destructive'
                          disabled={readOnly}
                          onClick={() => setDeleteTarget(model)}
                        >
                          删除
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      <Dialog open={dialogOpen} onOpenChange={handleDialogOpenChange}>
        <DialogContent className='max-h-[90vh] overflow-y-auto sm:max-w-lg'>
          <DialogHeader>
            <DialogTitle>
              {editingModel ? '编辑模型配置' : '新建模型配置'}
            </DialogTitle>
          </DialogHeader>
          {renderModelForm()}
          <DialogFooter>
            <Button
              type='button'
              variant='outline'
              onClick={() => handleDialogOpenChange(false)}
            >
              取消
            </Button>
            <Button
              type='button'
              disabled={submitting}
              onClick={() => void handleSubmit()}
            >
              {submitting
                ? editingModel
                  ? '保存中…'
                  : '创建中…'
                : editingModel
                  ? '保存'
                  : '创建'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open && !deleting) setDeleteTarget(null)
        }}
        title='删除模型配置'
        desc={
          deleteTarget ? (
            <>
              确定删除「{deleteTarget.name}」吗？删除后不可恢复；若该模型为当前启用项，将自动切换到其他配置。
            </>
          ) : (
            ''
          )
        }
        cancelBtnText='取消'
        confirmText='删除'
        destructive
        isLoading={deleting}
        handleConfirm={() => void handleDeleteConfirm()}
      />
    </div>
  )
}
