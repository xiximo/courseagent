import { useEffect, useState } from 'react'
import { z } from 'zod'
import { useForm } from 'react-hook-form'
import { CaretSortIcon, CheckIcon } from '@radix-ui/react-icons'
import { zodResolver } from '@hookform/resolvers/zod'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { ApiClientError, getApiErrorMessage } from '@/lib/api/client'
import { changePassword } from '@/lib/api/auth'
import { cn } from '@/lib/utils'
import { useLocale } from '@/context/locale-provider'
import { SUPPORTED_LOCALES, type AppLocale } from '@/i18n/i18n'
import { PasswordInput } from '@/components/password-input'
import { Button } from '@/components/ui/button'
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command'
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import { Separator } from '@/components/ui/separator'

function createPasswordFormSchema(t: (key: string) => string) {
  return z
    .object({
      currentPassword: z
        .string()
        .min(1, t('settings.account.validation.currentPasswordRequired')),
      newPassword: z
        .string()
        .min(1, t('settings.account.validation.newPasswordRequired'))
        .min(6, t('settings.account.validation.passwordMin')),
      confirmPassword: z
        .string()
        .min(1, t('settings.account.validation.confirmPasswordRequired')),
    })
    .refine((data) => data.newPassword === data.confirmPassword, {
      message: t('settings.account.validation.passwordMismatch'),
      path: ['confirmPassword'],
    })
    .refine((data) => data.newPassword !== data.currentPassword, {
      message: t('settings.account.validation.passwordSame'),
      path: ['newPassword'],
    })
}

function createLanguageFormSchema(t: (key: string) => string) {
  return z.object({
    language: z.enum(SUPPORTED_LOCALES, {
      error: t('settings.account.validation.languageRequired'),
    }),
  })
}

type PasswordFormValues = z.infer<ReturnType<typeof createPasswordFormSchema>>
type LanguageFormValues = z.infer<ReturnType<typeof createLanguageFormSchema>>

