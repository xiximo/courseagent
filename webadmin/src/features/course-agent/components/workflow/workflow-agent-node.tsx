import { Handle, Position, type NodeProps } from '@xyflow/react'
import { cn } from '@/lib/utils'
import {
  NODE_TYPE_META,
  type WorkflowFlowNode,
} from '../../lib/workflow-graph'

export function WorkflowAgentNode({
  data,
  selected,
}: NodeProps<WorkflowFlowNode>) {
  const meta = NODE_TYPE_META[data.nodeType]
  return (
    <div
      className={cn(
        'w-[210px] rounded-xl border-2 px-3 py-2.5 shadow-sm transition-shadow',
        meta?.tone ?? 'border-border bg-card',
        selected && 'ring-primary shadow-md ring-2'
      )}
    >
      <Handle type='target' position={Position.Left} className='!bg-slate-400' />
      <div className='space-y-1'>
        <div className='flex items-center justify-between gap-2'>
          <p className='text-sm font-semibold leading-tight'>{data.name}</p>
        </div>
        <p className='font-mono text-[10px] text-slate-500'>{data.nodeType}</p>
        <p className='text-muted-foreground line-clamp-2 text-[11px] leading-snug'>
          {data.summary}
        </p>
        <p className='text-[10px] text-slate-400'>{meta?.contract}</p>
      </div>
      <Handle type='source' position={Position.Right} className='!bg-slate-400' />
    </div>
  )
}
