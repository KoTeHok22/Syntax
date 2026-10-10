/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        base: '#EFEBE3',
        raised: '#F3EFE8',
        inset: '#E7E2D9',
        sunken: '#E1DBD1',
        pvn: {
          blue: '#402FFF',
          'blue-dark': '#2C1FE0',
          'blue-deep': '#1E15B8',
          red: '#EC1D35',
          'red-dark': '#CF1229',
          'red-ink': '#B8101F',
          dark: '#1B1C21',
        },
        ink: {
          DEFAULT: '#1B1C21',
          secondary: '#6A6459',
          muted: '#8B8578',
          line: '#C8C9CA',
        },
        good: {
          DEFAULT: '#1E9E5A',
          ink: '#147A43',
        },
        warn: {
          DEFAULT: '#B07C00',
          ink: '#8A6100',
        },
        outline: '#C8C9CA',
      },
      borderRadius: {
        DEFAULT: '0.75rem',
        lg: '0.75rem',
        xl: '1rem',
        '2xl': '1.25rem',
        panel: '20px',
        full: '9999px',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      fontSize: {
        display: ['28px', { lineHeight: '34px', letterSpacing: '-0.02em', fontWeight: '700' }],
        h2: ['20px', { lineHeight: '28px', letterSpacing: '-0.01em', fontWeight: '700' }],
        h3: ['16px', { lineHeight: '22px', fontWeight: '600' }],
        body: ['15px', { lineHeight: '22px', fontWeight: '400' }],
        caption: ['13px', { lineHeight: '18px', fontWeight: '400' }],
        score: ['24px', { lineHeight: '28px', letterSpacing: '-0.02em', fontWeight: '700' }],
        label: ['11px', { lineHeight: '14px', letterSpacing: '0.08em', fontWeight: '600' }],
        chip: ['12px', { lineHeight: '16px', fontWeight: '500' }],
      },
      boxShadow: {
        raised: '6px 6px 16px rgba(27,28,33,0.10), -6px -6px 14px rgba(255,255,255,0.85)',
        'raised-sm': '3px 3px 9px rgba(27,28,33,0.09), -3px -3px 8px rgba(255,255,255,0.80)',
        'raised-lg': '10px 10px 26px rgba(27,28,33,0.12), -8px -8px 20px rgba(255,255,255,0.90)',
        inset: 'inset 3px 3px 8px rgba(27,28,33,0.10), inset -3px -3px 8px rgba(255,255,255,0.90)',
        'inset-sm': 'inset 2px 2px 5px rgba(27,28,33,0.09), inset -2px -2px 5px rgba(255,255,255,0.85)',
        pressed: 'inset 2px 2px 6px rgba(27,28,33,0.18), inset -2px -2px 6px rgba(255,255,255,0.70)',
        blue: '0 6px 14px rgba(64,47,255,0.34), inset 0 1px 0 rgba(255,255,255,0.28)',
        'blue-lg': '0 10px 24px rgba(64,47,255,0.40), inset 0 1px 0 rgba(255,255,255,0.28)',
        red: '0 8px 18px rgba(236,29,53,0.34), inset 0 1px 0 rgba(255,255,255,0.30)',
        'red-lg': '0 12px 26px rgba(236,29,53,0.42), inset 0 1px 0 rgba(255,255,255,0.30)',
      },
      backgroundImage: {
        'red-btn': 'linear-gradient(180deg, #F5304A 0%, #EC1D35 55%, #D9152B 100%)',
        'blue-btn': 'linear-gradient(180deg, #5544FF 0%, #402FFF 55%, #3423E6 100%)',
      },
    },
  },
  plugins: [],
}
