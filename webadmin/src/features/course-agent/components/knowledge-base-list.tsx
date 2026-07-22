import { useState } from 'react'

import { Link } from '@tanstack/react-router'

import { Database, LayoutGrid, List, Pencil, Plus, Trash2 } from 'lucide-react'

import { toast } from 'sonner'

import {

  createKnowledgeBase,

  deleteKnowledgeBase,

  updateKnowledgeBase,

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

  Table,

  TableBody,

  TableCell,

  TableHead,

  TableHeader,

  TableRow,

} from '@/components/ui/table'

import { Textarea } from '@/components/ui/textarea'

import type { CourseAgentKnowledgeBase } from '../data/types'

import {

  knowledgeBaseRoleLabel,

  STATUS_LABEL,

  STATUS_VARIANT,

} from '../lib/knowledge-base-labels'



type ViewMode = 'card' | 'list'



type KnowledgeBaseListProps = {

  knowledgeBases: CourseAgentKnowledgeBase[]

  readOnly?: boolean

  onCreated: (kb: CourseAgentKnowledgeBase) => void

  onUpdated: (kb: CourseAgentKnowledgeBase) => void

  onDeleted: (kbId: string) => void

}



export function KnowledgeBaseList({

  knowledgeBases,

  readOnly,

  onCreated,

  onUpdated,

  onDeleted,

}: KnowledgeBaseListProps) {

  const [viewMode, setViewMode] = useState<ViewMode>('card')

  const [dialogOpen, setDialogOpen] = useState(false)

  const [editingKb, setEditingKb] = useState<CourseAgentKnowledgeBase | null>(null)

  const [deleteTarget, setDeleteTarget] = useState<CourseAgentKnowledgeBase | null>(

    null

  )

  const [submitting, setSubmitting] = useState(false)

  const [deleting, setDeleting] = useState(false)

  const [name, setName] = useState('')

  const [description, setDescription] = useState('')



  const resetForm = () => {

    setName('')

    setDescription('')

    setEditingKb(null)

  }



  const openCreateDialog = () => {

    resetForm()

    setDialogOpen(true)

  }



  const openEditDialog = (kb: CourseAgentKnowledgeBase) => {

    setEditingKb(kb)

    setName(kb.name)

    setDescription(kb.description ?? '')

    setDialogOpen(true)

  }



  const handleDialogOpenChange = (open: boolean) => {

    setDialogOpen(open)

    if (!open) resetForm()

  }



  const handleSubmit = async () => {

    const trimmed = name.trim()

    if (!trimmed) {

      toast.error('请输入知识库名称')

      return

    }

    setSubmitting(true)

    try {

      if (editingKb) {

        const kb = await updateKnowledgeBase(editingKb.id, {

          name: trimmed,

          description: description.trim(),

        })

        onUpdated(kb)

        toast.success('知识库已更新')

      } else {

        const kb = await createKnowledgeBase({

          name: trimmed,

          description: description.trim(),

        })

        onCreated(kb)

        toast.success('知识库已创建')

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

      const result = await deleteKnowledgeBase(deleteTarget.id)

      onDeleted(deleteTarget.id)

      setDeleteTarget(null)

      toast.success(result.message || '知识库已删除')

    } catch (e) {

      toast.error(e instanceof ApiClientError ? e.message : '删除失败')

    } finally {

      setDeleting(false)

    }

  }



  return (

    <div className='space-y-4'>

      <div className='flex flex-wrap items-start justify-between gap-3'>

        <div>

          <h2 className='text-lg font-semibold'>知识库</h2>

          <p className='text-muted-foreground text-sm'>

            管理平台知识库；进入后可上传文档、切片与向量索引

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

            新建知识库

          </Button>

        </div>

      </div>



      {knowledgeBases.length === 0 ? (

        <Card>

          <CardContent className='text-muted-foreground py-12 text-center text-sm'>

            暂无知识库，点击「新建知识库」开始

          </CardContent>

        </Card>

      ) : viewMode === 'card' ? (

        <div className='grid gap-4 sm:grid-cols-2 xl:grid-cols-3'>

          {knowledgeBases.map((kb) => (

            <Card key={kb.id} className='flex h-full flex-col'>

              <CardHeader className='pb-3'>

                <div className='flex items-start gap-3'>

                  <div className='bg-primary/10 text-primary flex size-10 shrink-0 items-center justify-center rounded-lg'>

                    <Database className='size-5' />

                  </div>

                  <div className='min-w-0 flex-1'>

                    <CardTitle className='line-clamp-1 text-base'>

                      {kb.name}

                    </CardTitle>

                    <CardDescription className='mt-1 line-clamp-2'>

                      {kb.description || '点击进入管理文档与索引'}

                    </CardDescription>

                  </div>

                </div>

              </CardHeader>

              <CardContent className='space-y-3 pt-0'>

                <div className='flex flex-wrap gap-2'>

                  {knowledgeBaseRoleLabel(kb.role) ? (

                    <Badge variant='outline'>{knowledgeBaseRoleLabel(kb.role)}</Badge>

                  ) : null}

                  <Badge variant={STATUS_VARIANT[kb.status]}>

                    {STATUS_LABEL[kb.status]}

                  </Badge>

                </div>

                <p className='text-muted-foreground text-sm'>

                  {kb.documentCount} 文档 · {kb.chunkCount} 块

                </p>

              </CardContent>

              <CardFooter className='mt-auto flex flex-wrap gap-2 pt-0'>

                <Button size='sm' asChild>

                  <Link

                    to='/admin/knowledge/$kbId'

                    params={{ kbId: kb.id }}

                  >

                    进入

                  </Link>

                </Button>

                <Button

                  type='button'

                  size='sm'

                  variant='outline'

                  disabled={readOnly}

                  onClick={() => openEditDialog(kb)}

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

                  onClick={() => setDeleteTarget(kb)}

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

                  <TableHead>文档/块</TableHead>

                  <TableHead>状态</TableHead>

                  <TableHead>最近索引</TableHead>

                  <TableHead className='text-right'>操作</TableHead>

                </TableRow>

              </TableHeader>

              <TableBody>

                {knowledgeBases.map((kb) => (

                  <TableRow key={kb.id}>

                    <TableCell>

                      <div>

                        <p className='font-medium'>{kb.name}</p>

                        {kb.description ? (

                          <p className='text-muted-foreground line-clamp-1 text-xs'>

                            {kb.description}

                          </p>

                        ) : null}

                      </div>

                    </TableCell>

                    <TableCell>

                      {kb.documentCount} / {kb.chunkCount}

                    </TableCell>

                    <TableCell>

                      <Badge variant={STATUS_VARIANT[kb.status]}>

                        {STATUS_LABEL[kb.status]}

                      </Badge>

                    </TableCell>

                    <TableCell className='text-muted-foreground text-sm'>

                      {kb.lastIndexedAt

                        ? new Date(kb.lastIndexedAt).toLocaleString('zh-CN')

                        : '—'}

                    </TableCell>

                    <TableCell className='text-right'>

                      <div className='flex justify-end gap-1'>

                        <Button size='sm' variant='outline' asChild>

                          <Link

                            to='/admin/knowledge/$kbId'

                            params={{ kbId: kb.id }}

                          >

                            进入

                          </Link>

                        </Button>

                        <Button

                          type='button'

                          size='sm'

                          variant='ghost'

                          disabled={readOnly}

                          onClick={() => openEditDialog(kb)}

                        >

                          编辑

                        </Button>

                        <Button

                          type='button'

                          size='sm'

                          variant='ghost'

                          className='text-destructive hover:text-destructive'

                          disabled={readOnly}

                          onClick={() => setDeleteTarget(kb)}

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

        <DialogContent>

          <DialogHeader>

            <DialogTitle>{editingKb ? '编辑知识库' : '新建知识库'}</DialogTitle>

          </DialogHeader>

          <div className='space-y-4 py-2'>

            <div className='space-y-2'>

              <Label htmlFor='kb-name'>名称</Label>

              <Input

                id='kb-name'

                value={name}

                onChange={(e) => setName(e.target.value)}

                placeholder='例如：暑期课程 FAQ'

              />

            </div>

            <div className='space-y-2'>

              <Label htmlFor='kb-desc'>描述（可选）</Label>

              <Textarea

                id='kb-desc'

                value={description}

                onChange={(e) => setDescription(e.target.value)}

                placeholder='简要说明该知识库用途'

                rows={3}

              />

            </div>

          </div>

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

                ? editingKb

                  ? '保存中…'

                  : '创建中…'

                : editingKb

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

        title='删除知识库'

        desc={

          deleteTarget ? (

            <>

              确定删除「{deleteTarget.name}」吗？将同时删除所有上传文件、解析 Markdown、切片与向量索引，且不可恢复。

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


