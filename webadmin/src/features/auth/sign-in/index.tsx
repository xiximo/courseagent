import { Link, useSearch } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'
import { Logo } from '@/assets/logo'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { AuthLayout } from '../auth-layout'
import { UserAuthForm } from './components/user-auth-form'

export function SignIn() {
  const { t } = useTranslation()
  const { redirect } = useSearch({ from: '/(auth)/sign-in' })

  return (
    <AuthLayout>
      <Card className='w-full max-w-lg gap-0 border-border/60 px-2 py-2 shadow-xl sm:max-w-xl'>
        <CardHeader className='space-y-5 px-8 pt-10 pb-2 text-center'>
          <div className='mx-auto flex size-14 items-center justify-center rounded-2xl bg-blue-500/10'>
            <Logo className='size-9' />
          </div>
          <div className='space-y-2'>
            <h1 className='text-2xl font-semibold tracking-tight'>
              {t('auth.platformName')}
            </h1>
            {t('auth.platformTagline') ? (
              <p className='text-sm text-muted-foreground'>
                {t('auth.platformTagline')}
              </p>
            ) : null}
          </div>
        </CardHeader>
        <CardContent className='px-8 pt-4 pb-10'>
          <UserAuthForm redirectTo={redirect} className='gap-4' />
          <p className='text-muted-foreground mt-6 text-center text-sm'>
            机构成员请用管理员给的账号登录；还没有机构空间？{' '}
            <Link
              to='/sign-up'
              search={{ intent: undefined }}
              className='text-foreground underline underline-offset-4'
            >
              开通免费试用
            </Link>
          </p>
        </CardContent>
      </Card>
    </AuthLayout>
  )
}
