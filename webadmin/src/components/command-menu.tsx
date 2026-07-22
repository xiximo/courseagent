import React from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from '@tanstack/react-router'
import {
  ArrowRight,
  ChevronRight,
  Languages,
  Laptop,
  Moon,
  Palette,
  Sun,
} from 'lucide-react'
import { useLocale } from '@/context/locale-provider'
import { useSearch } from '@/context/search-provider'
import { useTheme } from '@/context/theme-provider'
import type { AppLocale } from '@/i18n/i18n'
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from '@/components/ui/command'
import { useFilteredSidebarData } from './layout/use-filtered-sidebar-data'
import { ScrollArea } from './ui/scroll-area'

export function CommandMenu() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { setTheme, setColorTheme, availableColorThemes } = useTheme()
  const { locale, setLocale } = useLocale()
  const { open, setOpen } = useSearch()
  const filteredSidebar = useFilteredSidebarData()

  const runCommand = React.useCallback(
    (command: () => unknown) => {
      setOpen(false)
      command()
    },
    [setOpen]
  )

  return (
    <CommandDialog modal open={open} onOpenChange={setOpen}>
      <CommandInput placeholder={t('command.placeholder')} />
      <CommandList>
        <ScrollArea type='hover' className='h-72 pe-1'>
          <CommandEmpty>{t('command.empty')}</CommandEmpty>
          {filteredSidebar.navGroups.map((group) => (
            <CommandGroup key={group.title} heading={t(group.title)}>
              {group.items.map((navItem, i) => {
                if (navItem.url)
                  return (
                    <CommandItem
                      key={`${String(navItem.url)}-${i}`}
                      value={`${t(navItem.title)}-${String(navItem.url)}`}
                      onSelect={() => {
                        runCommand(() => navigate({ to: navItem.url }))
                      }}
                    >
                      <div className='flex size-4 items-center justify-center'>
                        <ArrowRight className='size-2 text-muted-foreground/80' />
                      </div>
                      {t(navItem.title)}
                    </CommandItem>
                  )

                return navItem.items?.map((subItem, j) => (
                  <CommandItem
                    key={`${navItem.title}-${String(subItem.url)}-${j}`}
                    value={`${t(navItem.title)}-${t(subItem.title)}-${String(subItem.url)}`}
                    onSelect={() => {
                      runCommand(() => navigate({ to: subItem.url }))
                    }}
                  >
                    <div className='flex size-4 items-center justify-center'>
                      <ArrowRight className='size-2 text-muted-foreground/80' />
                    </div>
                    {t(navItem.title)} <ChevronRight /> {t(subItem.title)}
                  </CommandItem>
                ))
              })}
            </CommandGroup>
          ))}
          <CommandSeparator />
          <CommandGroup heading={t('command.groupTheme')}>
            <CommandItem onSelect={() => runCommand(() => setTheme('light'))}>
              <Sun /> <span>{t('appearance.light')}</span>
            </CommandItem>
            <CommandItem onSelect={() => runCommand(() => setTheme('dark'))}>
              <Moon className='scale-90' />
              <span>{t('appearance.dark')}</span>
            </CommandItem>
            <CommandItem onSelect={() => runCommand(() => setTheme('system'))}>
              <Laptop />
              <span>{t('appearance.system')}</span>
            </CommandItem>
          </CommandGroup>
          {availableColorThemes.length > 1 ? (
            <CommandGroup heading={t('command.groupColorPalette')}>
              {availableColorThemes.map((palette) => (
                <CommandItem
                  key={palette.id}
                  onSelect={() =>
                    runCommand(() => setColorTheme(palette.id))
                  }
                >
                  <Palette className='scale-90' />
                  <span>{palette.name}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          ) : null}
          <CommandGroup heading={t('command.groupLanguage')}>
            {(
              [
                ['en', 'locale.en'],
                ['zh', 'locale.zh'],
              ] as const satisfies [AppLocale, string][]
            ).map(([code, labelKey]) => (
              <CommandItem
                key={code}
                onSelect={() =>
                  runCommand(() => {
                    setLocale(code)
                  })
                }
              >
                <Languages className='scale-90' />
                <span>{t(labelKey)}</span>
                {locale === code ? (
                  <span className='ms-auto text-xs text-muted-foreground'>
                    ✓
                  </span>
                ) : null}
              </CommandItem>
            ))}
          </CommandGroup>
        </ScrollArea>
      </CommandList>
    </CommandDialog>
  )
}
