import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { cn } from '@/lib/utils'
import { CopyButton } from '@/components/ui/copy-button'

interface MarkdownRendererProps {
  children: string
}

export function MarkdownRenderer({ children }: MarkdownRendererProps) {
  return (
    <div className='space-y-3'>
      <Markdown
        remarkPlugins={[remarkGfm]}
        // react-markdown Components 与自定义 withClass 签名略有差异
        components={COMPONENTS as never}
      >
        {children}
      </Markdown>
    </div>
  )
}

function childrenTakeAllStringContents(element: unknown): string {
  if (typeof element === 'string') return element
  if (
    element &&
    typeof element === 'object' &&
    'props' in element &&
    (element as { props?: { children?: unknown } }).props?.children
  ) {
    const children = (element as { props: { children: unknown } }).props.children
    if (Array.isArray(children)) {
      return children.map((child) => childrenTakeAllStringContents(child)).join('')
    }
    return childrenTakeAllStringContents(children)
  }
  return ''
}

const CodeBlock = ({
  children,
  className,
  ...restProps
}: React.HTMLAttributes<HTMLPreElement> & { children: React.ReactNode }) => {
  const code =
    typeof children === 'string'
      ? children
      : childrenTakeAllStringContents(children)

  return (
    <div className='group/code relative mb-4'>
      <pre
        className={cn(
          'overflow-x-auto rounded-md border bg-background/50 p-4 font-mono text-sm',
          className
        )}
        {...restProps}
      >
        <code>{code}</code>
      </pre>
      <div className='invisible absolute top-2 right-2 flex space-x-1 rounded-lg p-1 opacity-0 transition-all duration-200 group-hover/code:visible group-hover/code:opacity-100'>
        <CopyButton content={code} copyMessage='已复制代码' />
      </div>
    </div>
  )
}

const COMPONENTS = {
  h1: withClass('h1', 'text-2xl font-semibold'),
  h2: withClass('h2', 'text-xl font-semibold'),
  h3: withClass('h3', 'text-lg font-semibold'),
  h4: withClass('h4', 'text-base font-semibold'),
  h5: withClass('h5', 'font-medium'),
  strong: withClass('strong', 'font-semibold'),
  a: withClass('a', 'text-primary underline underline-offset-2'),
  blockquote: withClass('blockquote', 'border-l-2 border-primary pl-4'),
  code: ({ children, className, ...rest }: React.HTMLAttributes<HTMLElement>) => {
    const match = /language-(\w+)/.exec(className || '')
    return match ? (
      <CodeBlock className={className} {...rest}>
        {children}
      </CodeBlock>
    ) : (
      <code
        className={cn(
          'font-mono [:not(pre)>&]:rounded-md [:not(pre)>&]:bg-background/50 [:not(pre)>&]:px-1 [:not(pre)>&]:py-0.5'
        )}
        {...rest}
      >
        {children}
      </code>
    )
  },
  pre: ({ children }: { children?: React.ReactNode }) => children,
  img: withClass('img', 'my-2 max-w-full rounded-md border'),
  ol: withClass('ol', 'list-decimal space-y-2 pl-6'),
  ul: withClass('ul', 'list-disc space-y-2 pl-6'),
  li: withClass('li', 'my-1.5'),
  table: withClass(
    'table',
    'w-full border-collapse overflow-y-auto rounded-md border border-foreground/20'
  ),
  th: withClass(
    'th',
    'border border-foreground/20 px-4 py-2 text-left font-bold'
  ),
  td: withClass('td', 'border border-foreground/20 px-4 py-2 text-left'),
  tr: withClass('tr', 'm-0 border-t p-0 even:bg-muted'),
  p: withClass('p', 'whitespace-pre-wrap'),
  hr: withClass('hr', 'border-foreground/20'),
}

function withClass(Tag: keyof React.JSX.IntrinsicElements, classes: string) {
  const Component = (props: Record<string, unknown>) => {
    const { node: _node, ...rest } = props
    const Elem = Tag as React.ElementType
    return <Elem className={classes} {...rest} />
  }
  Component.displayName = Tag
  return Component
}
