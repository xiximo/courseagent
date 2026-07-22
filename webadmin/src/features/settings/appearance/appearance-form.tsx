import { z } from 'zod'
import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { CaretSortIcon, CheckIcon, ChevronDownIcon } from '@radix-ui/react-icons'
import { zodResolver } from '@hookform/resolvers/zod'
import type { ColorThemeId } from '@/config/color-themes'
import { COLOR_THEMES, type ColorThemeMeta } from '@/config/color-themes'
import { fonts } from '@/config/fonts'
import { showSubmittedData } from '@/lib/show-submitted-data'
import { cn } from '@/lib/utils'
import { useFont } from '@/context/font-provider'
import { useLocale } from '@/context/locale-provider'
import { useTheme } from '@/context/theme-provider'
import { SUPPORTED_LOCALES, type AppLocale } from '@/i18n/i18n'
import { Button, buttonVariants } from '@/components/ui/button'
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
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'

const colorThemeIds = COLOR_THEMES.map((t) => t.id) as [
  ColorThemeId,
  ...ColorThemeId[],
]

const appearanceFormSchema = z.object({
  locale: z.enum(SUPPORTED_LOCALES),
  theme: z.enum(['light', 'dark']),
  colorTheme: z.enum(colorThemeIds),
  font: z.enum(fonts),
})

type AppearanceFormValues = z.infer<typeof appearanceFormSchema>

function formatColorThemeLabel(theme: ColorThemeMeta): string {
  return `${theme.name}${theme.description ? ` — ${theme.description}` : ''}`
}

