import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react'
import i18n, {
  appLocaleToHtmlLang,
  LOCALE_COOKIE_NAME,
  type AppLocale,
} from '@/i18n/i18n'
import { getCookie, removeCookie, setCookie } from '@/lib/cookies'

const DEFAULT_LOCALE: AppLocale = 'en'
const LOCALE_COOKIE_MAX_AGE = 60 * 60 * 24 * 365

function parseLocale(raw: string | undefined): AppLocale {
  return raw === 'zh' || raw === 'en' ? raw : DEFAULT_LOCALE
}

type LocaleContextValue = {
  defaultLocale: AppLocale
  locale: AppLocale
  setLocale: (locale: AppLocale) => void
  resetLocale: () => void
}

const LocaleContext = createContext<LocaleContextValue | null>(null)

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<AppLocale>(() =>
    parseLocale(getCookie(LOCALE_COOKIE_NAME))
  )

  useEffect(() => {
    void i18n.changeLanguage(locale)
    document.documentElement.lang = appLocaleToHtmlLang(locale)
  }, [locale])

  const setLocale = (next: AppLocale) => {
    setCookie(LOCALE_COOKIE_NAME, next, LOCALE_COOKIE_MAX_AGE)
    setLocaleState(next)
  }

  const resetLocale = () => {
    removeCookie(LOCALE_COOKIE_NAME)
    setLocaleState(DEFAULT_LOCALE)
  }

  return (
    <LocaleContext
      value={{
        defaultLocale: DEFAULT_LOCALE,
        locale,
        resetLocale,
        setLocale,
      }}
    >
      {children}
    </LocaleContext>
  )
}

function fallbackLocaleValue(): LocaleContextValue {
  const locale = parseLocale(getCookie(LOCALE_COOKIE_NAME))
  return {
    defaultLocale: DEFAULT_LOCALE,
    locale,
    setLocale: (next) => {
      setCookie(LOCALE_COOKIE_NAME, next, LOCALE_COOKIE_MAX_AGE)
      void i18n.changeLanguage(next)
      document.documentElement.lang = appLocaleToHtmlLang(next)
    },
    resetLocale: () => {
      removeCookie(LOCALE_COOKIE_NAME)
      void i18n.changeLanguage(DEFAULT_LOCALE)
      document.documentElement.lang = appLocaleToHtmlLang(DEFAULT_LOCALE)
    },
  }
}

// eslint-disable-next-line react-refresh/only-export-components
export const useLocale = () => {
  const ctx = useContext(LocaleContext)
  return ctx ?? fallbackLocaleValue()
}
