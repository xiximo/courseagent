import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from '@tanstack/react-router'
import { GraduationCap, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { z } from 'zod'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { registerMember } from '@/lib/api/auth'
import { getPublicTenant, type PublicTenant } from '@/lib/api/org'
import { ApiClientError, getApiErrorMessage } from '@/lib/api/client'
import { useAuthStore } from '@/stores/auth-store'
import { Button } from '@/components/ui/button'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { PasswordInput } from '@/components/password-input'
import { resolvePostLoginTarget } from '@/lib/auth/home-path'

const formSchema = z
  .object({
    fullName: z.string().trim().min(1, '请填写姓名'),
    username: z.string().trim().min(2, '用户名至少 2 位'),
    password: z.string().min(6, '密码至少 6 位'),
    confirmPassword: z.string().min(1, '请再次输入密码'),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: '两次输入的密码不一致',
    path: ['confirmPassword'],
  })

export function JoinOrgPage() {
  const { slug } = useParams({ from: '/join/$slug' })
  const navigate = useNavigate()
  const { auth } = useAuthStore()
  const [tenant, setTenant] = useState<PublicTenant | null>(null)
  const [error, setError] = useState<string>()
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      fullName: '',
      username: '',
      password: '',
      confirmPassword: '',
    },
  })

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const next = await getPublicTenant(slug)
        if (!cancelled) setTenant(next)
      } catch (e) {
        if (!cancelled) {
          setError(
            e instanceof ApiClientError ? e.message : '邀请链接无效或机构不存在'
          )
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [slug])

  async function onSubmit(data: z.infer<typeof formSchema>) {
    setSubmitting(true)
    try {
      const result = await registerMember({
        slug,
        fullName: data.fullName.trim(),
        username: data.username.trim(),
        password: data.password,
      })
      auth.setSession(result.accessToken, result.user)
      toast.success(`已加入 ${result.user.tenantName || tenant?.name || '机构'}`)
      const dest = await resolvePostLoginTarget(undefined, result.user.roleCodes)
      if (dest.params?.agentId) {
        navigate({
          to: '/admin/chat/$agentId',
          params: { agentId: dest.params.agentId },
          replace: true,
        })
      } else {
        navigate({ to: dest.to as '/settings/account', replace: true })
      }
    } catch (e) {
      toast.error(getApiErrorMessage(e, '注册失败，请稍后重试'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-svh bg-[#f4efe4] text-[#1c2a22] antialiased [--font-serif:'Noto_Serif_SC',serif]">
      <header className='relative mx-auto flex h-16 max-w-5xl items-center justify-between px-5'>
        <Link to='/' className='flex items-center gap-2.5'>
          <span className='flex size-9 items-center justify-center rounded-xl bg-[#1f6b4a] text-[#f4efe4]'>
            <GraduationCap className='size-5' />
          </span>
          <span className='font-serif text-[15px] font-semibold tracking-wide'>
            启明顾问
          </span>
        </Link>
        <Link
          to='/sign-in'
          className='text-sm text-[#1c2a22]/70 underline-offset-4 hover:underline'
        >
          已有账号？登录
        </Link>
      </header>

      <main className='relative mx-auto max-w-lg px-5 py-12'>
        {loading ? (
          <p className='text-sm text-[#1c2a22]/60'>正在打开邀请…</p>
        ) : error || !tenant ? (
          <div className='space-y-3'>
            <h1 className='font-serif text-2xl font-semibold'>邀请链接无效</h1>
            <p className='text-sm text-[#1c2a22]/68'>
              {error || '请向机构管理员重新索取邀请链接。'}
            </p>
            <Button asChild variant='outline'>
              <Link to='/'>返回首页</Link>
            </Button>
          </div>
        ) : (
          <>
            <p className='text-xs font-medium tracking-[0.18em] text-[#1f6b4a] uppercase'>
              加入机构
            </p>
            <h1 className='mt-3 font-serif text-3xl font-semibold tracking-tight'>
              {tenant.name}
            </h1>
            <p className='mt-3 text-sm leading-7 text-[#1c2a22]/68'>
              注册后即可使用该机构已发布的课程顾问。对话次数计入机构套餐。
            </p>
            <div className='mt-8 rounded-2xl border border-[#1c2a22]/8 bg-[#fbf7ef] p-6 shadow-[0_24px_60px_-28px_rgba(28,42,34,0.35)]'>
              <Form {...form}>
                <form
                  onSubmit={form.handleSubmit(onSubmit)}
                  className='grid gap-4'
                >
                  <FormField
                    control={form.control}
                    name='fullName'
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>姓名</FormLabel>
                        <FormControl>
                          <Input placeholder='如：李老师' {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name='username'
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>用户名</FormLabel>
                        <FormControl>
                          <Input placeholder='登录用，至少 2 位' {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name='password'
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>密码</FormLabel>
                        <FormControl>
                          <PasswordInput placeholder='至少 6 位' {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name='confirmPassword'
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>确认密码</FormLabel>
                        <FormControl>
                          <PasswordInput placeholder='再输入一次' {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <Button type='submit' disabled={submitting} className='mt-2'>
                    {submitting ? (
                      <>
                        <Loader2 className='mr-2 size-4 animate-spin' />
                        加入中…
                      </>
                    ) : (
                      '注册并进入顾问'
                    )}
                  </Button>
                </form>
              </Form>
            </div>
          </>
        )}
      </main>
    </div>
  )
}
