import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import {
  DEFAULT_COLOR_THEME_ID,
  type ColorThemeId,
  type ColorThemeMeta,
  isColorThemeId,
  resolveColorThemes,
} from '@/config/color-themes'
import { getCookie, removeCookie, setCookie } from '@/lib/cookies'

type Theme = 'dark' | 'light' | 'system'
type ResolvedTheme = Exclude<Theme, 'system'>

const DEFAULT_THEME: Theme = 'system'
const THEME_COOKIE_NAME = 'vite-ui-theme'
const COLOR_THEME_COOKIE_NAME = 'vite-ui-color-theme'
const THEME_COOKIE_MAX_AGE = 60 * 60 * 24 * 365 // 1 year

type ThemeProviderProps = {
  children: ReactNode
  defaultTheme?: Theme
  /** 配色主题 id，须存在于 `allowedColorThemes` 或注册表 */
  defaultColorTheme?: ColorThemeId
  /** 多租户下仅展示/允许这些配色（不传则全部） */
  allowedColorThemes?: ColorThemeId[]
  storageKey?: string
  colorThemeStorageKey?: string
}

type ThemeProviderState = {
  defaultTheme: Theme
  resolvedTheme: ResolvedTheme
  theme: Theme
  setTheme: (theme: Theme) => void
  resetTheme: () => void
  colorTheme: ColorThemeId
  setColorTheme: (id: ColorThemeId) => void
  resetColorTheme: () => void
  defaultColorTheme: ColorThemeId
  availableColorThemes: ColorThemeMeta[]
}

const initialState: ThemeProviderState = {
  defaultTheme: DEFAULT_THEME,
  resolvedTheme: 'light',
  theme: DEFAULT_THEME,
  setTheme: () => null,
  resetTheme: () => null,
  colorTheme: DEFAULT_COLOR_THEME_ID,
  setColorTheme: () => null,
  resetColorTheme: () => null,
  defaultColorTheme: DEFAULT_COLOR_THEME_ID,
  availableColorThemes: [],
}

const ThemeContext = createContext<ThemeProviderState>(initialState)

function resolveDefaultColorId(
  allowed: readonly ColorThemeMeta[],
  preferred?: ColorThemeId
): ColorThemeId {
  const ids = allowed.map((t) => t.id)
  const p = preferred ?? DEFAULT_COLOR_THEME_ID
  if (ids.includes(p)) return p
  return (ids[0] as ColorThemeId | undefined) ?? DEFAULT_COLOR_THEME_ID
}

export function ThemeProvider({
  children,
  defaultTheme = DEFAULT_THEME,
  defaultColorTheme: defaultColorThemeProp,
  allowedColorThemes,
  storageKey = THEME_COOKIE_NAME,
  colorThemeStorageKey = COLOR_THEME_COOKIE_NAME,
  ...props
}: ThemeProviderProps) {
  const availableColorThemes = useMemo(
    () => [...resolveColorThemes(allowedColorThemes)],
    [allowedColorThemes]
  )

  const defaultColorThemeResolved = useMemo(
    () => resolveDefaultColorId(availableColorThemes, defaultColorThemeProp),
    [availableColorThemes, defaultColorThemeProp]
  )

  const [theme, _setTheme] = useState<Theme>(
    () => (getCookie(storageKey) as Theme) || defaultTheme
  )

  const [colorTheme, _setColorTheme] = useState<ColorThemeId>(() => {
    const ids = new Set(availableColorThemes.map((t) => t.id))
    const raw = getCookie(colorThemeStorageKey)
    if (raw && isColorThemeId(raw) && ids.has(raw)) return raw
    return defaultColorThemeResolved
  })

  const resolvedTheme = useMemo((): ResolvedTheme => {
    if (theme === 'system') {
      return window.matchMedia('(prefers-color-scheme: dark)').matches
        ? 'dark'
        : 'light'
    }
    return theme as ResolvedTheme
  }, [theme])

  useEffect(() => {
    document.documentElement.setAttribute('data-color-theme', colorTheme)
  }, [colorTheme])

  useEffect(() => {
    const root = window.document.documentElement
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')

    const applyTheme = (currentResolvedTheme: ResolvedTheme) => {
      root.classList.remove('light', 'dark')
      root.classList.add(currentResolvedTheme)
    }

    const handleChange = () => {
      if (theme === 'system') {
        const systemTheme = mediaQuery.matches ? 'dark' : 'light'
        applyTheme(systemTheme)
      }
    }

    applyTheme(resolvedTheme)

    mediaQuery.addEventListener('change', handleChange)

    return () => mediaQuery.removeEventListener('change', handleChange)
  }, [theme, resolvedTheme])

  const setTheme = (next: Theme) => {
    setCookie(storageKey, next, THEME_COOKIE_MAX_AGE)
    _setTheme(next)
  }

  const setColorTheme = (id: ColorThemeId) => {
    if (!availableColorThemes.some((t) => t.id === id)) return
    setCookie(colorThemeStorageKey, id, THEME_COOKIE_MAX_AGE)
    _setColorTheme(id)
  }

  const resetColorTheme = () => {
    removeCookie(colorThemeStorageKey)
    _setColorTheme(defaultColorThemeResolved)
  }

  const resetTheme = () => {
    removeCookie(storageKey)
    removeCookie(colorThemeStorageKey)
    _setTheme(DEFAULT_THEME)
    _setColorTheme(defaultColorThemeResolved)
  }

  const contextValue: ThemeProviderState = {
    availableColorThemes,
    colorTheme,
    defaultColorTheme: defaultColorThemeResolved,
    defaultTheme,
    resetColorTheme,
    resetTheme,
    resolvedTheme,
    setColorTheme,
    setTheme,
    theme,
  }

  return (
    <ThemeContext value={contextValue} {...props}>
      {children}
    </ThemeContext>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export const useTheme = () => {
  const context = useContext(ThemeContext)

  if (!context) throw new Error('useTheme must be used within a ThemeProvider')

  return context
}
