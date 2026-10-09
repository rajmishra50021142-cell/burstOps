/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        azure: {
          50: '#f0f6ff',
          100: '#e0edfe',
          200: '#b9dbfe',
          300: '#7cbcfd',
          400: '#369cfb',
          500: '#0078D4', // Primary Azure Blue
          600: '#106EBE',
          700: '#005A9E',
          800: '#004578',
          900: '#002447',
          950: '#001833', // Azure Portal dark header
        },
        portal: {
          bg: '#FAF9F8',
          card: '#FFFFFF',
          border: '#EDEBE9',
          text: '#323130',
          secondary: '#605E5C',
          hover: '#F3F2F1',
          header: '#001833',
        },
        portalDark: {
          bg: '#11100F',
          card: '#1B1A19',
          surface: '#252423',
          border: '#323130',
          text: '#F3F2F1',
          secondary: '#A19F9D',
          hover: '#292827',
          header: '#11100F',
        },
        status: {
          green: '#107C10',
          amber: '#FFB900',
          orange: '#D83B01',
          red: '#D13438',
          blue: '#0078D4',
        }
      },
      fontFamily: {
        sans: ['"Segoe UI"', '-apple-system', 'BlinkMacSystemFont', 'Roboto', '"Helvetica Neue"', 'sans-serif'],
        mono: ['"Consolas"', '"Courier New"', 'monospace'],
      },
      borderRadius: {
        sm: '2px',
        DEFAULT: '3px',
        md: '4px',
        lg: '6px',
      },
      boxShadow: {
        azure: '0 1.6px 3.6px 0 rgba(0,0,0,0.132), 0 0.3px 0.9px 0 rgba(0,0,0,0.108)',
        azureElevated: '0 6.4px 14.4px 0 rgba(0,0,0,0.132), 0 1.2px 3.6px 0 rgba(0,0,0,0.108)',
      }
    },
  },
  plugins: [],
}
