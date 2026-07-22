import { type QueryClient } from '@tanstack/react-query'
import { createRootRouteWithContext, Outlet } from '@tanstack/react-router'
// import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
// import { TanStackRouterDevtools } from '@tanstack/react-router-devtools'
import { Toaster } from '@/components/ui/sonner'
import { NavigationProgress } from '@/components/navigation-progress'
import { DirectionProvider } from '@/context/direction-provider'
import { FontProvider } from '@/context/font-provider'
import { LocaleProvider } from '@/context/locale-provider'
import { ThemeProvider } from '@/context/theme-provider'
import { GeneralError } from '@/features/errors/general-error'
import { NotFoundError } from '@/features/errors/not-found-error'

function RootShell() {
  return (
    <LocaleProvider>
      <ThemeProvider>
        <FontProvider>
          <DirectionProvider>
            <NavigationProgress />
            <Outlet />
            <Toaster duration={5000} />
            {/* {import.meta.env.MODE === 'development' && (
              <>
                <ReactQueryDevtools buttonPosition='bottom-left' />
                <TanStackRouterDevtools position='bottom-right' />
              </>
            )} */}
          </DirectionProvider>
        </FontProvider>
      </ThemeProvider>
    </LocaleProvider>
  )
}

export const Route = createRootRouteWithContext<{
  queryClient: QueryClient
}>()({
  component: RootShell,
  notFoundComponent: NotFoundError,
  errorComponent: GeneralError,
})
