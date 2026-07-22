import { ExternalLink, FileText } from 'lucide-react'
import { toast } from 'sonner'
import type { CourseAgentCitation } from '../data/types'

type MessageCitationLinksProps = {
  citations?: CourseAgentCitation[]
  onOpenCitation: (citation: CourseAgentCitation) => void
}

export function MessageCitationLinks({
  citations,
  onOpenCitation,
}: MessageCitationLinksProps) {
  if (!citations?.length) return null

  return (
    <div className='mt-2 space-y-1.5 border-t border-border/60 pt-2'>
      <p className='text-muted-foreground text-xs font-medium'>来源</p>
      <ul className='space-y-1.5'>
        {citations.map((citation, index) => {
          const label = `${citation.document}${citation.chapter ? ` · ${citation.chapter}` : ''}`

          return (
            <li key={`${citation.document}-${citation.chapter}-${index}`}>
              <button
                type='button'
                className='text-primary inline-flex max-w-full cursor-pointer items-start gap-1.5 text-left text-xs underline-offset-2 hover:underline'
                onClick={() => {
                  if (!citation.attachmentId) {
                    toast.error('未找到关联文档，请确认知识库已上传并解析该资料')
                    return
                  }
                  onOpenCitation(citation)
                }}
              >
                <FileText className='mt-0.5 size-3.5 shrink-0 opacity-80' />
                <span className='truncate'>{label}</span>
                <ExternalLink className='mt-0.5 size-3 shrink-0 opacity-70' />
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
