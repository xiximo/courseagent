import { useState, type ReactNode } from 'react'
import { Link, useNavigate } from '@tanstack/react-router'
import {
  ArrowRight,
  BookOpen,
  Building2,
  Check,
  GraduationCap,
  MessageSquare,
  ShieldCheck,
  Sparkles,
  Users,
} from 'lucide-react'
import { isPlatformAdmin } from '@/lib/auth/permissions'
import { resolveLoggedInHome } from '@/lib/auth/home-path'
import { useAuthStore } from '@/stores/auth-store'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

const PLANS = [
  {
    name: '免费版',
    price: '¥0',
    period: '/ 月',
    desc: '适合机构先试用顾问对话',
    features: ['每月 50 次课程咨询', '1 个知识库与顾问配置', '基础型 Agent'],
    cta: '免费开始',
    highlighted: false,
  },
  {
    name: '专业版',
    price: '¥199',
    period: '/ 月',
    desc: '适合正式对外提供咨询服务',
    features: [
      '无限对话次数',
      '不限数量知识库与顾问配置',
      '基础型 Agent + Harness Agent',
      '对话记录与用量看板',
    ],
    cta: '升级专业版',
    highlighted: true,
  },
] as const

export function LandingPage() {
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.auth.user)
  const [entering, setEntering] = useState(false)

  const enterWorkspace = async () => {
    setEntering(true)
    try {
      const dest = await resolveLoggedInHome()
      if (dest.params?.agentId) {
        navigate({
          to: '/admin/chat/$agentId',
          params: { agentId: dest.params.agentId },
        })
        return
      }
      navigate({
        to: dest.to as
          | '/admin'
          | '/saasadmin'
          | '/admin/course-agents'
          | '/settings/account',
      })
    } finally {
      setEntering(false)
    }
  }

  return (
    <div className="landing-root min-h-svh bg-[#f4efe4] text-[#1c2a22] antialiased [--font-serif:'Noto_Serif_SC',serif]">
      <div
        aria-hidden
        className='pointer-events-none fixed inset-0 bg-[radial-gradient(ellipse_at_top,#e7dcc4_0%,transparent_55%)]'
      />
      <Header
        loggedIn={Boolean(user)}
        entering={entering}
        onEnterWorkspace={() => void enterWorkspace()}
      />

      <main className='relative'>
        <Hero
          loggedIn={Boolean(user)}
          entering={entering}
          onEnterWorkspace={() => void enterWorkspace()}
        />
        <TrustBar />
        <Capabilities />
        <HowItWorks />
        <Pricing />
        <ClosingCta
          loggedIn={Boolean(user)}
          entering={entering}
          onEnterWorkspace={() => void enterWorkspace()}
        />
      </main>

      <Footer />
    </div>
  )
}

function Header({
  loggedIn,
  entering,
  onEnterWorkspace,
}: {
  loggedIn: boolean
  entering: boolean
  onEnterWorkspace: () => void
}) {
  return (
    <header className='sticky top-0 z-40 border-b border-[#1c2a22]/8 bg-[#f4efe4]/80 backdrop-blur-md'>
      <div className='mx-auto flex h-16 max-w-6xl items-center justify-between px-5'>
        <Link to='/' className='flex items-center gap-2.5'>
          <span className='flex size-9 items-center justify-center rounded-xl bg-[#1f6b4a] text-[#f4efe4]'>
            <GraduationCap className='size-5' />
          </span>
          <span className='leading-tight'>
            <span className='block font-serif text-[15px] font-semibold tracking-wide'>
              启明顾问
            </span>
            <span className='block text-[11px] text-[#1c2a22]/55'>
              AI 教育顾问 SaaS
            </span>
          </span>
        </Link>
        <nav className='hidden items-center gap-8 text-sm text-[#1c2a22]/70 md:flex'>
          <a href='#capabilities' className='hover:text-[#1c2a22]'>
            产品能力
          </a>
          <a href='#how' className='hover:text-[#1c2a22]'>
            开通流程
          </a>
          <a href='#pricing' className='hover:text-[#1c2a22]'>
            套餐
          </a>
        </nav>
        <div className='flex items-center gap-2'>
          {loggedIn ? (
            <Button
              className='bg-[#1f6b4a] text-[#f4efe4] hover:bg-[#18583c]'
              onClick={onEnterWorkspace}
              disabled={entering}
            >
              进入工作台
            </Button>
          ) : (
            <>
              <Button
                variant='ghost'
                className='hidden text-[#1c2a22] hover:bg-[#1c2a22]/6 sm:inline-flex'
                asChild
              >
                <Link to='/sign-in'>登录</Link>
              </Button>
              <Button
                className='bg-[#1f6b4a] text-[#f4efe4] hover:bg-[#18583c]'
                asChild
              >
                <Link to='/sign-up' search={{ intent: undefined }}>
                  免费试用
                </Link>
              </Button>
            </>
          )}
        </div>
      </div>
    </header>
  )
}

