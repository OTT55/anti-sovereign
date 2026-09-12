import type { Config } from "tailwindcss";

/**
 * Shared Tailwind preset for every app in the portfolio. Colors/radii/motion
 * all resolve to the CSS custom properties in ./tokens.css so each app only
 * needs to override --accent to express its own product identity.
 */
const preset: Partial<Config> = {
  darkMode: ["class"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        surface: "var(--surface)",
        elevated: "var(--elevated)",
        text: "var(--text)",
        muted: "var(--muted)",
        border: "var(--border)",
        signature: "var(--ott-signature)",
        ok: "var(--ok)",
        warn: "var(--warn)",
        danger: "var(--danger)",
        info: "var(--info)",
        accent: {
          DEFAULT: "var(--accent)",
          glow: "var(--accent-glow)",
          subtle: "var(--accent-subtle)",
          border: "var(--accent-border)",
        },
      },
      borderRadius: {
        xs: "var(--r-xs)",
        sm: "var(--r-sm)",
        md: "var(--r-md)",
        lg: "var(--r-lg)",
        pill: "var(--r-pill)",
      },
      transitionTimingFunction: {
        vibe: "var(--ease-vibe)",
        bounce: "var(--ease-bounce)",
      },
      transitionDuration: {
        fast: "var(--dur-fast)",
        base: "var(--dur-base)",
        slow: "var(--dur-slow)",
      },
      fontFamily: {
        display: ["var(--font-display)", "sans-serif"],
        sans: ["var(--font-sans)", "sans-serif"],
        mono: ["var(--font-mono)", "monospace"],
      },
      backdropBlur: {
        glass: "16px",
      },
      boxShadow: {
        glass: "0 8px 32px rgba(0, 0, 0, 0.32)",
      },
    },
  },
};

export default preset;
