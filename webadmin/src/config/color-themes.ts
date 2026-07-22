/**
 * 配色主题注册表（多租户时可通过 ThemeProvider 的 `allowedColorThemes` 收窄可选列表）。
 * 新增主题：在此处添加 meta，并在 `src/styles/theme-palettes.css` 增加
 * `html.light[data-color-theme="…"]` / `html.dark[data-color-theme="…"]` 变量块。
 * 也可将 oklch 清单放在独立 JSON 中，由构建脚本生成上述 CSS（本仓库暂未接入）。
 */
export const COLOR_THEMES = [
  {
    id: 'default',
    name: 'Slate',
    description: '项目内置默认',
  },
  {
    id: 'ember',
    name: 'Ember',
    description: '暖色主色',
  },
] as const

export type ColorThemeId = (typeof COLOR_THEMES)[number]['id']

export const DEFAULT_COLOR_THEME_ID: ColorThemeId = 'default'

export function isColorThemeId(id: string): id is ColorThemeId {
  return COLOR_THEMES.some((t) => t.id === id)
}

export type ColorThemeMeta = (typeof COLOR_THEMES)[number]

export function resolveColorThemes(
  allowed?: readonly ColorThemeId[]
): readonly ColorThemeMeta[] {
  if (!allowed?.length) return COLOR_THEMES
  const allow = new Set(allowed)
  return COLOR_THEMES.filter((t) => allow.has(t.id))
}
