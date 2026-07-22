import { type ErrorComponentProps, useNavigate, useRouter } from '@tanstack/react-router'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'

type GeneralErrorProps = Partial<ErrorComponentProps> & {
  className?: string
  minimal?: boolean
}

export function GeneralError({
  error,
  reset,
  className,
  minimal = false,
}: GeneralErrorProps) {
  const navigate = useNavigate()
  const { history } = useRouter()
  const message =
    error instanceof Error ? error.message : error != null ? String(error) : ''

  return (
    <div className={cn('h-svh w-full', className)}>
      <div className='m-auto flex h-full w-full flex-col items-center justify-center gap-2 px-4'>
        {!minimal && (
          <h1 className='text-[7rem] leading-tight font-bold'>500</h1>
        )}
        <span className='font-medium'>Oops! Something went wrong {`:')`}</span>
        <p className='text-center text-muted-foreground'>
          We apologize for the inconvenience. <br /> Please try again later.
        </p>
        {import.meta.env.DEV && message ? (
          <pre className='mt-4 max-h-40 max-w-lg overflow-auto rounded-md border bg-muted p-3 text-start text-xs whitespace-pre-wrap'>
            {message}
          </pre>
        ) : null}
        {!minimal && (
          <div className='mt-6 flex gap-4'>
            <Button variant='outline' onClick={() => history.go(-1)}>
              Go Back
            </Button>
            {reset ? (
              <Button variant='outline' onClick={reset}>
                Retry
              </Button>
            ) : null}
            <Button onClick={() => navigate({ to: '/' })}>Back to Home</Button>
          </div>
        )}
      </div>
    </div>
  )
}
