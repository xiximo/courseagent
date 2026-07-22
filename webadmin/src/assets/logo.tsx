import { type SVGProps } from 'react'
import { cn } from '@/lib/utils'

export function Logo({ className, ...props }: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox='0 0 24 24'
      xmlns='http://www.w3.org/2000/svg'
      height='24'
      width='24'
      fill='none'
      stroke='currentColor'
      strokeWidth='2'
      strokeLinecap='round'
      strokeLinejoin='round'
      className={cn('size-6 text-blue-600 dark:text-blue-400', className)}
      {...props}
    >
      <title>企业标准AI智能平台</title>
      <path d='M9 3h4l3 3v13a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h3z' />
      <path d='M13 3v3h3' />
      <path d='M8 11h6' />
      <path d='M8 14h6' />
      <path d='M8 17h4' />
      <path d='M18 5v2' />
      <path d='M19 6h-2' />
      <path d='M17.3 7.7l.7.7' />
      <path d='M17.3 4.3l.7-.7' />
    </svg>
  )
}
