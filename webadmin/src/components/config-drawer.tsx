import { useTranslation } from 'react-i18next'
import { type SVGProps } from 'react'
import { Root as Radio, Item } from '@radix-ui/react-radio-group'
import { CircleCheck, Languages, Palette, RotateCcw, Settings } from 'lucide-react'
import { IconDir } from '@/assets/custom/icon-dir'
import { IconLayoutCompact } from '@/assets/custom/icon-layout-compact'
import { IconLayoutDefault } from '@/assets/custom/icon-layout-default'
import { IconLayoutFull } from '@/assets/custom/icon-layout-full'
import { IconSidebarFloating } from '@/assets/custom/icon-sidebar-floating'
import { IconSidebarInset } from '@/assets/custom/icon-sidebar-inset'
import { IconSidebarSidebar } from '@/assets/custom/icon-sidebar-sidebar'
import { IconThemeDark } from '@/assets/custom/icon-theme-dark'
import { IconThemeLight } from '@/assets/custom/icon-theme-light'
import { IconThemeSystem } from '@/assets/custom/icon-theme-system'
import { cn } from '@/lib/utils'
import { useDirection } from '@/context/direction-provider'
import { useLocale } from '@/context/locale-provider'
import { type Collapsible, useLayout } from '@/context/layout-provider'
import { useTheme } from '@/context/theme-provider'
import { type ColorThemeId } from '@/config/color-themes'
import type { AppLocale } from '@/i18n/i18n'
import { Button } from '@/components/ui/button'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'
import { useSidebar } from './ui/sidebar'

function PaletteIcon(props: SVGProps<SVGSVGElement>) {
  return <Palette {...props} />
}

function LanguagesGlyph(props: SVGProps<SVGSVGElement>) {
  return <Languages {...props} />
}

export function ConfigDrawer() {
  const { t } = useTranslation()
  const { setOpen } = useSidebar()
  const { resetDir } = useDirection()
  const { resetLocale } = useLocale()
  const { resetTheme } = useTheme()
  const { resetLayout } = useLayout()

  const handleReset = () => {
    setOpen(true)
    resetDir()
    resetLocale()
    resetTheme()
    resetLayout()
  }

  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button
          size='icon'
          variant='ghost'
          aria-label={t('drawer.openAria')}
          className='rounded-full'
        >
          <Settings aria-hidden='true' />
        </Button>
      </SheetTrigger>
      <SheetContent className='flex flex-col'>
        <SheetHeader className='pb-0 text-start'>
          <SheetTitle>{t('drawer.title')}</SheetTitle>
          <SheetDescription>{t('drawer.description')}</SheetDescription>
        </SheetHeader>
        <div className='space-y-6 overflow-y-auto px-4'>
          <ThemeConfig />
          <ColorPaletteConfig />
          <LanguageConfig />
          <SidebarConfig />
          <LayoutConfig />
          <DirConfig />
        </div>
        <SheetFooter className='gap-2'>
          <Button
            variant='destructive'
            onClick={handleReset}
            aria-label={t('drawer.resetAllAria')}
          >
            {t('drawer.resetAll')}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}

function SectionTitle({
  title,
  showReset = false,
  onReset,
  resetAriaLabel,
  className,
}: {
  title: string
  showReset?: boolean
  onReset?: () => void
  /** Shown on the small per-section reset (RotateCcw) for accessibility and tests. */
  resetAriaLabel?: string
  className?: string
}) {
  return (
    <div
      className={cn(
        'mb-2 flex items-center gap-2 text-sm font-semibold text-muted-foreground',
        className
      )}
    >
      {title}
      {showReset && onReset && (
        <Button
          type='button'
          size='icon'
          variant='secondary'
          className='size-4 rounded-full'
          onClick={onReset}
          aria-label={resetAriaLabel}
        >
          <RotateCcw className='size-3' />
        </Button>
      )}
    </div>
  )
}

