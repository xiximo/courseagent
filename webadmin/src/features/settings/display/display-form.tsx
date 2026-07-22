import { z } from 'zod'
import { useMemo } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useTranslation } from 'react-i18next'
import { showSubmittedData } from '@/lib/show-submitted-data'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'

const DISPLAY_ITEM_IDS = [
  'recents',
  'home',
  'applications',
  'desktop',
  'downloads',
  'documents',
] as const

const DISPLAY_ITEMS: { id: (typeof DISPLAY_ITEM_IDS)[number]; labelKey: string }[] = [
  { id: 'recents', labelKey: 'settings.display.itemRecents' },
  { id: 'home', labelKey: 'settings.display.itemHome' },
  { id: 'applications', labelKey: 'settings.display.itemApplications' },
  { id: 'desktop', labelKey: 'settings.display.itemDesktop' },
  { id: 'downloads', labelKey: 'settings.display.itemDownloads' },
  { id: 'documents', labelKey: 'settings.display.itemDocuments' },
]

function createDisplayFormSchema(t: (key: string) => string) {
  return z.object({
    items: z.array(z.string()).refine((value) => value.some((item) => item), {
      message: t('settings.display.validation.itemsMin'),
    }),
  })
}

type DisplayFormValues = z.infer<ReturnType<typeof createDisplayFormSchema>>

const defaultValues: Partial<DisplayFormValues> = {
  items: ['recents', 'home'],
}

export function DisplayForm() {
  const { t } = useTranslation()
  const displayFormSchema = createDisplayFormSchema(t)

  const items = useMemo(
    () =>
      DISPLAY_ITEMS.map((item) => ({
        id: item.id,
        label: t(item.labelKey),
      })),
    [t]
  )

  const form = useForm<DisplayFormValues>({
    resolver: zodResolver(displayFormSchema),
    defaultValues,
  })

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit((data) => showSubmittedData(data))}
        className='space-y-8'
      >
        <FormField
          control={form.control}
          name='items'
          render={() => (
            <FormItem>
              <div className='mb-4'>
                <FormLabel className='text-base'>{t('settings.display.sidebar')}</FormLabel>
                <FormDescription>{t('settings.display.sidebarHint')}</FormDescription>
              </div>
              {items.map((item) => (
                <FormField
                  key={item.id}
                  control={form.control}
                  name='items'
                  render={({ field }) => (
                    <FormItem key={item.id} className='flex flex-row items-start'>
                      <FormControl>
                        <Checkbox
                          checked={field.value?.includes(item.id)}
                          onCheckedChange={(checked) => {
                            return checked
                              ? field.onChange([...(field.value ?? []), item.id])
                              : field.onChange(
                                  field.value?.filter((value) => value !== item.id)
                                )
                          }}
                        />
                      </FormControl>
                      <FormLabel className='font-normal'>{item.label}</FormLabel>
                    </FormItem>
                  )}
                />
              ))}
              <FormMessage />
            </FormItem>
          )}
        />
        <Button type='submit'>{t('settings.display.submit')}</Button>
      </form>
    </Form>
  )
}