function Hero({
  loggedIn,
  entering,
  onEnterWorkspace,
}: {
  loggedIn: boolean
  entering: boolean
  onEnterWorkspace: () => void
}) {
  return (
    <section className='mx-auto grid max-w-6xl items-center gap-12 px-5 pt-16 pb-20 md:grid-cols-[1.05fr_0.95fr] md:pt-24'>
      <div>
        <p className='mb-4 inline-flex items-center gap-2 rounded-full border border-[#1f6b4a]/20 bg-[#1f6b4a]/8 px-3 py-1 text-xs font-medium text-[#1f6b4a]'>
          <Sparkles className='size-3.5' />
          面向教育机构的可授权 SaaS
        </p>
        <h1 className='font-serif text-4xl leading-[1.15] font-semibold tracking-tight text-[#1c2a22] sm:text-5xl'>
          把课程顾问
          <br />
          做成可对外授权的能力
        </h1>
        <p className='mt-5 max-w-xl text-base leading-7 text-[#1c2a22]/70 sm:text-[17px]'>
          启明顾问帮助培训机构、学校与教研中心，用自己的课程资料回答家长咨询、推荐班型，并按套餐管理用量。无需自建大模型团队，15
          分钟即可演示上线。
        </p>
        <div className='mt-8 flex flex-wrap items-center gap-3'>
          {loggedIn ? (
            <Button
              size='lg'
              className='h-11 bg-[#1f6b4a] px-6 text-[#f4efe4] hover:bg-[#18583c]'
              onClick={onEnterWorkspace}
              disabled={entering}
            >
              进入工作台
              <ArrowRight className='size-4' />
            </Button>
          ) : (
            <>
              <Button
                size='lg'
                className='h-11 bg-[#1f6b4a] px-6 text-[#f4efe4] hover:bg-[#18583c]'
                asChild
              >
                <Link to='/sign-up' search={{ intent: undefined }}>
                  开通机构空间
                  <ArrowRight className='size-4' />
                </Link>
              </Button>
              <Button
                size='lg'
                variant='outline'
                className='h-11 border-[#1c2a22]/15 bg-transparent px-6 text-[#1c2a22] hover:bg-[#1c2a22]/5'
                asChild
              >
                <a href='#pricing'>查看套餐</a>
              </Button>
            </>
          )}
        </div>
        <p className='mt-4 text-xs text-[#1c2a22]/45'>
          免费版每月 50 次对话、1 个知识库 · 专业版不限知识库数量，并开放 Harness Agent
        </p>
      </div>

      <HeroPreview />
    </section>
  )
}

