import { AlertTriangle } from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'

type AppErrorAlertProps = {
  message?: string
  title?: string
}

export function AppErrorAlert({ message, title }: AppErrorAlertProps) {
  if (!message) return null

  return (
    <Alert variant='destructive'>
      <AlertTriangle className='h-4 w-4' />
      {title ? <AlertTitle>{title}</AlertTitle> : null}
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  )
}
