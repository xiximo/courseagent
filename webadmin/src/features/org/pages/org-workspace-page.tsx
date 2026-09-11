import { useEffect, useState } from 'react'
import { Link } from '@tanstack/react-router'
import {
  BookOpen,
  Copy,
  CreditCard,
  MessageSquare,
  ScrollText,
  Sparkles,
  Users,
} from 'lucide-react'
import { ApiClientError } from '@/lib/api/client'
import { firstPublishedChatTarget } from '@/lib/auth/home-path'
import { getBillingMe, type BillingMe } from '@/lib/api/billing'
import { toast } from 'sonner'
import { useAuthStore } from '@/stores/auth-store'
import { AppErrorAlert } from '@/components/app-error-alert'
import { AppPageHeader } from '@/components/app-page-header'
import { Main } from '@/components/layout/main'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'

export function OrgWorkspacePage() {
  const user = useAuthStore((s) => s.auth.user)
  const [me, setMe] = useState<BillingMe | null>(null)
  const [chatTo, setChatTo] = useState<string | null>(null)
  const [chatAgentId, setChatAgentId] = useState<string>()
  const [error, setError] = useState<string>()

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const [billing, chat] = await Promise.all([
          getBillingMe(),
          firstPublishedChatTarget(),
        ])
        if (cancelled) return
        setMe(billing)
        if (chat?.params?.agentId) {
          setChatTo('/admin/chat/$agentId')
          setChatAgentId(chat.params.agentId)
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof ApiClientError ? e.message : '加载工作台失败')
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const tenantName = user?.tenantName || '本机构'
  const used = me?.usage.used ?? 0
  const limit = me?.usage.limit
  const remaining = me?.usage.remaining
  const isPro = me?.planCode === 'pro'

  return (
    <>
      <AppPageHeader />
      <Main className='flex flex-1 flex-col gap-6'>
        <div>
          <p className='text-muted-foreground text-sm'>机构工作台</p>
          <h1 className='mt-1 text-2xl font-bold tracking-tight'>
            {tenantName}
          </h1>
          <p className='text-muted-foreground mt-1'>
            欢迎，{user?.fullName || user?.username}。当前套餐为
            {isPro ? '专业版' : '免费版'}
            {limit != null
              ? `，本月已咨询 ${used} / ${limit} 次`
              : `，本月已咨询 ${used} 次`}
            。
          </p>
        </div>

        {error ? <AppErrorAlert message={error} /> : null}

        <div className='grid gap-4 sm:grid-cols-2 xl:grid-cols-3'>
          <Card>
            <CardHeader>
              <CardTitle className='flex items-center gap-2 text-base'>
                <Sparkles className='size-4' />
                当前套餐
              </CardTitle>
              <CardDescription>
                {isPro
                  ? '已解锁不限数量知识库、Harness Agent 与无限咨询'
                  : '免费版可用 1 个知识库、顾问配置与基础型 Agent'}
              </CardDescription>
            </CardHeader>
            <CardContent className='space-y-3'>
              <div className='text-2xl font-semibold'>
                {me?.planName ?? '加载中…'}
              </div>
              <p className='text-muted-foreground text-sm'>
                {remaining != null
                  ? `本月剩余 ${remaining} 次对话`
                  : '对话次数不限'}
              </p>
              <Button asChild variant={isPro ? 'outline' : 'default'}>
                <Link to='/plans' search={{ pay: undefined }}>
                  {isPro ? '查看套餐' : '升级专业版'}
                </Link>
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className='flex items-center gap-2 text-base'>
                <MessageSquare className='size-4' />
                顾问对话
              </CardTitle>
              <CardDescription>用本机构资料接待家长咨询</CardDescription>
            </CardHeader>
            <CardContent>
              {chatTo && chatAgentId ? (
                <Button asChild>
                  <Link to='/admin/chat/$agentId' params={{ agentId: chatAgentId }}>
                    开始咨询
                  </Link>
                </Button>
              ) : (
                <p className='text-muted-foreground text-sm'>
                  暂无已发布顾问，请稍后再试或联系平台。
                </p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className='flex items-center gap-2 text-base'>
                <Users className='size-4' />
                邀请成员
              </CardTitle>
              <CardDescription>
                把链接发给本机构的人，他们注册后使用你们的顾问
              </CardDescription>
            </CardHeader>
            <CardContent className='space-y-3'>
              {user?.tenantSlug ? (
                <>
                  <p className='text-muted-foreground break-all font-mono text-xs'>
                    {`${window.location.origin}/join/${user.tenantSlug}`}
                  </p>
                  <div className='flex flex-wrap gap-2'>
                    <Button
                      type='button'
                      variant='outline'
                      onClick={() => {
                        const url = `${window.location.origin}/join/${user.tenantSlug}`
                        void navigator.clipboard.writeText(url).then(
                          () => toast.success('邀请链接已复制'),
                          () => toast.error('复制失败')
                        )
                      }}
                    >
                      <Copy className='mr-1 size-4' />
                      复制链接
                    </Button>
                    <Button asChild variant='outline'>
                      <Link to='/admin/members'>管理成员</Link>
                    </Button>
                  </div>
                </>
              ) : (
                <p className='text-muted-foreground text-sm'>
                  当前账号尚未绑定机构。
                </p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className='flex items-center gap-2 text-base'>
                <BookOpen className='size-4' />
                常用入口
              </CardTitle>
              <CardDescription>资料、记录与用量</CardDescription>
            </CardHeader>
            <CardContent className='flex flex-wrap gap-2'>
              <Button asChild variant='outline'>
                <Link to='/admin/members'>成员</Link>
              </Button>
              <Button asChild variant='outline'>
                <Link to='/admin/course-agents'>顾问配置</Link>
              </Button>
              <Button asChild variant='outline'>
                <Link to='/admin/knowledge'>知识库</Link>
              </Button>
              <Button asChild variant='outline'>
                <Link to='/admin/course-agents/leads'>会话记录</Link>
              </Button>
              <Button asChild variant='outline'>
                <Link to='/admin/usage'>用量</Link>
              </Button>
              <Button asChild variant='outline'>
                <Link to='/plans' search={{ pay: undefined }}>
                  <CreditCard className='size-4' />
                  套餐
                </Link>
              </Button>
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className='flex items-center gap-2 text-base'>
              <ScrollText className='size-4' />
              接下来可以做什么
            </CardTitle>
          </CardHeader>
          <CardContent className='text-muted-foreground space-y-2 text-sm leading-7'>
            <p>1. 上传课程手册到知识库，并在顾问配置里绑定基础型 Agent、发布顾问。</p>
            <p>2. 在「成员」页复制邀请链接，发给教师、咨询顾问或家长；对方注册后即可咨询。</p>
            <p>3. 也可在成员页直接创建账号，把用户名和初始密码发给对方。</p>
            <p>4. 升级专业版后可创建 Harness Agent，并解除知识库数量与每月对话次数上限。</p>
          </CardContent>
        </Card>
      </Main>
    </>
  )
}
