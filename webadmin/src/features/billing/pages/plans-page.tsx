import { useCallback, useEffect, useState } from 'react'
import { useSearch } from '@tanstack/react-router'
import { Check, Sparkles } from 'lucide-react'
import { toast } from 'sonner'
import { ApiClientError } from '@/lib/api/client'
import {
  createBillingOrder,
  getBillingMe,
  getBillingPayOptions,
  listBillingPlans,
  mockPayBillingOrder,
  startAlipayPagePay,
  startStripeCheckout,
  type BillingMe,
  type BillingPayOptions,
  type BillingPlan,
} from '@/lib/api/billing'
import { AppErrorAlert } from '@/components/app-error-alert'
import { AppPageHeader } from '@/components/app-page-header'
import { Main } from '@/components/layout/main'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { useAuthStore } from '@/stores/auth-store'

export function PlansPage() {
  const search = useSearch({ from: '/_authenticated/plans/' })
  const [plans, setPlans] = useState<BillingPlan[]>([])
  const [me, setMe] = useState<BillingMe | null>(null)
  const [options, setOptions] = useState<BillingPayOptions | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string>()
  const [paying, setPaying] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)

  const reload = useCallback(async () => {
    setLoading(true)
    setError(undefined)
    try {
      const [planRows, mine, payOptions] = await Promise.all([
        listBillingPlans(),
        getBillingMe(),
        getBillingPayOptions(),
      ])
      setPlans(planRows)
      setMe(mine)
      setOptions(payOptions)
      const current = useAuthStore.getState().auth.user
      if (current) {
        useAuthStore.getState().auth.setUser({
          ...current,
          planCode: mine.planCode,
        })
      }
    } catch (e) {
      setError(e instanceof ApiClientError ? e.message : '加载套餐失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void reload()
  }, [reload])

  useEffect(() => {
    if (search.pay === 'success') {
      toast.success('Stripe 测试支付成功，已升级为专业版')
      void reload()
    } else if (search.pay === 'failed') {
      toast.error('支付未完成或订单未找到，请重试')
    } else if (search.pay === 'canceled') {
      toast.message('已取消支付')
    }
  }, [reload, search.pay])

  const handleStripePay = async () => {
    setPaying(true)
    try {
      const order = await createBillingOrder('pro')
      const pay = await startStripeCheckout(order.id)
      window.location.href = pay.payUrl
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : '发起 Stripe 支付失败')
      setPaying(false)
    }
  }

  const handleAlipayPay = async () => {
    setPaying(true)
    try {
      const order = await createBillingOrder('pro')
      const pay = await startAlipayPagePay(order.id)
      window.location.href = pay.payUrl
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : '发起支付宝支付失败')
      setPaying(false)
    }
  }

  const handleMockPay = async () => {
    setPaying(true)
    try {
      const order = await createBillingOrder('pro')
      await mockPayBillingOrder(order.id)
      toast.success('支付成功，已升级为专业版')
      setConfirmOpen(false)
      await reload()
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : '支付失败')
    } finally {
      setPaying(false)
    }
  }

  const usageText = me
    ? me.usage.limit == null
      ? `本月已对话 ${me.usage.used} 次（专业版不限次数）`
      : `本月已用 ${me.usage.used} / ${me.usage.limit} 次，剩余 ${me.usage.remaining ?? 0} 次`
    : ''

  return (
    <>
      <AppPageHeader />
      <Main className='flex flex-1 flex-col gap-6'>
        <div>
          <h1 className='text-2xl font-bold tracking-tight'>套餐与用量</h1>
          <p className='text-muted-foreground mt-1'>
            对比免费版与专业版权益。两边都能管理知识库和顾问配置；免费版限 1 个知识库，专业版不限数量，并开放 Harness Agent 与无限对话。
          </p>
        </div>

        {error ? <AppErrorAlert message={error} /> : null}

        {me ? (
          <Card>
            <CardHeader>
              <CardTitle className='flex items-center gap-2'>
                当前套餐
                <Badge variant={me.planCode === 'pro' ? 'default' : 'secondary'}>
                  {me.planName}
                </Badge>
              </CardTitle>
              <CardDescription>{usageText}</CardDescription>
            </CardHeader>
          </Card>
        ) : null}

        {loading ? (
          <p className='text-muted-foreground'>加载中…</p>
        ) : (
          <div className='grid gap-4 md:grid-cols-2'>
            {plans.map((plan) => {
              const current = me?.planCode === plan.code
              return (
                <Card
                  key={plan.code}
                  className={plan.highlighted ? 'border-primary shadow-sm' : ''}
                >
                  <CardHeader>
                    <div className='flex items-center justify-between'>
                      <CardTitle>{plan.name}</CardTitle>
                      {plan.highlighted ? (
                        <Badge>
                          <Sparkles className='mr-1 size-3' />
                          推荐
                        </Badge>
                      ) : null}
                    </div>
                    <CardDescription className='text-2xl font-semibold text-foreground'>
                      {plan.priceLabel}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <ul className='space-y-2 text-sm'>
                      {plan.features.map((item) => (
                        <li key={item} className='flex items-start gap-2'>
                          <Check className='text-primary mt-0.5 size-4 shrink-0' />
                          <span>{item}</span>
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                  <CardFooter>
                    {current ? (
                      <Button disabled className='w-full'>
                        当前方案
                      </Button>
                    ) : plan.code === 'pro' ? (
                      <Button
                        className='w-full'
                        onClick={() => setConfirmOpen(true)}
                      >
                        立即升级
                      </Button>
                    ) : (
                      <Button variant='outline' disabled className='w-full'>
                        免费使用中
                      </Button>
                    )}
                  </CardFooter>
                </Card>
              )
            })}
          </div>
        )}
      </Main>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Stripe 测试支付专业版</DialogTitle>
            <DialogDescription>
              {options?.stripeReady
                ? '将跳转 Stripe Checkout。测试卡 4242 4242 4242 4242，有效期填未来年月如 12/28（不要填 22 这种已过年份），CVC 填任意 3 位如 123。'
                : '尚未配置 STRIPE_SECRET_KEY。填好 backend/.env 后即可跳转测试收银台。'}
            </DialogDescription>
          </DialogHeader>
          <div className='space-y-2 rounded-md border px-3 py-2 text-sm'>
            <div>应付金额：¥199.00</div>
            <div className='text-muted-foreground'>
              渠道：Stripe {options?.stripeMode === 'test' ? '测试模式' : options?.stripeMode || ''}
              {options?.stripeReady ? '（已配置）' : '（未配置密钥）'}
            </div>
          </div>
          <DialogFooter className='flex-col gap-2 sm:flex-row sm:justify-end'>
            <Button
              variant='outline'
              onClick={() => setConfirmOpen(false)}
              disabled={paying}
            >
              取消
            </Button>
            {options?.mockPayEnabled ? (
              <Button
                variant='secondary'
                onClick={() => void handleMockPay()}
                disabled={paying}
              >
                {paying ? '处理中…' : '本地模拟支付'}
              </Button>
            ) : null}
            {options?.alipayReady ? (
              <Button
                variant='secondary'
                onClick={() => void handleAlipayPay()}
                disabled={paying}
              >
                {paying ? '跳转中…' : '去支付宝沙箱支付'}
              </Button>
            ) : null}
            <Button onClick={() => void handleStripePay()} disabled={paying}>
              {paying ? '跳转中…' : '去 Stripe 测试支付'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