function RadioGroupItem({
  item,
  isTheme = false,
}: {
  item: {
    value: string
    label: string
    icon: (props: SVGProps<SVGSVGElement>) => React.ReactElement
  }
  isTheme?: boolean
}) {
  return (
    <Item
      value={item.value}
      className={cn('group outline-none', 'transition duration-200 ease-in')}
      aria-label={`Select ${item.label.toLowerCase()}`}
      aria-describedby={`${item.value}-description`}
    >
      <div
        className={cn(
          'relative rounded-[6px] ring-[1px] ring-border',
          'group-data-[state=checked]:shadow-2xl group-data-[state=checked]:ring-primary',
          'group-focus-visible:ring-2'
        )}
        role='img'
        aria-hidden='false'
        aria-label={`${item.label} option preview`}
      >
        <CircleCheck
          className={cn(
            'size-6 fill-primary stroke-white',
            'group-data-[state=unchecked]:hidden',
            'absolute top-0 right-0 translate-x-1/2 -translate-y-1/2'
          )}
          aria-hidden='true'
        />
        <item.icon
          className={cn(
            !isTheme &&
              'fill-primary stroke-primary group-data-[state=unchecked]:fill-muted-foreground group-data-[state=unchecked]:stroke-muted-foreground'
          )}
          aria-hidden='true'
        />
      </div>
      <div
        className='mt-1 text-xs'
        id={`${item.value}-description`}
        aria-live='polite'
      >
        {item.label}
      </div>
    </Item>
  )
}

function ThemeConfig() {
  const { t } = useTranslation()
  const { defaultTheme, theme, setTheme } = useTheme()
  return (
    <div>
      <SectionTitle
        title={t('drawer.sectionTheme')}
        showReset={theme !== defaultTheme}
        onReset={() => setTheme(defaultTheme)}
        resetAriaLabel={t('drawer.resetThemeAria')}
      />
      <Radio
        value={theme}
        onValueChange={setTheme}
        className='grid w-full max-w-md grid-cols-3 gap-4'
        aria-label={t('drawer.themeModeAria')}
        aria-describedby='theme-description'
      >
        {[
          {
            value: 'system',
            label: t('appearance.system'),
            icon: IconThemeSystem,
          },
          {
            value: 'light',
            label: t('appearance.light'),
            icon: IconThemeLight,
          },
          {
            value: 'dark',
            label: t('appearance.dark'),
            icon: IconThemeDark,
          },
        ].map((item) => (
          <RadioGroupItem key={item.value} item={item} isTheme />
        ))}
      </Radio>
      <div id='theme-description' className='sr-only'>
        {t('drawer.themeDescription')}
      </div>
    </div>
  )
}

function ColorPaletteConfig() {
  const { t } = useTranslation()
  const {
    availableColorThemes,
    colorTheme,
    defaultColorTheme,
    resetColorTheme,
    setColorTheme,
  } = useTheme()

  if (availableColorThemes.length <= 1) return null

  return (
    <div>
      <SectionTitle
        title={t('drawer.sectionColorPalette')}
        showReset={colorTheme !== defaultColorTheme}
        onReset={resetColorTheme}
        resetAriaLabel={t('drawer.resetColorAria')}
      />
      <Radio
        value={colorTheme}
        onValueChange={(v) => setColorTheme(v as ColorThemeId)}
        className='grid w-full max-w-md grid-cols-2 gap-4'
        aria-label={t('drawer.colorPaletteAria')}
        aria-describedby='color-palette-description'
      >
        {availableColorThemes.map((item) => (
          <RadioGroupItem
            key={item.id}
            item={{
              value: item.id,
              label: item.name,
              icon: PaletteIcon,
            }}
          />
        ))}
      </Radio>
      <div id='color-palette-description' className='sr-only'>
        {t('drawer.colorPaletteDescription')}
      </div>
    </div>
  )
}

function LanguageConfig() {
  const { t } = useTranslation()
  const { defaultLocale, locale, setLocale, resetLocale } = useLocale()

  return (
    <div>
      <SectionTitle
        title={t('drawer.sectionLanguage')}
        showReset={locale !== defaultLocale}
        onReset={resetLocale}
        resetAriaLabel={t('drawer.resetLanguageAria')}
      />
      <Radio
        value={locale}
        onValueChange={(v) => setLocale(v as AppLocale)}
        className='grid w-full max-w-md grid-cols-2 gap-4'
        aria-label={t('drawer.languageAria')}
        aria-describedby='language-description'
      >
        {[
          { value: 'en' as const, label: t('locale.en'), icon: LanguagesGlyph },
          { value: 'zh' as const, label: t('locale.zh'), icon: LanguagesGlyph },
        ].map((item) => (
          <RadioGroupItem key={item.value} item={item} />
        ))}
      </Radio>
      <div id='language-description' className='sr-only'>
        {t('drawer.languageDescription')}
      </div>
    </div>
  )
}

