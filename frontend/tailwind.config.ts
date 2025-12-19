import type { Config } from 'tailwindcss'

/**
 * Tailwind Configuration
 *
 * All colors use CSS variables for theme switching (light/dark).
 * See globals.css for variable definitions.
 * See lib/design-tokens.ts for semantic mappings.
 */
const config: Config = {
  darkMode: 'class',
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  /**
   * Safelist for dynamically constructed class names.
   * These classes are used in ModuleLayout.tsx and other components
   * where the color is determined at runtime.
   */
  safelist: [
    // Quick link icon colors
    { pattern: /^text-(amber|teal|sky|violet|emerald|rose|cyan|indigo|orange|blue|purple|lime|stone|slate)-\d00$/ },
    // Workflow step colors
    { pattern: /^bg-(amber|teal|sky|violet|emerald|rose|cyan|indigo|orange|blue|purple|lime|stone|slate)-500\/20$/ },
    { pattern: /^text-(amber|teal|sky|violet|emerald|rose|cyan|indigo|orange|blue|purple|lime|stone|slate)-400$/ },
  ],
  theme: {
    extend: {
      colors: {
        // Slate palette (backgrounds, borders) - CSS variables
        'slate-deep': 'var(--color-slate-deep)',
        'slate-card': 'var(--color-slate-card)',
        'slate-elevated': 'var(--color-slate-elevated)',
        'slate-border': 'var(--color-slate-border)',
        'slate-muted': 'var(--color-slate-muted)',

        // Brand colors - CSS variables
        'teal-electric': 'var(--color-teal-electric)',
        'teal-glow': 'var(--color-teal-glow)',

        // Semantic colors - CSS variables (NO hardcoded hex values)
        'coral-alert': 'var(--color-coral-alert)',
        'amber-warn': 'var(--color-amber-warn)',
        'blue-info': 'var(--color-blue-info)',
        'purple-accent': 'var(--color-purple-accent)',
        'cyan-accent': 'var(--color-cyan-accent)',
      },
      fontFamily: {
        'display': ['var(--font-plus-jakarta)', 'Plus Jakarta Sans', 'sans-serif'],
        'mono': ['var(--font-jetbrains-mono)', 'JetBrains Mono', 'monospace'],
        'body': ['var(--font-plus-jakarta)', 'Plus Jakarta Sans', 'sans-serif'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'glow': 'glow 2s ease-in-out infinite alternate',
        'slide-up': 'slideUp 0.5s ease-out forwards',
        'slide-in': 'slideIn 0.3s ease-out forwards',
        'counter': 'counter 1.5s ease-out forwards',
        'heartbeat': 'heartbeat 1.5s ease-in-out infinite',
      },
      keyframes: {
        glow: {
          '0%': { opacity: '0.5' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideIn: {
          '0%': { opacity: '0', transform: 'translateX(-10px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        counter: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        heartbeat: {
          '0%, 100%': { transform: 'scale(1)' },
          '50%': { transform: 'scale(1.05)' },
        },
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'grid-pattern': 'linear-gradient(to right, var(--color-slate-border) 1px, transparent 1px), linear-gradient(to bottom, var(--color-slate-border) 1px, transparent 1px)',
      },
    },
  },
  plugins: [],
}
export default config
