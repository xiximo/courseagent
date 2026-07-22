import { useEffect, useState } from 'react'
import { Search } from 'lucide-react'
import { toast } from 'sonner'
import { searchKnowledgeChunks } from '@/lib/api/knowledge-processing'
import { ApiClientError } from '@/lib/api/client'
import { AppErrorAlert } from '@/components/app-error-alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import type { ChunkSearchHit, ChunkSearchMode } from '../data/types'

const MODE_LABEL: Record<ChunkSearchMode, string> = {
  hybrid: '混合检索',
  semantic: '向量检索',
  keyword: '关键词',
}

type KnowledgeRetrievalTestSheetProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  standardId?: string
}

export function KnowledgeRetrievalTestSheet({
  open,
  onOpenChange,
  standardId,
}: KnowledgeRetrievalTestSheetProps) {
  const [query, setQuery] = useState('')
  const [mode, setMode] = useState<ChunkSearchMode>('hybrid')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string>()
  const [hits, setHits] = useState<ChunkSearchHit[]>([])
  const [elapsedSec, setElapsedSec] = useState<number>()

  useEffect(() => {
    if (!open) {
      setError(undefined)
      return
    }
  }, [open])

  const handleSearch = async (searchMode: ChunkSearchMode = mode) => {
    const trimmed = query.trim()
    if (!trimmed) {
      toast.error('请输入检索问题')
      return
    }
    if (!standardId) {
      toast.error('知识库尚未初始化标准库，无法检索')
      return
    }

    setMode(searchMode)
    setLoading(true)
    setError(undefined)
    try {
      const result = await searchKnowledgeChunks({
        query: trimmed,
        mode: searchMode,
        topK: 10,
        standardId,
      })
      setHits(result.hits)
      setElapsedSec(result.elapsedSec)
    } catch (e) {
      const message = e instanceof ApiClientError ? e.message : '检索失败'
      setError(message)
      setHits([])
      setElapsedSec(undefined)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className='flex w-full flex-col sm:max-w-xl'>
        <SheetHeader>
          <SheetTitle>检索测试</SheetTitle>
          <SheetDescription>
            在当前知识库范围内测试混合、向量与关键词检索效果
          </SheetDescription>
        </SheetHeader>

        <div className='space-y-4 pt-2'>
          <div className='space-y-2'>
            <Label htmlFor='retrieval-query'>测试问题</Label>
            <div className='flex gap-2'>
              <Input
                id='retrieval-query'
                value={query}
                placeholder='例如：暑期班多少钱？'
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') void handleSearch()
                }}
              />
              <Button
                type='button'
                disabled={loading}
                onClick={() => void handleSearch()}
              >
                <Search className='mr-1 size-4' />
                {loading ? '检索中…' : '检索'}
              </Button>
            </div>
          </div>

          <Tabs
            value={mode}
            onValueChange={(v) => {
              const next = v as ChunkSearchMode
              setMode(next)
              if (query.trim()) void handleSearch(next)
            }}
            className='flex min-h-0 flex-1 flex-col'
          >
            <TabsList className='grid w-full grid-cols-3'>
              <TabsTrigger value='hybrid'>混合检索</TabsTrigger>
              <TabsTrigger value='semantic'>向量检索</TabsTrigger>
              <TabsTrigger value='keyword'>关键词</TabsTrigger>
            </TabsList>

            {(['hybrid', 'semantic', 'keyword'] as const).map((tabMode) => (
              <TabsContent
                key={tabMode}
                value={tabMode}
                className='mt-3 min-h-0 flex-1 space-y-3'
              >
                {error ? <AppErrorAlert message={error} /> : null}

                {elapsedSec != null && mode === tabMode ? (
                  <p className='text-muted-foreground text-xs'>
                    {MODE_LABEL[tabMode]} · 返回 {hits.length} 条 · 耗时{' '}
                    {elapsedSec.toFixed(2)}s
                  </p>
                ) : (
                  <p className='text-muted-foreground text-xs'>
                    输入问题后点击检索，或切换 Tab 自动以对应模式重新检索
                  </p>
                )}

                {hits.length > 0 && mode === tabMode ? (
                  <ScrollArea className='h-[min(60vh,520px)]'>
                    <div className='space-y-3 pr-3'>
                      {hits.map((hit) => (
                        <div
                          key={hit.chunkId}
                          className='rounded-md border p-3 text-sm'
                        >
                          <div className='mb-2 flex flex-wrap items-center gap-2'>
                            {hit.fileName ? (
                              <Badge variant='outline' className='max-w-[240px] truncate'>
                                {hit.fileName}
                              </Badge>
                            ) : null}
                            {hit.score != null ? (
                              <Badge variant='secondary'>
                                score {hit.score.toFixed(3)}
                              </Badge>
                            ) : null}
                            {hit.positionLabel ? (
                              <span className='text-muted-foreground text-xs'>
                                {hit.positionLabel}
                              </span>
                            ) : null}
                            {hit.source ? (
                              <span className='text-muted-foreground text-xs'>
                                {hit.source}
                              </span>
                            ) : null}
                          </div>
                          <p className='text-xs leading-relaxed whitespace-pre-wrap'>
                            {hit.content}
                          </p>
                        </div>
                      ))}
                    </div>
                  </ScrollArea>
                ) : mode === tabMode && !loading && !error ? (
                  <p className='text-muted-foreground text-sm'>
                    暂无检索结果
                  </p>
                ) : null}
              </TabsContent>
            ))}
          </Tabs>
        </div>
      </SheetContent>
    </Sheet>
  )
}
