import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from '@tanstack/react-router'
import { ArrowLeft, FileText, Layers, Pencil, RefreshCw, Search, Trash2, Upload } from 'lucide-react'
import { toast } from 'sonner'
import {
  deleteKnowledgeBase,
  deleteMaterialDocument,
  listMaterialDocuments,
  reindexCourseMaterial,
  updateKnowledgeBase,
  uploadCourseMaterial,
} from '@/lib/api/course-agent'
import { ApiClientError } from '@/lib/api/client'
import { AppErrorAlert } from '@/components/app-error-alert'
import { ConfirmDialog } from '@/components/confirm-dialog'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { DocumentInspectSheet } from './document-inspect-sheet'
import { KnowledgeRetrievalTestSheet } from './knowledge-retrieval-test-panel'
import type {
  CourseAgentKnowledgeBase,
  CourseMaterialDocument,
} from '../data/types'
import {
  formatFileSize,
  knowledgeBaseRoleLabel,
  PARSE_STATUS_LABEL,
  STATUS_LABEL,
  STATUS_VARIANT,
} from '../lib/knowledge-base-labels'

const ACCEPT =
  '.pdf,.doc,.docx,.md,.markdown,.txt,application/pdf,text/plain,text/markdown'

type KnowledgeBaseDetailProps = {
  knowledgeBase: CourseAgentKnowledgeBase
  readOnly?: boolean
  onKnowledgeBaseUpdated: (kb: CourseAgentKnowledgeBase) => void
  onKnowledgeBaseDeleted?: (kbId: string) => void
}

