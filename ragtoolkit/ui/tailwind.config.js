/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'rag-blue': '#1e40af',
        'rag-green': '#16a34a',
        'rag-amber': '#d97706',
        'rag-red': '#dc2626',
      }
    },
  },
  plugins: [],
} 