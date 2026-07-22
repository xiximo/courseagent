import { useEffect, useState } from 'react'
import { ApiClientError } from '@/lib/api/client'
import {
  getAttachmentChunks,
  getAttachmentExtractedText,
} from '@/lib/api/knowledge-processing'
import { AppErrorAlert } from '@/components/app-error-alert'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ExtractedTextPreview } from './extracted-text-preview'
import type {
  AttachmentChunks,
  AttachmentExtractedText,
  CourseMaterialDocument,
} from '../data/types'

type DocumentInspectSheetProps = {
  document: CourseMaterialDocument | null
  open: boolean
  onOpenChange: (open: boolean) => void
  initialTab?: 'parse' | 'chunks'
}

export function DocumentInspectSheet({
  document,
  open,
  onOpenChange,
  initialTab = 'parse',
}: DocumentInspectSheetProps) {
  const [tab, setTab] = useState<'parse' | 'chunks'>(initialTab)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string>()
  const [extracted, setExtracted] = useState<AttachmentExtractedText | null>(null)
  const [chunks, setChunks] = useState<AttachmentChunks | null>(null)

  useEffect(() => {
    if (open) setTab(initialTab)
  }, [open, initialTab, document?.id])

  useEffect(() => {
    if (!open || !document) {
      setExtracted(null)
      setChunks(null)
      setError(undefined)
      return
    }

    void (async () => {
      setLoading(true)
      setError(undefined)
      try {
        const [textResult, chunkResult] = await Promise.allSettled([
          getAttachmentExtractedText(document.id),
          getAttachmentChunks(document.id),
        ])

        if (textResult.status === 'fulfilled') {
          setExtracted(textResult.value)
        } else {
          setExtracted(null)
        }

        if (chunkResult.status === 'fulfilled') {
          setChunks(chunkResult.value)
        } else {
          setChunks(null)
        }

        if (
          textResult.status === 'rejected' &&
          chunkResult.status === 'rejected'
        ) {
          const err =
            textResult.reason instanceof ApiClientError
              ? textResult.reason.message
              : '加载失败'
          setError(err)
        }
      } finally {
        setLoading(false)
      }
    })()
  }, [open, document])

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className='flex w-full flex-col sm:max-w-3xl'>
        <SheetHeader>
          <SheetTitle className='truncate pr-6'>
            {document?.fileName ?? '文档详情'}
          </SheetTitle>
          <SheetDescription>
            查看抽取后的原文与结构切片，便于核对解析质量
          </SheetDescription>
        </SheetHeader>

        {error ? (
          <AppErrorAlert message={error} />
        ) : (
          <Tabs
            value={tab}
            onValueChange={(v) => setTab(v as 'parse' | 'chunks')}
            className='flex min-h-0 flex-1 flex-col'
          >
            <TabsList className='grid w-full grid-cols-2'>
              <TabsTrigger value='parse'>解析文本</TabsTrigger>
              <TabsTrigger value='chunks'>
                切片 {chunks ? `(${chunks.total})` : ''}
              </TabsTrigger>
            </TabsList>

            <TabsContent value='parse' className='mt-3 min-h-0 flex-1'>
              {loading ? (
                <p className='text-muted-foreground text-sm'>加载中…</p>
              ) : extracted ? (
                <ExtractedTextPreview extracted={extracted} />
              ) : (
                <p className='text-muted-foreground text-sm'>
                  暂无解析文本，请等待文档处理完成
                </p>
              )}
            </TabsContent>

            <TabsContent value='chunks' className='mt-3 min-h-0 flex-1'>
              {loading ? (
                <p className='text-muted-foreground text-sm'>加载中…</p>
              ) : chunks && chunks.chunks.length > 0 ? (
                <ScrollArea className='h-[min(60vh,520px)]'>
                  <div className='space-y-3 pr-3'>
                    {chunks.chunks.map((chunk) => (
                      <div
                        key={chunk.id}
                        className='space-y-1 rounded-md border p-3 text-sm'
                      >
                        <div className='flex flex-wrap items-center gap-2'>
                          <Badge variant='outline'>#{chunk.chunkIndex}</Badge>
                          <Badge variant='secondary'>{chunk.chunkType}</Badge>
                          {chunk.positionLabel ? (
                            <span className='text-muted-foreground text-xs'>
                              {chunk.positionLabel}
                            </span>
                          ) : null}
                        </div>
                        <p className='text-xs leading-relaxed whitespace-pre-wrap'>
                          {chunk.content}
                        </p>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              ) : (
                <p className='text-muted-foreground text-sm'>
                  暂无切片，请等待文档处理完成
                </p>
              )}
            </TabsContent>
          </Tabs>
        )}
      </SheetContent>
    </Sheet>
  )
}
