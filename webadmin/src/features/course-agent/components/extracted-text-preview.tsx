import { useState } from 'react'
import { MarkdownRenderer } from '@/components/ui/markdown-renderer'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import type { AttachmentExtractedText } from '../data/types'

type PreviewMode = 'render' | 'source'

const PARSE_QUALITY_LABEL: Record<string, string> = {
  high: '高',
  medium: '中',
  low: '低',
  ocr: 'OCR',
}

type ExtractedTextPreviewProps = {
  extracted: AttachmentExtractedText
}

export function ExtractedTextPreview({ extracted }: ExtractedTextPreviewProps) {
  const [mode, setMode] = useState<PreviewMode>('render')
  const figureCount = extracted.figureAssets?.length ?? 0

  return (
    <div className='space-y-3'>
      <div className='flex flex-wrap gap-2 text-xs'>
        <Badge variant='outline'>{extracted.fileType}</Badge>
        {extracted.parseEngine ? (
          <Badge variant='outline'>{extracted.parseEngine}</Badge>
        ) : null}
        {extracted.parseQuality ? (
          <Badge variant='secondary'>
            质量 {PARSE_QUALITY_LABEL[extracted.parseQuality] ?? extracted.parseQuality}
          </Badge>
        ) : null}
        {extracted.hasTables ? (
          <Badge variant='secondary'>含表格</Badge>
        ) : null}
        {extracted.hasFigures ? (
          <Badge variant='secondary'>
            含图片{figureCount > 0 ? ` ${figureCount}` : ''}
          </Badge>
        ) : null}
        {extracted.pageCount ? (
          <Badge variant='outline'>{extracted.pageCount} 页</Badge>
        ) : null}
        <span className='text-muted-foreground self-center'>
          {extracted.charCount.toLocaleString('zh-CN')} 字符
        </span>
      </div>

      {extracted.extractedAt ? (
        <p className='text-muted-foreground text-xs'>
          抽取于{' '}
          {new Date(extracted.extractedAt).toLocaleString('zh-CN', {
            hour12: false,
          })}
        </p>
      ) : null}

      <div className='flex gap-1'>
        <Button
          type='button'
          size='sm'
          variant={mode === 'render' ? 'default' : 'outline'}
          onClick={() => setMode('render')}
        >
          渲染预览
        </Button>
        <Button
          type='button'
          size='sm'
          variant={mode === 'source' ? 'default' : 'outline'}
          onClick={() => setMode('source')}
        >
          Markdown 源码
        </Button>
      </div>

      <ScrollArea className='h-[min(60vh,520px)] rounded-md border p-4'>
        {mode === 'render' ? (
          extracted.contentFormat === 'markdown' ? (
            <div className='prose-sm max-w-none text-sm'>
              <MarkdownRenderer>{extracted.content}</MarkdownRenderer>
            </div>
          ) : (
            <p className='text-sm whitespace-pre-wrap'>{extracted.content}</p>
          )
        ) : (
          <pre className='text-xs whitespace-pre-wrap'>{extracted.content}</pre>
        )}
      </ScrollArea>
    </div>
  )
}
