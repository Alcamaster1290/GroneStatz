import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        surface: "var(--surface)",
        line: "var(--line)",
        ink: "var(--ink)",
        muted: "var(--muted)",
        accent: "var(--accent)",
        win: "var(--win)",
        draw: "var(--draw)",
        loss: "var(--loss)",
      },
      fontFamily: { sans: ["system-ui", "-apple-system", "Segoe UI", "Roboto", "Helvetica Neue", "Arial", "sans-serif"] },
    },
  },
  plugins: [],
};

export default config;
