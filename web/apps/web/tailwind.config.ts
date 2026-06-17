import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  darkMode: "media",
  theme: {
    extend: {
      colors: {
        // Single neutral palette; we'll add semantic tokens when the design
        // system grows past "good enough to read".
        brand: {
          50: "#f5f7fb",
          100: "#e7ecf5",
          500: "#5b6dff",
          600: "#4a5cf0",
          700: "#3c4dd6",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
