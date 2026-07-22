import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import { getCookie } from '@/lib/cookies'
import en from './locales/en.json'
import zh from './locales/zh.json'

export const LOCALE_COOKIE_NAME = 'vite-ui-locale'
export const SUPPORTED_LOCALES = ['en', 'zh'] as const
export type AppLocale = (typeof SUPPORTED_LOCALES)[number]

const DEFAULT_LOCALE: AppLocale = 'en'

function readInitialLocale(): AppLocale {
  const fromCookie = getCookie(LOCALE_COOKIE_NAME)
  if (fromCookie === 'zh' || fromCookie === 'en') return fromCookie
  return DEFAULT_LOCALE
}

void i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    zh: { translation: zh },
  },
  lng: readInitialLocale(),
  fallbackLng: DEFAULT_LOCALE,
  interpolation: { escapeValue: false },
})

export function appLocaleToHtmlLang(locale: AppLocale): string {
  return locale === 'zh' ? 'zh-CN' : 'en'
}

export default i18n
