/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        darkBg: '#0D0D0F',
        cardBg: '#1A1A1D',
        borderDark: '#2A2A2E',
        accentOrange: '#FF5A1F',
        neonEmerald: '#10B981',
        neonRose: '#F43F5E',
        neonAmber: '#F59E0B',
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
