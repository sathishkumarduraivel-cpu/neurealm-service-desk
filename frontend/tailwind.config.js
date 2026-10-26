/** @type {import('tailwindcss').Config} */
import animate from "tailwindcss-animate";
const v = (n) => `hsl(var(--${n}) / <alpha-value>)`;
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    container: { center: true, padding: "1.5rem" },
    extend: {
      fontFamily: { sans: ["Roboto", "ui-sans-serif", "system-ui", "sans-serif"], display: ["Exo", "ui-sans-serif", "system-ui", "sans-serif"], mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"] },
      colors: {
        border: v("border"), input: v("input"), ring: v("ring"), background: v("background"), foreground: v("foreground"),
        primary: { DEFAULT: v("primary"), foreground: v("primary-foreground") },
        secondary: { DEFAULT: v("secondary"), foreground: v("secondary-foreground") },
        destructive: { DEFAULT: v("destructive"), foreground: v("destructive-foreground") },
        muted: { DEFAULT: v("muted"), foreground: v("muted-foreground") },
        accent: { DEFAULT: v("accent"), foreground: v("accent-foreground") },
        popover: { DEFAULT: v("popover"), foreground: v("popover-foreground") },
        card: { DEFAULT: v("card"), foreground: v("card-foreground") },
        sidebar: { DEFAULT: v("sidebar"), foreground: v("sidebar-foreground"), border: v("sidebar-border"), accent: v("sidebar-accent") },
        brand: { 50: "#EEF4FF", 100: "#DCE7FF", 200: "#B9CFFF", 300: "#86AEFF", 400: "#4D86F5", 500: "#1863DC", 600: "#1550BF", 700: "#10399A", 800: "#0C277D", 900: "#081160", 950: "#050B3D" }, nr: { navy: "#081160", ink: "#011C25", red: "#E5002B", blue: "#168AFF", orange: "#E5002B", coral: "#FF5A75", purple: "#081160", indigo: "#1863DC" },
        violet: { 50: "#F8EEF9", 100: "#F0DCF3", 200: "#E0B8E6", 300: "#CB8AD4", 400: "#AF57BC", 500: "#9634A4", 600: "#82228E", 700: "#6C1C76", 800: "#561760", 900: "#42124A", 950: "#2A0B30" }, purple: { 50: "#F8EEF9", 100: "#F0DCF3", 200: "#E0B8E6", 300: "#CB8AD4", 400: "#AF57BC", 500: "#9634A4", 600: "#82228E", 700: "#6C1C76", 800: "#561760", 900: "#42124A", 950: "#2A0B30" }, indigo: { 50: "#EEF0F9", 100: "#DDE1F3", 200: "#BAC2E6", 300: "#8F9BD5", 400: "#6573C0", 500: "#4452A8", 600: "#2E3B8F", 700: "#263175", 800: "#1E275C", 900: "#161D44", 950: "#0E132D" }, red: { 50: "#FDEEEE", 100: "#FBDCDB", 200: "#F6B8B7", 300: "#F08F8D", 400: "#EA6E6C", 500: "#E5514F", 600: "#CC3B39", 700: "#A92F2D", 800: "#862524", 900: "#631B1B", 950: "#3F1111" }, coral: { 50: "#FDEEEE", 100: "#FBDCDB", 200: "#F6B8B7", 300: "#F08F8D", 400: "#EA6E6C", 500: "#E5514F", 600: "#CC3B39", 700: "#A92F2D", 800: "#862524", 900: "#631B1B", 950: "#3F1111" }, orange: { 50: "#FEF4EC", 100: "#FDE6D4", 200: "#FACCA9", 300: "#F7B07D", 400: "#F49C5D", 500: "#F2893F", 600: "#D9712A", 700: "#B45A1F", 800: "#8E4618", 900: "#683312", 950: "#40200B" }, amber: { 50: "#FEF4EC", 100: "#FDE6D4", 200: "#FACCA9", 300: "#F7B07D", 400: "#F49C5D", 500: "#F2893F", 600: "#D9712A", 700: "#B45A1F", 800: "#8E4618", 900: "#683312", 950: "#40200B" }, navy: { 50: "#F1F3F8", 100: "#E1E5EF", 200: "#C2C9DC", 300: "#99A3BF", 400: "#6B779A", 500: "#4A5677", 600: "#343F5E", 700: "#26304B", 800: "#1B2540", 900: "#121E39", 950: "#0B1326" }, slate: { 50: "#F1F3F8", 100: "#E1E5EF", 200: "#C2C9DC", 300: "#99A3BF", 400: "#6B779A", 500: "#4A5677", 600: "#343F5E", 700: "#26304B", 800: "#1B2540", 900: "#121E39", 950: "#0B1326" },
      },
      borderRadius: { lg: "var(--radius)", md: "calc(var(--radius) - 2px)", sm: "calc(var(--radius) - 4px)" },
      boxShadow: { xs: "0 1px 2px 0 rgb(15 23 42 / 0.04)", soft: "0 1px 3px 0 rgb(15 23 42 / 0.06), 0 1px 2px -1px rgb(15 23 42 / 0.04)", pop: "0 10px 30px -10px rgb(15 23 42 / 0.25)" },
      keyframes: { shimmer: { "100%": { transform: "translateX(100%)" } } },
    },
  },
  plugins: [animate],
};
