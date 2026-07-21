export type ThemeMode = 'light' | 'dark'

export const THEME_STORAGE_KEY = 'pcb-cdso:theme:v1'

export function initialTheme(): ThemeMode {
  return localStorage.getItem(THEME_STORAGE_KEY) === 'dark' ? 'dark' : 'light'
}

export function applyTheme(mode: ThemeMode): void {
  document.documentElement.dataset.theme = mode
  localStorage.setItem(THEME_STORAGE_KEY, mode)
}
