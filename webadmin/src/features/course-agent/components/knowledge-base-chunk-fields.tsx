import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import {
  DEFAULT_CHUNK_MAX_CHARS,
  DEFAULT_CHUNK_OVERLAP_CHARS,
  type KnowledgeChunkMode,
} from '../lib/knowledge-base-chunk'

type KnowledgeBaseChunkFieldsProps = {
  mode: KnowledgeChunkMode
  maxChars: number
  overlapChars: number
  disabled?: boolean
  onModeChange: (mode: KnowledgeChunkMode) => void
  onMaxCharsChange: (value: number) => void
  onOverlapCharsChange: (value: number) => void
}

export function KnowledgeBaseChunkFields({
  mode,
  maxChars,
  overlapChars,
  disabled,
  onModeChange,
  onMaxCharsChange,
  onOverlapCharsChange,
}: KnowledgeBaseChunkFieldsProps) {
  return (
    <div className='space-y-3'>
      <div className='space-y-2'>
        <Label>切片方式</Label>
        <RadioGroup
          value={mode}
          disabled={disabled}
          onValueChange={(value) => onModeChange(value as KnowledgeChunkMode)}
          className='gap-2'
        >
          <label className='flex items-start gap-2 text-sm'>
            <RadioGroupItem value='size' className='mt-0.5' />
            <span>
              <span className='font-medium'>按大小与重叠</span>
              <span className='text-muted-foreground block text-xs'>
                固定字符窗口切片，适合连续长文；重叠可避免关键句被切断。
              </span>
            </span>
          </label>
          <label className='flex items-start gap-2 text-sm'>
            <RadioGroupItem value='chapter' className='mt-0.5' />
            <span>
              <span className='font-medium'>按章节</span>
              <span className='text-muted-foreground block text-xs'>
                按标题、章、节切开。单章过长时再按大小切开。
              </span>
            </span>
          </label>
        </RadioGroup>
      </div>
      {mode === 'size' ? (
        <div className='grid gap-3 sm:grid-cols-2'>
          <div className='space-y-1.5'>
            <Label htmlFor='kb-chunk-size'>切片大小（字符）</Label>
            <Input
              id='kb-chunk-size'
              type='number'
              min={200}
              max={8000}
              step={100}
              disabled={disabled}
              value={maxChars}
              onChange={(e) => {
                const next = Number(e.target.value)
                onMaxCharsChange(
                  Number.isFinite(next) ? next : DEFAULT_CHUNK_MAX_CHARS
                )
              }}
            />
          </div>
          <div className='space-y-1.5'>
            <Label htmlFor='kb-chunk-overlap'>重叠（字符）</Label>
            <Input
              id='kb-chunk-overlap'
              type='number'
              min={0}
              max={4000}
              step={50}
              disabled={disabled}
              value={overlapChars}
              onChange={(e) => {
                const next = Number(e.target.value)
                onOverlapCharsChange(
                  Number.isFinite(next) ? next : DEFAULT_CHUNK_OVERLAP_CHARS
                )
              }}
            />
          </div>
        </div>
      ) : (
        <p className='text-muted-foreground text-xs'>
          识别「第 X 章 / 节」、Markdown 标题后按章节成块。已有文档保存后会按新方式重新切片。
        </p>
      )}
    </div>
  )
}