function HeroPreview() {
  return (
    <div className='relative'>
      <div
        aria-hidden
        className='absolute -inset-6 rounded-[2rem] bg-[#1f6b4a]/8 blur-2xl'
      />
      <div className='relative overflow-hidden rounded-[1.6rem] border border-[#1c2a22]/8 bg-[#fbf7ef] shadow-[0_24px_60px_-28px_rgba(28,42,34,0.35)]'>
        <div className='flex items-center justify-between border-b border-[#1c2a22]/8 px-5 py-3.5'>
          <div className='flex items-center gap-2 text-sm font-medium'>
            <span className='size-2 rounded-full bg-[#1f6b4a]' />
            启明课程顾问
          </div>
          <span className='rounded-full bg-[#c4a35a]/15 px-2.5 py-0.5 text-[11px] text-[#8a7040]'>
            专业版 · 引用溯源
          </span>
        </div>
        <div className='space-y-4 px-5 py-5'>
          <ChatBubble align='user'>我在上海，只有周末有空，想给老师报班。</ChatBubble>
          <ChatBubble align='assistant'>
            根据您的城市与时间，推荐 <b>周末研修班</b>
            ：每周六全天、浦东校区、1800 元/期，适合在职教师持续学习。
            <span className='mt-2 block text-[11px] text-[#1f6b4a]'>
              来源：班型目录 · 周末研修班
            </span>
          </ChatBubble>
          <div className='flex flex-wrap gap-2'>
            {['北京线下班详情', '只有工作日能上课', '费用怎么算'].map((item) => (
              <span
                key={item}
                className='rounded-full border border-[#1c2a22]/10 bg-white/70 px-3 py-1 text-[12px] text-[#1c2a22]/70'
              >
                {item}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function ChatBubble({
  align,
  children,
}: {
  align: 'user' | 'assistant'
  children: ReactNode
}) {
  return (
    <div className={cn('flex', align === 'user' ? 'justify-end' : 'justify-start')}>
      <div
        className={cn(
          'max-w-[90%] rounded-2xl px-4 py-3 text-sm leading-6',
          align === 'user'
            ? 'bg-[#1c2a22] text-[#f4efe4]'
            : 'bg-white text-[#1c2a22] shadow-sm ring-1 ring-[#1c2a22]/6'
        )}
      >
        {children}
      </div>
    </div>
  )
}

function TrustBar() {
  const items = [
    { icon: Building2, label: '多机构独立空间' },
    { icon: BookOpen, label: '自有课程资料作答' },
    { icon: Users, label: '班型查询与推荐' },
    { icon: ShieldCheck, label: '用量与套餐可控' },
  ]
  return (
    <section className='border-y border-[#1c2a22]/8 bg-[#efe7d6]/70'>
      <div className='mx-auto grid max-w-6xl grid-cols-2 gap-6 px-5 py-8 md:grid-cols-4'>
        {items.map((item) => (
          <div
            key={item.label}
            className='flex items-center gap-3 text-sm text-[#1c2a22]/75'
          >
            <item.icon className='size-4 text-[#1f6b4a]' />
            {item.label}
          </div>
        ))}
      </div>
    </section>
  )
}

function Capabilities() {
  const cards = [
    {
      icon: BookOpen,
      title: '课程知识库',
      body: '上传 PDF 手册后自动解析、切片与检索。回答带文档名和章节，资料外的问题明确说明不在知识范围内。',
    },
    {
      icon: GraduationCap,
      title: '班型顾问 Skill',
      body: '查询班型时间、地点、费用、师资与大纲；按城市和时间偏好推荐 1–2 个班，参数不足时请用户补充。',
    },
    {
      icon: MessageSquare,
      title: '多轮咨询对话',
      body: '家长与教师可以连续追问。顾问记住约束，把推荐、详情和报名说明放在同一段对话里完成。',
    },
    {
      icon: ShieldCheck,
      title: '机构后台雏形',
      body: '知识库、顾问配置、脱敏对话记录与用量统计。免费版限 1 个知识库和基础型 Agent，专业版不限知识库数量，并开放 Harness 与无限对话。',
    },
  ]
  return (
    <section id='capabilities' className='mx-auto max-w-6xl px-5 py-20'>
      <div className='max-w-2xl'>
        <p className='text-xs font-medium tracking-[0.18em] text-[#1f6b4a] uppercase'>
          产品能力
        </p>
        <h2 className='mt-3 font-serif text-3xl font-semibold'>
          机构需要的，不只是一个聊天框
        </h2>
        <p className='mt-3 text-[#1c2a22]/65'>
          从获客咨询到资料治理，启明顾问把课程顾问做成可复制给其他教育机构的标准产品。
        </p>
      </div>
      <div className='mt-10 grid gap-4 md:grid-cols-2'>
        {cards.map((card) => (
          <article
            key={card.title}
            className='rounded-2xl border border-[#1c2a22]/8 bg-[#fbf7ef] p-6 shadow-[0_10px_30px_-24px_rgba(28,42,34,0.45)]'
          >
            <div className='mb-4 flex size-10 items-center justify-center rounded-xl bg-[#1f6b4a]/10 text-[#1f6b4a]'>
              <card.icon className='size-5' />
            </div>
            <h3 className='font-serif text-xl font-semibold'>{card.title}</h3>
            <p className='mt-2 text-sm leading-7 text-[#1c2a22]/68'>{card.body}</p>
          </article>
        ))}
      </div>
    </section>
  )
}

function HowItWorks() {
  const steps = [
    { n: '01', title: '开通机构空间', body: '填写机构信息完成注册，自动进入机构工作台，套餐默认为免费版。' },
    { n: '02', title: '挂上课程资料', body: '上传班型手册或服务说明，系统完成解析与索引。' },
    { n: '03', title: '顾问开始接待', body: '把邀请链接发给教师或家长，他们注册后即可咨询；超限时引导升级专业版。' },
  ]
  return (
    <section id='how' className='bg-[#1c2a22] text-[#f4efe4]'>
      <div className='mx-auto max-w-6xl px-5 py-20'>
        <p className='text-xs font-medium tracking-[0.18em] text-[#c4a35a] uppercase'>
          开通流程
        </p>
        <h2 className='mt-3 font-serif text-3xl font-semibold'>三步，把顾问交给自己的机构</h2>
        <div className='mt-10 grid gap-8 md:grid-cols-3'>
          {steps.map((step) => (
            <div key={step.n} className='border-t border-[#f4efe4]/15 pt-6'>
              <div className='font-serif text-sm text-[#c4a35a]'>{step.n}</div>
              <h3 className='mt-2 text-xl font-medium'>{step.title}</h3>
              <p className='mt-2 text-sm leading-7 text-[#f4efe4]/65'>{step.body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

function ProPlanLink({ children }: { children: ReactNode }) {
  const user = useAuthStore((s) => s.auth.user)
  if (!user) {
    return (
      <Link to='/sign-up' search={{ intent: 'pro' }}>
        {children}
      </Link>
    )
  }
  if (isPlatformAdmin(user.roleCodes ?? [])) {
    return <Link to='/saasadmin'>{children}</Link>
  }
  if (user.planCode === 'pro') {
    return <Link to='/admin'>{children}</Link>
  }
  return (
    <Link to='/plans' search={{ pay: undefined }}>
      {children}
    </Link>
  )
}

function Pricing() {
  return (
    <section id='pricing' className='mx-auto max-w-6xl px-5 py-20'>
      <div className='text-center'>
        <p className='text-xs font-medium tracking-[0.18em] text-[#1f6b4a] uppercase'>
          订阅套餐
        </p>
        <h2 className='mt-3 font-serif text-3xl font-semibold'>先试用，再为正式接待升级</h2>
        <p className='mx-auto mt-3 max-w-xl text-[#1c2a22]/65'>
          专业版挂在机构名下。未开通时先注册机构，再进入套餐页完成 Stripe 测试支付。
        </p>
      </div>
      <div className='mx-auto mt-10 grid max-w-3xl gap-5 md:grid-cols-2'>
        {PLANS.map((plan) => (
          <article
            key={plan.name}
            className={cn(
              'flex h-full flex-col rounded-2xl border p-6',
              plan.highlighted
                ? 'border-[#1f6b4a] bg-[#1f6b4a] text-[#f4efe4] shadow-lg'
                : 'border-[#1c2a22]/8 bg-[#fbf7ef]'
            )}
          >
            <div className='text-sm opacity-80'>{plan.name}</div>
            <div className='mt-2 flex items-baseline gap-1'>
              <span className='font-serif text-4xl'>{plan.price}</span>
              <span className='text-sm opacity-70'>{plan.period}</span>
            </div>
            <p
              className={cn(
                'mt-2 min-h-10 text-sm',
                plan.highlighted ? 'text-[#f4efe4]/75' : 'text-[#1c2a22]/60'
              )}
            >
              {plan.desc}
            </p>
            <ul className='mt-5 min-h-36 flex-1 space-y-2.5 text-sm'>
              {plan.features.map((item) => (
                <li key={item} className='flex items-start gap-2'>
                  <Check className='mt-0.5 size-4 shrink-0' />
                  {item}
                </li>
              ))}
            </ul>
            <Button
              className={cn(
                'mt-6 w-full',
                plan.highlighted
                  ? 'bg-[#f4efe4] text-[#1f6b4a] hover:bg-white'
                  : 'bg-[#1c2a22] text-[#f4efe4] hover:bg-[#1c2a22]/90'
              )}
              asChild
            >
              {plan.highlighted ? (
                <ProPlanLink>{plan.cta}</ProPlanLink>
              ) : (
                <Link to='/sign-up' search={{ intent: undefined }}>
                  {plan.cta}
                </Link>
              )}
            </Button>
          </article>
        ))}
      </div>
    </section>
  )
}

function ClosingCta({
  loggedIn,
  entering,
  onEnterWorkspace,
}: {
  loggedIn: boolean
  entering: boolean
  onEnterWorkspace: () => void
}) {
  return (
    <section className='px-5 pb-20'>
      <div className='mx-auto max-w-6xl overflow-hidden rounded-[1.8rem] bg-[linear-gradient(135deg,#1f6b4a_0%,#163d2d_55%,#1c2a22_100%)] px-8 py-14 text-[#f4efe4] md:px-14'>
        <h2 className='max-w-xl font-serif text-3xl font-semibold'>
          让每一所合作机构，都有一位懂自己课程的顾问
        </h2>
        <p className='mt-3 max-w-lg text-sm leading-7 text-[#f4efe4]/70'>
          用同一套产品服务不同校区与项目。资料在本机构空间内管理，用量按套餐计量。
        </p>
        <div className='mt-8'>
          {loggedIn ? (
            <Button
              size='lg'
              className='bg-[#f4efe4] text-[#1f6b4a] hover:bg-white'
              onClick={onEnterWorkspace}
              disabled={entering}
            >
              进入工作台
            </Button>
          ) : (
            <Button
              size='lg'
              className='bg-[#f4efe4] text-[#1f6b4a] hover:bg-white'
              asChild
            >
              <Link to='/sign-in'>预约演示 / 立即登录</Link>
            </Button>
          )}
        </div>
      </div>
    </section>
  )
}

function Footer() {
  return (
    <footer className='border-t border-[#1c2a22]/8 px-5 py-8 text-sm text-[#1c2a22]/50'>
      <div className='mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3'>
        <span>启明顾问 · AI 教育顾问 SaaS MVP</span>
        <span>供教育机构授权演示，不构成真实招生承诺</span>
      </div>
    </footer>
  )
}
