/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#071329",
        muted: "#5b667f",
        line: "#dfe5ef",
        brand: "#604fd8",
        teal: "#15beb5",
        coral: "#ff7b65"
      },
      boxShadow: {
        soft: "0 16px 42px rgba(39, 50, 90, 0.12)"
      }
    }
  },
  plugins: []
};
