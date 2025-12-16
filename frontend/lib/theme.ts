export type ColorScheme = 'light' | 'dark' | 'system';

export function resolvePreferredScheme(): 'light' | 'dark' {
  if (typeof window === 'undefined') return 'light';
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export function applyColorScheme(scheme: ColorScheme) {
  if (typeof document === 'undefined') return;
  const applied = scheme === 'system' ? resolvePreferredScheme() : scheme;
  document.documentElement.classList.toggle('dark', applied === 'dark');
  document.documentElement.dataset.colorScheme = scheme;
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem('dotmac-color-scheme', scheme);
  }
}

export function getSavedColorScheme(): ColorScheme | null {
  if (typeof localStorage === 'undefined') return null;
  const saved = localStorage.getItem('dotmac-color-scheme');
  return saved === 'light' || saved === 'dark' || saved === 'system' ? saved : null;
}
