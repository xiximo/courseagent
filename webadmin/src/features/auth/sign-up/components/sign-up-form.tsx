import { useState } from 'react'
import { z } from 'zod'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useNavigate } from '@tanstack/react-router'
import { Loader2, Building2 } from 'lucide-react'
import { toast } from 'sonner'
import { registerOrganization } from '@/lib/api/auth'
import { getApiErrorMessage } from '@/lib/api/client'
import { useAuthStore } from '@/stores/auth-store'
import { cn } from '@/lib/utils'
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

const formSchema = z
  .object({
    orgName: z.string().trim().min(2, '请填写机构名称'),
    contactName: z.string().trim().min(2, '请填写联系人姓名'),
    username: z.string().trim().min(2, '用户名至少 2 位'),
    password: z
      .string()
      .min(1, '请输入密码')
      .min(6, '密码至少 6 位'),
    confirmPassword: z.string().min(1, '请再次输入密码'),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: '两次输入的密码不一致',
    path: ['confirmPassword'],
  })

export function SignUpForm({
  className,
  intent,
  ...props
}: React.HTMLAttributes<HTMLFormElement> & { intent?: 'pro' }) {
  const [isLoading, setIsLoading] = useState(false)
  const navigate = useNavigate()
  const { auth } = useAuthStore()

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      orgName: '',
      contactName: '',
      username: '',
      password: '',
      confirmPassword: '',
    },
  })

  async function onSubmit(data: z.infer<typeof formSchema>) {
    setIsLoading(true)
    try {
      const result = await registerOrganization({
        orgName: data.orgName.trim(),
        contactName: data.contactName.trim(),
        username: data.username.trim(),
        password: data.password,
      })
      auth.setSession(result.accessToken, result.user)
      if (intent === 'pro') {
        toast.success('机构已开通，请完成专业版支付')
        navigate({ to: '/plans', replace: true, search: { pay: undefined } })
      } else {
        toast.success('机构空间已开通，正在进入工作台')
        navigate({ to: '/admin', replace: true })
      }
    } catch (error) {
      toast.error(getApiErrorMessage(error, '开通失败，请稍后重试'))
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit(onSubmit)}
        className={cn('grid gap-3', className)}
        {...props}
      >
        <FormField
          control={form.control}
          name='orgName'
          render={({ field }) => (
            <FormItem>
              <FormLabel>机构名称</FormLabel>
              <FormControl>
                <Input placeholder='例如：启明教育' autoComplete='organization' {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name='contactName'
          render={({ field }) => (
            <FormItem>
              <FormLabel>联系人</FormLabel>
              <FormControl>
                <Input placeholder='您的姓名' autoComplete='name' {...field} />
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
              <FormLabel>登录用户名</FormLabel>
              <FormControl>
                <Input placeholder='用于登录工作台' autoComplete='username' {...field} />
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
                <PasswordInput placeholder='至少 6 位' autoComplete='new-password' {...field} />
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
                <PasswordInput placeholder='再次输入密码' autoComplete='new-password' {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <Button className='mt-2 h-11 bg-[#1f6b4a] text-[#f4efe4] hover:bg-[#18583c]' disabled={isLoading}>
          {isLoading ? <Loader2 className='animate-spin' /> : <Building2 />}
          {intent === 'pro' ? '开通并去支付' : '开通并进入工作台'}
        </Button>
      </form>
    </Form>
  )
}