function SidebarConfig() {
  const { t } = useTranslation()
  const { defaultVariant, variant, setVariant } = useLayout()
  return (
    <div className='max-md:hidden'>
      <SectionTitle
        title={t('drawer.sectionSidebar')}
        showReset={defaultVariant !== variant}
        onReset={() => setVariant(defaultVariant)}
        resetAriaLabel={t('drawer.resetSidebarAria')}
      />
      <Radio
        value={variant}
        onValueChange={setVariant}
        className='grid w-full max-w-md grid-cols-3 gap-4'
        aria-label={t('drawer.sidebarStyleAria')}
        aria-describedby='sidebar-description'
      >
        {[
          {
            value: 'inset',
            label: t('drawer.sidebarInset'),
            icon: IconSidebarInset,
          },
          {
            value: 'floating',
            label: t('drawer.sidebarFloating'),
            icon: IconSidebarFloating,
          },
          {
            value: 'sidebar',
            label: t('drawer.sidebarStandard'),
            icon: IconSidebarSidebar,
          },
        ].map((item) => (
          <RadioGroupItem key={item.value} item={item} />
        ))}
      </Radio>
      <div id='sidebar-description' className='sr-only'>
        {t('drawer.sidebarDescription')}
      </div>
    </div>
  )
}

function LayoutConfig() {
  const { t } = useTranslation()
  const { open, setOpen } = useSidebar()
  const { defaultCollapsible, collapsible, setCollapsible } = useLayout()

  const radioState = open ? 'default' : collapsible

  return (
    <div className='max-md:hidden'>
      <SectionTitle
        title={t('drawer.sectionLayout')}
        showReset={radioState !== 'default'}
        onReset={() => {
          setOpen(true)
          setCollapsible(defaultCollapsible)
        }}
        resetAriaLabel={t('drawer.resetLayoutAria')}
      />
      <Radio
        value={radioState}
        onValueChange={(v) => {
          if (v === 'default') {
            setOpen(true)
            return
          }
          setOpen(false)
          setCollapsible(v as Collapsible)
        }}
        className='grid w-full max-w-md grid-cols-3 gap-4'
        aria-label={t('drawer.layoutStyleAria')}
        aria-describedby='layout-description'
      >
        {[
          {
            value: 'default',
            label: t('drawer.layoutDefault'),
            icon: IconLayoutDefault,
          },
          {
            value: 'icon',
            label: t('drawer.layoutCompact'),
            icon: IconLayoutCompact,
          },
          {
            value: 'offcanvas',
            label: t('drawer.layoutFull'),
            icon: IconLayoutFull,
          },
        ].map((item) => (
          <RadioGroupItem key={item.value} item={item} />
        ))}
      </Radio>
      <div id='layout-description' className='sr-only'>
        {t('drawer.layoutDescription')}
      </div>
    </div>
  )
}

function DirConfig() {
  const { t } = useTranslation()
  const { defaultDir, dir, setDir } = useDirection()
  return (
    <div>
      <SectionTitle
        title={t('drawer.sectionDirection')}
        showReset={defaultDir !== dir}
        onReset={() => setDir(defaultDir)}
        resetAriaLabel={t('drawer.resetDirectionAria')}
      />
      <Radio
        value={dir}
        onValueChange={setDir}
        className='grid w-full max-w-md grid-cols-3 gap-4'
        aria-label={t('drawer.directionAria')}
        aria-describedby='direction-description'
      >
        {[
          {
            value: 'ltr',
            label: t('drawer.dirLtr'),
            icon: (props: SVGProps<SVGSVGElement>) => (
              <IconDir dir='ltr' {...props} />
            ),
          },
          {
            value: 'rtl',
            label: t('drawer.dirRtl'),
            icon: (props: SVGProps<SVGSVGElement>) => (
              <IconDir dir='rtl' {...props} />
            ),
          },
        ].map((item) => (
          <RadioGroupItem key={item.value} item={item} />
        ))}
      </Radio>
      <div id='direction-description' className='sr-only'>
        {t('drawer.directionDescription')}
      </div>
    </div>
  )
}