export function KnowledgeBaseDetail({
  knowledgeBase,
  readOnly,
  onKnowledgeBaseUpdated,
  onKnowledgeBaseDeleted,
}: KnowledgeBaseDetailProps) {
  const navigate = useNavigate()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [documents, setDocuments] = useState<CourseMaterialDocument[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string>()
  const [busy, setBusy] = useState(false)
  const [inspectDoc, setInspectDoc] = useState<CourseMaterialDocument | null>(
    null
  )
  const [inspectTab, setInspectTab] = useState<'parse' | 'chunks'>('parse')
  const [inspectOpen, setInspectOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<CourseMaterialDocument | null>(
    null
  )
  const [deleting, setDeleting] = useState(false)
  const [retrievalOpen, setRetrievalOpen] = useState(false)
  const [editOpen, setEditOpen] = useState(false)
  const [deleteKbOpen, setDeleteKbOpen] = useState(false)
  const [editName, setEditName] = useState(knowledgeBase.name)
  const [editDescription, setEditDescription] = useState(
    knowledgeBase.description ?? ''
  )
  const [savingKb, setSavingKb] = useState(false)
  const [deletingKb, setDeletingKb] = useState(false)

  const loadDocuments = useCallback(async () => {
    setLoading(true)
    setError(undefined)
    try {
      setDocuments(await listMaterialDocuments(knowledgeBase.id))
    } catch (e) {
      setError(e instanceof ApiClientError ? e.message : '加载文档失败')
      setDocuments([])
    } finally {
      setLoading(false)
    }
  }, [knowledgeBase.id])

  useEffect(() => {
    void loadDocuments()
  }, [loadDocuments])

  useEffect(() => {
    setEditName(knowledgeBase.name)
    setEditDescription(knowledgeBase.description ?? '')
  }, [knowledgeBase.id, knowledgeBase.name, knowledgeBase.description])

  const handleUploadClick = () => {
    fileInputRef.current?.click()
  }

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return

    setBusy(true)
    try {
      const result = await uploadCourseMaterial(knowledgeBase.id, file)
      onKnowledgeBaseUpdated(result.knowledgeBase)
      toast.success(result.message || '资料上传成功')
      await loadDocuments()
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : '上传失败')
    } finally {
      setBusy(false)
    }
  }

  const handleReindex = async () => {
    setBusy(true)
    try {
      const result = await reindexCourseMaterial(knowledgeBase.id)
      onKnowledgeBaseUpdated(result.knowledgeBase)
      toast.success(result.message || '重建索引已启动')
      await loadDocuments()
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : '重建索引失败')
    } finally {
      setBusy(false)
    }
  }

  const openInspect = (
    doc: CourseMaterialDocument,
    tab: 'parse' | 'chunks'
  ) => {
    setInspectDoc(doc)
    setInspectTab(tab)
    setInspectOpen(true)
  }

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      const result = await deleteMaterialDocument(
        knowledgeBase.id,
        deleteTarget.id
      )
      onKnowledgeBaseUpdated(result.knowledgeBase)
      if (inspectDoc?.id === deleteTarget.id) {
        setInspectOpen(false)
        setInspectDoc(null)
      }
      setDeleteTarget(null)
      toast.success(result.message || '文档已删除')
      await loadDocuments()
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : '删除失败')
    } finally {
      setDeleting(false)
    }
  }

  const handleEditKb = async () => {
    const trimmed = editName.trim()
    if (!trimmed) {
      toast.error('请输入知识库名称')
      return
    }
    setSavingKb(true)
    try {
      const kb = await updateKnowledgeBase(knowledgeBase.id, {
        name: trimmed,
        description: editDescription.trim(),
      })
      onKnowledgeBaseUpdated(kb)
      setEditOpen(false)
      toast.success('知识库已更新')
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : '更新失败')
    } finally {
      setSavingKb(false)
    }
  }

  const handleDeleteKbConfirm = async () => {
    setDeletingKb(true)
    try {
      const result = await deleteKnowledgeBase(knowledgeBase.id)
      onKnowledgeBaseDeleted?.(knowledgeBase.id)
      toast.success(result.message || '知识库已删除')
      void navigate({ to: '/admin/knowledge' })
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : '删除失败')
    } finally {
      setDeletingKb(false)
      setDeleteKbOpen(false)
    }
  }

  return (
    <div className='space-y-4'>
      <div className='flex flex-wrap items-start justify-between gap-3'>
        <div className='space-y-2'>
          <Button variant='ghost' size='sm' className='-ml-2 h-8 px-2' asChild>
            <Link to='/admin/knowledge'>
              <ArrowLeft className='mr-1 size-4' />
              返回知识库列表
            </Link>
          </Button>
          <div>
            <h2 className='text-lg font-semibold'>{knowledgeBase.name}</h2>
            <p className='text-muted-foreground text-sm'>
              {knowledgeBase.description ||
                '上传 PDF / DOCX / Markdown，自动抽取、切片并建立向量索引'}
            </p>
          </div>
          <div className='flex flex-wrap gap-2'>
            {knowledgeBaseRoleLabel(knowledgeBase.role) ? (
              <Badge variant='outline'>
                {knowledgeBaseRoleLabel(knowledgeBase.role)}
              </Badge>
            ) : null}
            <Badge variant={STATUS_VARIANT[knowledgeBase.status]}>
              {STATUS_LABEL[knowledgeBase.status]}
            </Badge>
            <span className='text-muted-foreground text-sm'>
              {knowledgeBase.documentCount} 文档 · {knowledgeBase.chunkCount} 块
            </span>
          </div>
        </div>
        <div className='flex flex-wrap gap-2'>
          <Button
            type='button'
            variant='outline'
            size='sm'
            disabled={busy}
            onClick={() => void loadDocuments()}
          >
            <RefreshCw className='mr-1 size-4' />
            刷新
          </Button>
          <Button
            type='button'
            size='sm'
            disabled={readOnly || busy}
            onClick={handleUploadClick}
          >
            <Upload className='mr-1 size-4' />
            {busy ? '处理中…' : '上传文档'}
          </Button>
          <Button
            type='button'
            size='sm'
            variant='secondary'
            disabled={readOnly || busy || knowledgeBase.documentCount === 0}
            onClick={() => void handleReindex()}
          >
            重建索引
          </Button>
          <Button
            type='button'
            size='sm'
            variant='outline'
            disabled={knowledgeBase.chunkCount === 0}
            onClick={() => setRetrievalOpen(true)}
          >
            <Search className='mr-1 size-4' />
            检索测试
          </Button>
          <Button
            type='button'
            size='sm'
            variant='outline'
            disabled={readOnly}
            onClick={() => setEditOpen(true)}
          >
            <Pencil className='mr-1 size-4' />
            编辑
          </Button>
          <Button
            type='button'
            size='sm'
            variant='outline'
            className='text-destructive hover:text-destructive'
            disabled={readOnly || busy}
            onClick={() => setDeleteKbOpen(true)}
          >
            <Trash2 className='mr-1 size-4' />
            删除
          </Button>
        </div>
      </div>

      <input
        ref={fileInputRef}
        type='file'
        accept={ACCEPT}
        className='hidden'
        onChange={(e) => void handleFileChange(e)}
      />

      {error ? <AppErrorAlert message={error} /> : null}

      <Card>
        <CardHeader>
          <CardTitle className='text-base'>知识文档</CardTitle>
          <CardDescription>
            文档上传后将进入抽取 → 切片 → 向量索引流水线
          </CardDescription>
        </CardHeader>
        <CardContent className='p-0'>
          {loading ? (
            <p className='text-muted-foreground px-6 py-8 text-sm'>加载中…</p>
          ) : documents.length === 0 ? (
            <p className='text-muted-foreground px-6 py-8 text-center text-sm'>
              暂无文档，点击「上传文档」添加资料
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>文件名</TableHead>
                  <TableHead>类型</TableHead>
                  <TableHead>大小</TableHead>
                  <TableHead>解析</TableHead>
                  <TableHead>切片</TableHead>
                  <TableHead>已索引</TableHead>
                  <TableHead>上传时间</TableHead>
                  <TableHead className='text-right'>操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {documents.map((doc) => (
                  <TableRow key={doc.id}>
                    <TableCell className='max-w-[200px] truncate font-medium'>
                      {doc.fileName}
                    </TableCell>
                    <TableCell className='uppercase'>{doc.fileType || '—'}</TableCell>
                    <TableCell>{formatFileSize(doc.fileSize)}</TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          doc.parseStatus === 'parsed'
                            ? 'default'
                            : doc.parseStatus === 'failed'
                              ? 'destructive'
                              : 'secondary'
                        }
                      >
                        {PARSE_STATUS_LABEL[doc.parseStatus]}
                      </Badge>
                    </TableCell>
                    <TableCell>{doc.chunkCount}</TableCell>
                    <TableCell>{doc.indexedChunkCount}</TableCell>
                    <TableCell className='text-muted-foreground text-sm'>
                      {doc.uploadedAt
                        ? new Date(doc.uploadedAt).toLocaleString('zh-CN')
                        : '—'}
                    </TableCell>
                    <TableCell className='text-right'>
                      <div className='flex justify-end gap-1'>
                        <Button
                          type='button'
                          size='sm'
                          variant='ghost'
                          disabled={doc.parseStatus === 'pending'}
                          onClick={() => openInspect(doc, 'parse')}
                        >
                          <FileText className='mr-1 size-3.5' />
                          解析
                        </Button>
                        <Button
                          type='button'
                          size='sm'
                          variant='ghost'
                          disabled={doc.chunkCount === 0}
                          onClick={() => openInspect(doc, 'chunks')}
                        >
                          <Layers className='mr-1 size-3.5' />
                          切片
                        </Button>
                        <Button
                          type='button'
                          size='sm'
                          variant='ghost'
                          className='text-destructive hover:text-destructive'
                          disabled={readOnly || busy}
                          onClick={() => setDeleteTarget(doc)}
                        >
                          <Trash2 className='mr-1 size-3.5' />
                          删除
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {documents.some((doc) => doc.failureReason) ? (
        <Card className='border-destructive/40'>
          <CardHeader className='pb-2'>
            <CardTitle className='text-destructive text-sm'>处理异常</CardTitle>
          </CardHeader>
          <CardContent className='space-y-2 text-sm'>
            {documents
              .filter((doc) => doc.failureReason)
              .map((doc) => (
                <p key={doc.id}>
                  <span className='font-medium'>{doc.fileName}：</span>
                  {doc.failureReason}
                </p>
              ))}
          </CardContent>
        </Card>
      ) : null}

      <DocumentInspectSheet
        document={inspectDoc}
        open={inspectOpen}
        initialTab={inspectTab}
        onOpenChange={setInspectOpen}
      />

      <KnowledgeRetrievalTestSheet
        open={retrievalOpen}
        onOpenChange={setRetrievalOpen}
        standardId={knowledgeBase.standardId}
      />

      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open && !deleting) setDeleteTarget(null)
        }}
        title='删除文档'
        desc={
          deleteTarget ? (
            <>
              确定删除「{deleteTarget.fileName}」吗？将同时删除上传文件、解析 Markdown
              与向量切片，且不可恢复。
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

      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>编辑知识库</DialogTitle>
          </DialogHeader>
          <div className='space-y-4 py-2'>
            <div className='space-y-2'>
              <Label htmlFor='edit-kb-name'>名称</Label>
              <Input
                id='edit-kb-name'
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
              />
            </div>
            <div className='space-y-2'>
              <Label htmlFor='edit-kb-desc'>描述（可选）</Label>
              <Textarea
                id='edit-kb-desc'
                value={editDescription}
                onChange={(e) => setEditDescription(e.target.value)}
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button type='button' variant='outline' onClick={() => setEditOpen(false)}>
              取消
            </Button>
            <Button
              type='button'
              disabled={savingKb}
              onClick={() => void handleEditKb()}
            >
              {savingKb ? '保存中…' : '保存'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={deleteKbOpen}
        onOpenChange={(open) => {
          if (!open && !deletingKb) setDeleteKbOpen(false)
        }}
        title='删除知识库'
        desc={
          <>
            确定删除「{knowledgeBase.name}」吗？将同时删除所有上传文件、解析 Markdown、切片与向量索引，且不可恢复。
          </>
        }
        cancelBtnText='取消'
        confirmText='删除'
        destructive
        isLoading={deletingKb}
        handleConfirm={() => void handleDeleteKbConfirm()}
      />
    </div>
  )
}
