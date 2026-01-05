/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/templates/**/*.html",
    "./app/modules/**/templates/**/*.html",
  ],
  theme: {
    extend: {
      fontFamily: {
        display: ['"DM Sans"', 'system-ui', 'sans-serif'],
        body: ['"Source Sans 3"', 'system-ui', 'sans-serif'],
      },
      colors: {
        // Deep teal - professional yet distinctive
        primary: {
          50: '#effcfc',
          100: '#d7f5f6',
          200: '#b3ebec',
          300: '#7fdcdf',
          400: '#44c3c9',
          500: '#28a7ae',
          600: '#0d7377',
          700: '#135c60',
          800: '#164b4e',
          900: '#173f42',
          950: '#082628',
        },
        // Warm amber accent
        accent: {
          50: '#fffbeb',
          100: '#fef3c7',
          200: '#fde68a',
          300: '#fcd34d',
          400: '#f2a900',
          500: '#d97706',
          600: '#b45309',
          700: '#92400e',
          800: '#78350f',
          900: '#451a03',
        },
        // Rich charcoal for sidebar
        slate: {
          850: '#1a1d21',
          950: '#0f1114',
        },
        // Warm backgrounds
        surface: {
          50: '#fdfcfb',
          100: '#faf9f7',
          200: '#f5f3f0',
        },
      },
      boxShadow: {
        'warm-sm': '0 1px 2px 0 rgba(26, 29, 33, 0.04)',
        'warm': '0 1px 3px 0 rgba(26, 29, 33, 0.08), 0 1px 2px -1px rgba(26, 29, 33, 0.08)',
        'warm-md': '0 4px 6px -1px rgba(26, 29, 33, 0.08), 0 2px 4px -2px rgba(26, 29, 33, 0.06)',
        'warm-lg': '0 10px 15px -3px rgba(26, 29, 33, 0.08), 0 4px 6px -4px rgba(26, 29, 33, 0.06)',
        'warm-xl': '0 20px 25px -5px rgba(26, 29, 33, 0.1), 0 8px 10px -6px rgba(26, 29, 33, 0.08)',
        'inner-glow': 'inset 0 1px 0 0 rgba(255, 255, 255, 0.05)',
        // Enhanced focus ring for better accessibility
        'focus-ring': '0 0 0 3px rgba(13, 115, 119, 0.4)',
      },
      ringWidth: {
        '3': '3px',
      },
      ringColor: {
        'focus': 'rgba(13, 115, 119, 0.4)',
      },
      animation: {
        'fade-in': 'fadeIn 0.5s ease-out',
        'fade-up': 'fadeUp 0.5s ease-out',
        'slide-in-right': 'slideInRight 0.3s ease-out',
        'slide-out-right': 'slideOutRight 0.25s ease-in forwards',
        'scale-in': 'scaleIn 0.2s ease-out',
        'shimmer': 'shimmer 2s linear infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        fadeUp: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideInRight: {
          '0%': { opacity: '0', transform: 'translateX(20px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        slideOutRight: {
          '0%': { opacity: '1', transform: 'translateX(0)' },
          '100%': { opacity: '0', transform: 'translateX(20px)' },
        },
        scaleIn: {
          '0%': { opacity: '0', transform: 'scale(0.95)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
    },
  },
  plugins: [],
}
