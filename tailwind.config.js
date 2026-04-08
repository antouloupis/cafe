/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./routers/**/*.py" // Just in case you return raw HTML strings from FastAPI
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}