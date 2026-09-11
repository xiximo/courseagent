import { createFileRoute } from '@tanstack/react-router'
import { PlansPage } from '@/features/billing/pages/plans-page'
import { appRouteGuard } from '@/lib/auth/route-guard'

export const Route = createFileRoute('/_authenticated/plans/')({
  validateSearch: (search: Record<string, unknown>) => ({
    pay: typeof search.pay === 'string' ? search.pay : undefined,
  }),
  beforeLoad: () => {
    appRouteGuard('/plans')
  },
  component: PlansPage,
})
