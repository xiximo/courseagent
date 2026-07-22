import { useEffect, useRef, useState } from 'react'
import { ApiClientError } from '@/lib/api/client'
import { getPublicAttachmentExtractedText } from '@/lib/api/course-agent'
import { AppErrorAlert } from '@/components/app-error-alert'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { ExtractedTextPreview } from './extracted-text-preview'
import type {
  AttachmentExtractedText,
  CourseAgentCitation,
} from '../data/types'

type CitationSourceSheetProps = {
  citation: CourseAgentCitation | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

function scrollToChapter(
  container: HTMLElement | null,
  chapter: string | undefined
) {
  if (!container || !chapter?.trim()) return
  const needle = chapter.trim().replace(/^#+\s*/, '')
  const headings = container.querySelectorAll('h1,h2,h3,h4,h5,h6')
  for (const heading of headings) {
    const text = (heading.textContent ?? '').trim()
    if (text.includes(needle) || needle.includes(text)) {
      heading.scrollIntoView({ behavior: 'smooth', block: 'start' })
      heading.classList.add('bg-primary/10', 'rounded-sm')
      window.setTimeout(() => {
        heading.classList.remove('bg-primary/10', 'rounded-sm')
      }, 2400)
      return
    }
  }
}

export function CitationSourceSheet({
  citation,
  open,
  onOpenChange,
}: CitationSourceSheetProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string>()
  const [extracted, setExtracted] = useState<AttachmentExtractedText | null>(
    null
  )
  const previewRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open || !citation?.attachmentId) {
      setExtracted(null)
      setError(undefined)
      return
    }

    let cancelled = false
    void (async () => {
      setLoading(true)
      setError(undefined)
      try {
        const result = await getPublicAttachmentExtractedText(
          citation.attachmentId!
        )
        if (!cancelled) setExtracted(result)
      } catch (e) {
        if (!cancelled) {
          setExtracted(null)
          setError(
            e instanceof ApiClientError ? e.message : '加载文档失败'
          )
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()

    return () => {
      cancelled = true
    }
  }, [open, citation?.attachmentId])

  useEffect(() => {
    if (!open || !extracted || loading) return
    const timer = window.setTimeout(() => {
      scrollToChapter(previewRef.current, citation?.chapter)
    }, 120)
    return () => window.clearTimeout(timer)
  }, [open, extracted, loading, citation?.chapter])

  const title = citation?.document ?? '引用来源'

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side='right' className='flex w-full flex-col sm:max-w-xl'>
        <SheetHeader>
          <SheetTitle className='truncate pr-6'>{title}</SheetTitle>
          <SheetDescription>
            {citation?.chapter ? `章节：${citation.chapter}` : '知识库文档预览'}
          </SheetDescription>
        </SheetHeader>

        <div className='min-h-0 flex-1 overflow-hidden pt-2'>
          {!citation?.attachmentId ? (
            <p className='text-muted-foreground text-sm'>
              该引用暂无关联文档，无法预览原文。
            </p>
          ) : loading ? (
            <p className='text-muted-foreground text-sm'>正在加载文档…</p>
          ) : error ? (
            <AppErrorAlert message={error} />
          ) : extracted ? (
            <div ref={previewRef}>
              <ExtractedTextPreview extracted={extracted} />
            </div>
          ) : null}
        </div>
      </SheetContent>
    </Sheet>
  )
}
