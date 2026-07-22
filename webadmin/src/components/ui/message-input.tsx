import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ArrowUp, Info, Loader2, Square, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAutosizeTextArea } from '@/hooks/use-autosize-textarea'
import { Button } from '@/components/ui/button'

interface MessageInputProps
  extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  value: string
  submitOnEnter?: boolean
  stop?: () => void
  isGenerating: boolean
  enableInterrupt?: boolean
  /** 最大字数；超过后禁止发送并高亮计数 */
  maxLength?: number
}

export function MessageInput({
  placeholder = '输入问题…',
  className,
  onKeyDown: onKeyDownProp,
  submitOnEnter = true,
  stop,
  isGenerating,
  enableInterrupt = true,
  value,
  onChange,
  maxLength,
  disabled,
  ...props
}: MessageInputProps) {
  const [showInterruptPrompt, setShowInterruptPrompt] = useState(false)
  const textAreaRef = useRef<HTMLTextAreaElement | null>(null)
  const charCount = [...value].length
  const overLimit =
    typeof maxLength === 'number' && maxLength > 0 && charCount > maxLength
  const canSubmit = Boolean(value.trim()) && !isGenerating && !overLimit && !disabled

  useAutosizeTextArea({
    ref: textAreaRef,
    maxHeight: 200,
    borderWidth: 1,
    dependencies: [value],
  })

  useEffect(() => {
    if (!isGenerating) setShowInterruptPrompt(false)
  }, [isGenerating])

  const onKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (submitOnEnter && event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      if (isGenerating && stop && enableInterrupt) {
        if (showInterruptPrompt) {
          stop()
          setShowInterruptPrompt(false)
        } else {
          setShowInterruptPrompt(true)
        }
        return
      }
      if (!isGenerating && canSubmit) {
        event.currentTarget.form?.requestSubmit()
      }
    }
    onKeyDownProp?.(event)
  }

  return (
    <div className='relative flex w-full flex-col gap-2'>
      <AnimatePresence>
        {showInterruptPrompt ? (
          <motion.div
            initial={{ top: 0, filter: 'blur(5px)' }}
            animate={{
              top: -40,
              filter: 'blur(0px)',
              transition: {
                type: 'spring',
                filter: { type: 'tween' },
              },
            }}
            exit={{ top: 0, filter: 'blur(5px)' }}
            className='absolute left-1/2 flex -translate-x-1/2 overflow-hidden whitespace-nowrap rounded-full border bg-background py-1 text-center text-sm text-muted-foreground'
          >
            <span className='ms-2.5'>再次按 Enter 可中断生成</span>
            <button
              className='ms-1 me-2.5 flex items-center'
              type='button'
              onClick={() => setShowInterruptPrompt(false)}
              aria-label='Close'
            >
              <X className='h-3 w-3' />
            </button>
          </motion.div>
        ) : null}
      </AnimatePresence>

      <div
        className={cn(
          'relative rounded-xl border bg-background shadow-sm',
          overLimit && 'border-destructive'
        )}
      >
        <textarea
          autoFocus
          aria-label='Message input'
          placeholder={placeholder}
          value={value}
          onChange={onChange}
          onKeyDown={onKeyDown}
          ref={textAreaRef}
          rows={1}
          disabled={disabled || isGenerating}
          className={cn(
            'flex w-full resize-none rounded-xl bg-transparent px-3 py-3 text-sm placeholder:text-muted-foreground focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50',
            className
          )}
          {...props}
        />
        <div className='flex items-center justify-between gap-2 p-2 pt-0'>
          <div className='text-muted-foreground flex min-w-0 flex-col gap-0.5 text-xs'>
            <p className='flex items-center gap-1'>
              <Info className='h-3 w-3 shrink-0' />
              Enter 发送 · Shift+Enter 换行
            </p>
            {typeof maxLength === 'number' && maxLength > 0 ? (
              <p
                className={cn(
                  'ps-4',
                  overLimit ? 'text-destructive font-medium' : 'text-muted-foreground'
                )}
              >
                {charCount} / {maxLength} 字
                {overLimit ? ' · 已超限，请精简后再发送' : ''}
              </p>
            ) : null}
          </div>
          {isGenerating && stop ? (
            <Button
              type='button'
              size='icon'
              variant='outline'
              className='h-8 w-8 rounded-full'
              aria-label='Stop generating'
              onClick={stop}
            >
              <Square className='h-3 w-3 fill-current' />
            </Button>
          ) : (
            <Button
              type='submit'
              size='icon'
              className='h-8 w-8 rounded-full'
              aria-label='Send message'
              disabled={!canSubmit}
            >
              {isGenerating ? (
                <Loader2 className='h-4 w-4 animate-spin' />
              ) : (
                <ArrowUp className='h-4 w-4' />
              )}
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
