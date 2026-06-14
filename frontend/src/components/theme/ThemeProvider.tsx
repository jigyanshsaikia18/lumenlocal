import type { CSSProperties, ReactNode } from "react";

/**
 * White-label brand theme. Each value is an RGB channel triplet (e.g. "79 70 229")
 * matching the `--ll-*` variables in globals.css. An agency supplies any subset;
 * unspecified tokens fall back to the platform default theme.
 */
export interface BrandTheme {
  brand?: string;
  brandForeground?: string;
  brandSoft?: string;
  accent?: string;
  canvas?: string;
  surface?: string;
  foreground?: string;
  muted?: string;
  hairline?: string;
  positive?: string;
  negative?: string;
  fontSans?: string;
}

const VAR_BY_KEY: Record<keyof BrandTheme, string> = {
  brand: "--ll-brand",
  brandForeground: "--ll-brand-foreground",
  brandSoft: "--ll-brand-soft",
  accent: "--ll-accent",
  canvas: "--ll-canvas",
  surface: "--ll-surface",
  foreground: "--ll-foreground",
  muted: "--ll-muted",
  hairline: "--ll-hairline",
  positive: "--ll-positive",
  negative: "--ll-negative",
  fontSans: "--ll-font-sans",
};

/** Map a partial brand theme to the inline CSS-variable overrides it sets. */
export function themeToCssVars(theme: BrandTheme): CSSProperties {
  const style: Record<string, string> = {};
  for (const [key, value] of Object.entries(theme)) {
    if (value) style[VAR_BY_KEY[key as keyof BrandTheme]] = value;
  }
  return style as CSSProperties;
}

interface ThemeProviderProps {
  theme?: BrandTheme;
  children: ReactNode;
  className?: string;
}

/**
 * Applies an agency's white-label theme by overriding the `--ll-*` CSS variables
 * on a wrapper element. Children (and all Tailwind brand tokens) inherit them, so
 * the same components render in any agency's palette with no rebuild.
 */
export function ThemeProvider({ theme, children, className }: ThemeProviderProps) {
  return (
    <div
      data-theme-scope
      className={className}
      style={theme ? themeToCssVars(theme) : undefined}
    >
      {children}
    </div>
  );
}
