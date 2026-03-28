module.exports = {
  content: [
    "./dist/index.html",
    "./src/**/*.{js,jsx,ts,tsx,html}",
  ],
  css: [
    "./dist/assets/*.css",
  ],
  output: "./dist/purged",
  safelist: [
    "active",
    "open",
    "show",
    "hidden",
    "dark",
    "light",
    "disabled",
    "selected",
    "loading",
    "error",
    "success",
    "warning",
  ],
};
