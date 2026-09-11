import { createFileRoute } from '@tanstack/react-router'
import { SignUp } from '@/features/auth/sign-up'

export const Route = createFileRoute('/(auth)/sign-up')({
  component: SignUp,
  validateSearch: (search: Record<string, unknown>) => ({
    intent: search.intent === 'pro' ? ('pro' as const) : undefined,
  }),
})
