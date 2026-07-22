type AuthLayoutProps = {
  children: React.ReactNode
}

export function AuthLayout({ children }: AuthLayoutProps) {
  return (
    <div className='relative min-h-svh overflow-hidden bg-gradient-to-br from-background via-background to-primary/5'>
      <div
        aria-hidden
        className='pointer-events-none absolute -end-24 -top-24 h-72 w-72 rounded-full bg-primary/10 blur-3xl'
      />
      <div
        aria-hidden
        className='pointer-events-none absolute -bottom-24 -start-24 h-72 w-72 rounded-full bg-emerald-500/10 blur-3xl'
      />
      <div className='container relative flex min-h-svh max-w-none items-center justify-center px-4 py-10'>
        {children}
      </div>
    </div>
  )
}
