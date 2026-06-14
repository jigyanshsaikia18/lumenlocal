import type { Config } from "tailwindcss";

/**
 * Colors are driven by CSS variables (RGB channel triplets) so an agency's
 * white-label theme can override them at runtime via <ThemeProvider> without a
 * rebuild. The `<alpha-value>` placeholder keeps Tailwind opacity modifiers
 * (e.g. `bg-brand/10`) working against the variables.
 */
const withVar = (name: string) => `rgb(var(${name}) / <alpha-value>)`;

const config: Config = {
  content: [
    "./src/app/**/*.{ts,tsx}",
    "./src/components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: withVar("--ll-brand"),
          foreground: withVar("--ll-brand-foreground"),
          soft: withVar("--ll-brand-soft"),
        },
        accent: withVar("--ll-accent"),
        canvas: withVar("--ll-canvas"),
        surface: withVar("--ll-surface"),
        foreground: withVar("--ll-foreground"),
        muted: withVar("--ll-muted"),
        hairline: withVar("--ll-hairline"),
        positive: withVar("--ll-positive"),
        negative: withVar("--ll-negative"),
      },
      borderRadius: {
        xl: "0.875rem",
        "2xl": "1.25rem",
      },
      boxShadow: {
        // Soft, layered elevation for a premium card feel.
        card: "0 1px 2px 0 rgb(15 23 42 / 0.04), 0 8px 24px -12px rgb(15 23 42 / 0.12)",
        "card-hover": "0 1px 2px 0 rgb(15 23 42 / 0.05), 0 16px 40px -16px rgb(15 23 42 / 0.22)",
      },
      fontFamily: {
        sans: ["var(--ll-font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