export function AppearanceForm() {
  const { t } = useTranslation()
  const { locale, setLocale } = useLocale()
  const { font, setFont } = useFont()
  const {
    theme,
    setTheme,
    resolvedTheme,
    colorTheme,
    setColorTheme,
    availableColorThemes,
  } = useTheme()

  const appearanceMode: 'light' | 'dark' =
    theme === 'system' ? resolvedTheme : theme

  const defaultValues: Partial<AppearanceFormValues> = {
    locale,
    theme: appearanceMode,
    colorTheme,
    font,
  }

  const form = useForm<AppearanceFormValues>({
    resolver: zodResolver(appearanceFormSchema),
    defaultValues,
  })

  useEffect(() => {
    form.setValue('locale', locale)
    form.setValue('colorTheme', colorTheme)
  }, [locale, colorTheme, form])

  function onSubmit(data: AppearanceFormValues) {
    if (data.locale !== locale) setLocale(data.locale)
    if (data.font != font) setFont(data.font)
    if (data.theme !== appearanceMode) setTheme(data.theme)
    if (data.colorTheme !== colorTheme) setColorTheme(data.colorTheme)

    showSubmittedData(data)
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className='space-y-8'>
        <FormField
          control={form.control}
          name='locale'
          render={({ field }) => (
            <FormItem className='flex flex-col'>
              <FormLabel>{t('appearance.interfaceLanguage')}</FormLabel>
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
                    <CommandInput placeholder={t('settings.account.searchLanguage')} />
                    <CommandEmpty>{t('settings.account.noLanguage')}</CommandEmpty>
                    <CommandGroup>
                      <CommandList>
                        {SUPPORTED_LOCALES.map((lang) => (
                          <CommandItem
                            value={t(`locale.${lang}`)}
                            key={lang}
                            onSelect={() => {
                              form.setValue('locale', lang as AppLocale)
                            }}
                          >
                            <CheckIcon
                              className={cn(
                                'size-4',
                                lang === field.value ? 'opacity-100' : 'opacity-0'
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
              <FormDescription>{t('appearance.interfaceLanguageHint')}</FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name='colorTheme'
          render={({ field }) => {
            const selectedTheme = availableColorThemes.find(
              (theme) => theme.id === field.value
            )

            return (
              <FormItem className='flex flex-col'>
                <FormLabel>{t('appearance.colorPalette')}</FormLabel>
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
                        <span className='truncate'>
                          {selectedTheme
                            ? formatColorThemeLabel(selectedTheme)
                            : t('appearance.selectColorPalette')}
                        </span>
                        <CaretSortIcon className='ms-2 h-4 w-4 shrink-0 opacity-50' />
                      </Button>
                    </FormControl>
                  </PopoverTrigger>
                  <PopoverContent className='w-50 p-0'>
                    <Command>
                      <CommandInput placeholder={t('appearance.searchColorPalette')} />
                      <CommandEmpty>{t('appearance.noColorPalette')}</CommandEmpty>
                      <CommandGroup>
                        <CommandList>
                          {availableColorThemes.map((theme) => (
                            <CommandItem
                              value={formatColorThemeLabel(theme)}
                              key={theme.id}
                              onSelect={() => {
                                form.setValue('colorTheme', theme.id)
                              }}
                            >
                              <CheckIcon
                                className={cn(
                                  'size-4',
                                  theme.id === field.value ? 'opacity-100' : 'opacity-0'
                                )}
                              />
                              {formatColorThemeLabel(theme)}
                            </CommandItem>
                          ))}
                        </CommandList>
                      </CommandGroup>
                    </Command>
                  </PopoverContent>
                </Popover>
                <FormDescription>{t('appearance.colorPaletteHint')}</FormDescription>
                <FormMessage />
              </FormItem>
            )
          }}
        />
        <FormField
          control={form.control}
          name='font'
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('appearance.font')}</FormLabel>
              <div className='relative w-max'>
                <FormControl>
                  <select
                    className={cn(
                      buttonVariants({ variant: 'outline' }),
                      'w-50 appearance-none font-normal capitalize',
                      'dark:bg-background dark:hover:bg-background'
                    )}
                    {...field}
                  >
                    {fonts.map((font) => (
                      <option key={font} value={font}>
                        {font}
                      </option>
                    ))}
                  </select>
                </FormControl>
                <ChevronDownIcon className='absolute inset-e-3 top-2.5 h-4 w-4 opacity-50' />
              </div>
              <FormDescription className='font-manrope'>
                {t('appearance.fontHint')}
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name='theme'
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('appearance.theme')}</FormLabel>
              <FormDescription>{t('appearance.themeHint')}</FormDescription>
              <FormMessage />
              <RadioGroup
                onValueChange={field.onChange}
                defaultValue={field.value}
                className='grid max-w-md grid-cols-2 gap-8 pt-2'
              >
                <FormItem>
                  <FormLabel className='[&:has([data-state=checked])>div]:border-primary'>
                    <FormControl>
                      <RadioGroupItem value='light' className='sr-only' />
                    </FormControl>
                    <div className='items-center rounded-md border-2 border-muted p-1 hover:border-accent'>
                      <div className='space-y-2 rounded-sm bg-[#ecedef] p-2'>
                        <div className='space-y-2 rounded-md bg-white p-2 shadow-xs'>
                          <div className='h-2 w-20 rounded-lg bg-[#ecedef]' />
                          <div className='h-2 w-25 rounded-lg bg-[#ecedef]' />
                        </div>
                        <div className='flex items-center space-x-2 rounded-md bg-white p-2 shadow-xs'>
                          <div className='h-4 w-4 rounded-full bg-[#ecedef]' />
                          <div className='h-2 w-25 rounded-lg bg-[#ecedef]' />
                        </div>
                        <div className='flex items-center space-x-2 rounded-md bg-white p-2 shadow-xs'>
                          <div className='h-4 w-4 rounded-full bg-[#ecedef]' />
                          <div className='h-2 w-25 rounded-lg bg-[#ecedef]' />
                        </div>
                      </div>
                    </div>
                    <span className='block w-full p-2 text-center font-normal'>
                      {t('appearance.light')}
                    </span>
                  </FormLabel>
                </FormItem>
                <FormItem>
                  <FormLabel className='[&:has([data-state=checked])>div]:border-primary'>
                    <FormControl>
                      <RadioGroupItem value='dark' className='sr-only' />
                    </FormControl>
                    <div className='items-center rounded-md border-2 border-muted bg-popover p-1 hover:bg-accent hover:text-accent-foreground'>
                      <div className='space-y-2 rounded-sm bg-slate-950 p-2'>
                        <div className='space-y-2 rounded-md bg-slate-800 p-2 shadow-xs'>
                          <div className='h-2 w-20 rounded-lg bg-slate-400' />
                          <div className='h-2 w-25 rounded-lg bg-slate-400' />
                        </div>
                        <div className='flex items-center space-x-2 rounded-md bg-slate-800 p-2 shadow-xs'>
                          <div className='h-4 w-4 rounded-full bg-slate-400' />
                          <div className='h-2 w-25 rounded-lg bg-slate-400' />
                        </div>
                        <div className='flex items-center space-x-2 rounded-md bg-slate-800 p-2 shadow-xs'>
                          <div className='h-4 w-4 rounded-full bg-slate-400' />
                          <div className='h-2 w-25 rounded-lg bg-slate-400' />
                        </div>
                      </div>
                    </div>
                    <span className='block w-full p-2 text-center font-normal'>
                      {t('appearance.dark')}
                    </span>
                  </FormLabel>
                </FormItem>
              </RadioGroup>
            </FormItem>
          )}
        />

        <Button type='submit'>{t('appearance.submit')}</Button>
      </form>
    </Form>
  )
}