export function AccountForm() {
  const { t } = useTranslation()
  const { locale, setLocale } = useLocale()
  const [submitting, setSubmitting] = useState(false)

  const passwordSchema = createPasswordFormSchema(t)
  const languageSchema = createLanguageFormSchema(t)

  const passwordForm = useForm<PasswordFormValues>({
    resolver: zodResolver(passwordSchema),
    defaultValues: {
      currentPassword: '',
      newPassword: '',
      confirmPassword: '',
    },
  })

  const languageForm = useForm<LanguageFormValues>({
    resolver: zodResolver(languageSchema),
    defaultValues: {
      language: locale,
    },
  })

  useEffect(() => {
    languageForm.setValue('language', locale)
  }, [locale, languageForm])

  async function onChangePassword(data: PasswordFormValues) {
    setSubmitting(true)
    try {
      await changePassword({
        currentPassword: data.currentPassword,
        newPassword: data.newPassword,
      })
      toast.success(t('settings.account.passwordChanged'))
      passwordForm.reset({
        currentPassword: '',
        newPassword: '',
        confirmPassword: '',
      })
    } catch (e) {
      toast.error(
        getApiErrorMessage(e, t('settings.account.passwordChangeFailed'))
      )
      if (e instanceof ApiClientError && e.code === 'INVALID_PASSWORD') {
        passwordForm.setError('currentPassword', { message: e.message })
      }
    } finally {
      setSubmitting(false)
    }
  }

  function onSaveLanguage(data: LanguageFormValues) {
    if (data.language !== locale) {
      setLocale(data.language as AppLocale)
      toast.success(t(`locale.${data.language}`))
    } else {
      toast.success(t('settings.account.languageUnchanged'))
    }
  }

  return (
    <div className='space-y-10'>
      <div className='space-y-4'>
        <div>
          <h3 className='text-base font-medium'>
            {t('settings.account.passwordSection')}
          </h3>
          <p className='text-muted-foreground text-sm'>
            {t('settings.account.passwordSectionHint')}
          </p>
        </div>
        <Form {...passwordForm}>
          <form
            onSubmit={passwordForm.handleSubmit(onChangePassword)}
            className='max-w-md space-y-6'
          >
            <FormField
              control={passwordForm.control}
              name='currentPassword'
              render={({ field }) => (
                <FormItem>
                  <FormLabel>
                    {t('settings.account.currentPassword')}
                  </FormLabel>
                  <FormControl>
                    <PasswordInput
                      placeholder={t(
                        'settings.account.currentPasswordPlaceholder'
                      )}
                      autoComplete='current-password'
                      disabled={submitting}
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={passwordForm.control}
              name='newPassword'
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('settings.account.newPassword')}</FormLabel>
                  <FormControl>
                    <PasswordInput
                      placeholder={t(
                        'settings.account.newPasswordPlaceholder'
                      )}
                      autoComplete='new-password'
                      disabled={submitting}
                      {...field}
                    />
                  </FormControl>
                  <FormDescription>
                    {t('settings.account.newPasswordHint')}
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={passwordForm.control}
              name='confirmPassword'
              render={({ field }) => (
                <FormItem>
                  <FormLabel>
                    {t('settings.account.confirmPassword')}
                  </FormLabel>
                  <FormControl>
                    <PasswordInput
                      placeholder={t(
                        'settings.account.confirmPasswordPlaceholder'
                      )}
                      autoComplete='new-password'
                      disabled={submitting}
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <Button type='submit' disabled={submitting}>
              {submitting
                ? t('settings.account.changingPassword')
                : t('settings.account.changePassword')}
            </Button>
          </form>
        </Form>
      </div>

      <Separator />

      <div className='space-y-4'>
        <div>
          <h3 className='text-base font-medium'>
            {t('settings.account.languageSection')}
          </h3>
          <p className='text-muted-foreground text-sm'>
            {t('settings.account.languageHint')}
          </p>
        </div>
        <Form {...languageForm}>
          <form
            onSubmit={languageForm.handleSubmit(onSaveLanguage)}
            className='max-w-md space-y-6'
          >
            <FormField
              control={languageForm.control}
              name='language'
              render={({ field }) => (
                <FormItem className='flex flex-col'>
                  <FormLabel>{t('settings.account.language')}</FormLabel>
                  <Popover>
                    <PopoverTrigger asChild>
                      <FormControl>
                        <Button
                          variant='outline'
                          role='combobox'
                          className={cn(
                            'w-50 justify-between',
                            !field.value && 'text-muted-foreground'
                          )}
                        >
                          {field.value
                            ? t(`locale.${field.value}`)
                            : t('settings.account.selectLanguage')}
                          <CaretSortIcon className='ms-2 h-4 w-4 shrink-0 opacity-50' />
                        </Button>
                      </FormControl>
                    </PopoverTrigger>
                    <PopoverContent className='w-50 p-0'>
                      <Command>
                        <CommandInput
                          placeholder={t('settings.account.searchLanguage')}
                        />
                        <CommandEmpty>
                          {t('settings.account.noLanguage')}
                        </CommandEmpty>
                        <CommandGroup>
                          <CommandList>
                            {SUPPORTED_LOCALES.map((lang) => (
                              <CommandItem
                                value={t(`locale.${lang}`)}
                                key={lang}
                                onSelect={() => {
                                  languageForm.setValue('language', lang)
                                }}
                              >
                                <CheckIcon
                                  className={cn(
                                    'size-4',
                                    lang === field.value
                                      ? 'opacity-100'
                                      : 'opacity-0'
                                  )}
                                />
                                {t(`locale.${lang}`)}
                              </CommandItem>
                            ))}
                          </CommandList>
                        </CommandGroup>
                      </Command>
                    </PopoverContent>
                  </Popover>
                  <FormMessage />
                </FormItem>
              )}
            />
            <Button type='submit'>{t('settings.account.saveLanguage')}</Button>
          </form>
        </Form>
      </div>
    </div>
  )
}
