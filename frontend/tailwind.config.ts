import type { Config } from 'tailwindcss'
import animate from 'tailwindcss-animate'

const config: Config = {
  darkMode: ['selector', '[data-theme="dark"]'],
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    container: {
      center: true,
      padding: '2rem',
      screens: {
        '2xl': '1400px',
      },
    },
    extend: {
      fontFamily: {
        sans: 'var(--font-sans)',
        mono: 'var(--font-mono)',
      },
      colors: {
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
        sidebar: {
          DEFAULT: 'hsl(var(--sidebar-background))',
          foreground: 'hsl(var(--sidebar-foreground))',
          primary: 'hsl(var(--sidebar-primary))',
          'primary-foreground': 'hsl(var(--sidebar-primary-foreground))',
          accent: 'hsl(var(--sidebar-accent))',
          'accent-foreground': 'hsl(var(--sidebar-accent-foreground))',
          border: 'hsl(var(--sidebar-border))',
          ring: 'hsl(var(--sidebar-ring))',
        },
        'chart-1': 'hsl(var(--chart-1))',
        'chart-2': 'hsl(var(--chart-2))',
        'chart-3': 'hsl(var(--chart-3))',
        'chart-4': 'hsl(var(--chart-4))',
        'chart-5': 'hsl(var(--chart-5))',
        canvas: 'var(--canvas)',
        surface: 'var(--surface)',
        'surface-2': 'var(--surface-2)',
        'surface-3': 'var(--surface-3)',
        hairline: 'var(--hairline)',
        'hairline-strong': 'var(--hairline-strong)',
        ink: {
          1: 'var(--ink-1)',
          2: 'var(--ink-2)',
          3: 'var(--ink-3)',
          4: 'var(--ink-4)',
        },
        iris: {
          1: 'var(--iris-1)',
          2: 'var(--iris-2)',
          3: 'var(--iris-3)',
          4: 'var(--iris-4)',
        },
        'blue-token': {
          DEFAULT: 'var(--blue)',
          soft: 'var(--blue-soft)',
          ink: 'var(--blue-ink)',
        },
        success: 'var(--success)',
        warn: 'var(--warn)',
        danger: 'var(--danger)',
        info: 'var(--info)',
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
        xl: 'var(--radius-xl)',
        full: 'var(--radius-full)',
      },
      boxShadow: {
        xs: 'var(--shadow-xs)',
        'token-sm': 'var(--shadow-sm)',
        'token-md': 'var(--shadow-md)',
        'token-lg': 'var(--shadow-lg)',
      },
      keyframes: {
        'accordion-down': {
          from: { height: '0' },
          to: { height: 'var(--radix-accordion-content-height)' },
        },
        'accordion-up': {
          from: { height: 'var(--radix-accordion-content-height)' },
          to: { height: '0' },
        },
        'iris-breathe': {
          '0%, 100%': { opacity: '0.55', transform: 'scale(1)' },
          '50%': { opacity: '0.95', transform: 'scale(1.02)' },
        },
        'fade-up': {
          from: { opacity: '0', transform: 'translateY(6px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'fade-in': {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        'pulse-dot': {
          '0%, 100%': { opacity: '0.65', transform: 'scale(1)' },
          '50%': { opacity: '1', transform: 'scale(1.15)' },
        },
        'shimmer-sheen': {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(200%)' },
        },
        'count-tick': {
          '0%': { transform: 'translateY(-3px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        'progress-stripe': {
          '0%': { backgroundPosition: '0 0' },
          '100%': { backgroundPosition: '24px 0' },
        },
        'spark-draw': {
          from: { strokeDashoffset: '400' },
          to: { strokeDashoffset: '0' },
        },
        spinner: {
          to: { transform: 'rotate(360deg)' },
        },
        'ring-pulse': {
          '0%': {
            boxShadow:
              '0 0 0 0 color-mix(in oklch, var(--iris-3) 50%, transparent)',
          },
          '70%': {
            boxShadow:
              '0 0 0 10px color-mix(in oklch, var(--iris-3) 0%, transparent)',
          },
          '100%': {
            boxShadow:
              '0 0 0 0 color-mix(in oklch, var(--iris-3) 0%, transparent)',
          },
        },
      },
      animation: {
        'accordion-down': 'accordion-down 0.2s ease-out',
        'accordion-up': 'accordion-up 0.2s ease-out',
        'iris-breathe': 'iris-breathe 5200ms ease-in-out infinite',
        'fade-up': 'fade-up var(--dur-3) var(--ease-out) both',
        'fade-in': 'fade-in var(--dur-2) var(--ease-out) both',
        'pulse-dot': 'pulse-dot 1600ms ease-in-out infinite',
        'shimmer-sheen': 'shimmer-sheen 1400ms ease-out infinite',
        'count-tick': 'count-tick var(--dur-1) var(--ease-out) both',
        'progress-stripe': 'progress-stripe 1200ms linear infinite',
        'spark-draw': 'spark-draw var(--dur-3) var(--ease-out) both',
        spinner: 'spinner 900ms linear infinite',
        'ring-pulse': 'ring-pulse 1800ms ease-out infinite',
      },
    },
  },
  plugins: [animate],
}

export default config
