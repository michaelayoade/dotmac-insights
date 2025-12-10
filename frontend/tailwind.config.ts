import type { Config } from 'tailwindcss'

const config: Config = {
  darkMode: 'class',
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Base colors - using CSS variables for theme switching
        'slate-deep': 'var(--color-slate-deep)',
        'slate-card': 'var(--color-slate-card)',
        'slate-elevated': 'var(--color-slate-elevated)',
        'slate-border': 'var(--color-slate-border)',
        'slate-muted': 'var(--color-slate-muted)',

        // Accent colors - using CSS variables for theme switching
        'teal-electric': 'var(--color-teal-electric)',
        'teal-glow': 'var(--color-teal-glow)',
        'coral-alert': 'var(--color-coral-alert)',
        'amber-warn': 'var(--color-amber-warn)',
        'blue-info': '#3b82f6',
        'purple-accent': '#a855f7',
      },
      fontFamily: {
        'display': ['Plus Jakarta Sans', 'sans-serif'],
        'mono': ['JetBrains Mono', 'monospace'],
        'body': ['Plus Jakarta Sans', 'sans-serif'],
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
        'grid-pattern': 'linear-gradient(to right, #2d3a4f 1px, transparent 1px), linear-gradient(to bottom, #2d3a4f 1px, transparent 1px)',
      },
    },
  },
  plugins: [],
}
export default config
