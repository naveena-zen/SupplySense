/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        darkBg: '#090D16',
        cardBg: '#111827',
        borderDark: '#1F2937',
        neonBlue: '#3B82F6',
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
