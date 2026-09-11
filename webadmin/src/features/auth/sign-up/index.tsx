import { Link, getRouteApi } from '@tanstack/react-router'
import { GraduationCap } from 'lucide-react'
import { SignUpForm } from './components/sign-up-form'

const signUpRoute = getRouteApi('/(auth)/sign-up')

export function SignUp() {
  const { intent } = signUpRoute.useSearch()
  const wantPro = intent === 'pro'
  return (
    <div className="min-h-svh bg-[#f4efe4] text-[#1c2a22] antialiased [--font-serif:'Noto_Serif_SC',serif]">
      <div
        aria-hidden
        className='pointer-events-none fixed inset-0 bg-[radial-gradient(ellipse_at_top,#e7dcc4_0%,transparent_55%)]'
      />
      <header className='relative mx-auto flex h-16 max-w-5xl items-center justify-between px-5'>
        <Link to='/' className='flex items-center gap-2.5'>
          <span className='flex size-9 items-center justify-center rounded-xl bg-[#1f6b4a] text-[#f4efe4]'>
            <GraduationCap className='size-5' />
          </span>
          <span className='leading-tight'>
            <span className='block font-serif text-[15px] font-semibold tracking-wide'>
              启明顾问
            </span>
            <span className='block text-[11px] text-[#1c2a22]/55'>开通机构空间</span>
          </span>
        </Link>
        <Link
          to='/sign-in'
          search={wantPro ? { redirect: '/plans' } : undefined}
          className='text-sm text-[#1c2a22]/70 underline-offset-4 hover:text-[#1c2a22] hover:underline'
        >
          已有账号？登录
        </Link>
      </header>

      <main className='relative mx-auto grid max-w-5xl gap-10 px-5 py-10 md:grid-cols-[1fr_1.05fr] md:py-16'>
        <div className='max-w-md'>
          <p className='text-xs font-medium tracking-[0.18em] text-[#1f6b4a] uppercase'>
            {wantPro ? '升级专业版' : '免费试用'}
          </p>
          <h1 className='mt-3 font-serif text-3xl font-semibold tracking-tight'>
            {wantPro ? '先开通机构，再完成支付' : '为你的机构开通顾问空间'}
          </h1>
          <p className='mt-4 text-sm leading-7 text-[#1c2a22]/68'>
            {wantPro
              ? '专业版挂在机构名下。提交后会先创建免费机构账号并登录，接着进入套餐页走 Stripe 测试支付。'
              : '提交后立即创建机构账号，默认进入免费版。完成后会自动登录并进入机构工作台。'}
          </p>
          <ul className='mt-6 space-y-2 text-sm text-[#1c2a22]/70'>
            {wantPro ? (
              <>
                <li>· 1. 填写机构信息开通账号</li>
                <li>· 2. 进入套餐页完成 Stripe 测试支付</li>
                <li>· 3. 支付成功后解锁 Harness 与无限对话</li>
              </>
            ) : (
              <>
                <li>· 每月 50 次课程咨询</li>
                <li>· 1 个知识库与基础型 Agent</li>
                <li>· 随时在工作台升级专业版</li>
              </>
            )}
          </ul>
        </div>
        <div className='rounded-2xl border border-[#1c2a22]/8 bg-[#fbf7ef] p-6 shadow-[0_24px_60px_-28px_rgba(28,42,34,0.35)] sm:p-8'>
          <SignUpForm intent={intent} />
        </div>
      </main>
    </div>
  )
}
