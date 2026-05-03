/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{ts,tsx}", "./src/**/*.{ts,tsx}"],
  presets: [require("nativewind/preset")],
  theme: {
    extend: {
      colors: {
        // Aligned with apps/web design tokens
        primary: {
          50: "#EFF6FF",
          100: "#DBEAFE",
          200: "#BFDBFE",
          300: "#93C5FD",
          400: "#60A5FA",
          500: "#3B82F6",
          600: "#2563EB",
          700: "#1D4ED8",
          800: "#1E40AF",
          900: "#1E3A8A",
          950: "#172554",
        },
        surface: {
          light: "#FFFFFF",
          dark: "#0F172A",
        },
        card: {
          light: "#F8FAFC",
          dark: "#1E293B",
        },
        text: {
          primary: { light: "#0F172A", dark: "#F1F5F9" },
          secondary: { light: "#475569", dark: "#94A3B8" },
          muted: { light: "#94A3B8", dark: "#64748B" },
        },
        accent: {
          green: "#10B981",
          red: "#EF4444",
          yellow: "#F59E0B",
        },
      },
      fontFamily: {
        sans: ["Inter", "System"],
        mono: ["JetBrains Mono", "monospace"],
      },
    },
  },
  plugins: [],
};
