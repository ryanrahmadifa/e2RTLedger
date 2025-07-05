/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx}",    // scan pages
    "./components/**/*.{js,ts,jsx,tsx}" // scan components
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
