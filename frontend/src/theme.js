/**
 * Design tokens — README Section 7.
 *
 * The CSS custom properties in styles.css are the source of truth for anything
 * styled in CSS; this module exports the same values for the handful of places
 * that need a colour in JS (inline badge backgrounds, chart-free status dots).
 */
export const theme = {
  color: {
    bgApp: "#f4f3ef",
    surface: "#ffffff",
    surfaceSunk: "#f6f5f1",
    surfaceSunkAlt: "#f0efe9",
    ink: "#1a1a18",
    inkSoft: "rgba(0, 0, 0, .45)",
    accent: "oklch(0.58 0.11 152)",
    accentInk: "oklch(0.42 0.11 152)",
    accentTint: "oklch(0.96 0.03 152)",
    warn: "oklch(0.62 0.14 60)",
    warnInk: "oklch(0.5 0.15 40)",
    warnTint: "oklch(0.95 0.05 40)",
    danger: "oklch(0.5 0.16 30)",
    dangerInk: "oklch(0.55 0.16 28)",
  },
  radius: { card: "13px", panel: "18px", pill: "20px", control: "11px", tight: "8px" },
  shadow: {
    card: "0 1px 2px rgba(0, 0, 0, .04)",
    modal: "0 20px 60px rgba(0, 0, 0, .28)",
  },
  font: "'Public Sans', system-ui, -apple-system, sans-serif",
};

/** Ledger activity dot colours, keyed by StockMove.reason. */
export const moveColor = {
  SALE: theme.color.accent,
  RECEIVE: "oklch(0.6 0.13 152)",
  REMOVE: theme.color.warnInk,
  OPENING: "oklch(0.55 0.11 260)",
};

export default theme;
