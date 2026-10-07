import type { Mode } from "./types";

export const pct = (x: number, digits = 1) => `${(x * 100).toFixed(digits)}%`;
export const num = (x: number) => x.toLocaleString("en-US");
export const ms = (x: number) => `${Math.round(x)} ms`;

export const MODE_LABEL: Record<Mode, string> = {
  never: "Never retrieve",
  always: "Always retrieve",
  adaptive: "Adaptive",
};

export const MODE_COLOR: Record<Mode, string> = {
  never: "var(--never)",
  always: "var(--always)",
  adaptive: "var(--adaptive)",
};

export const compact = (n: number) => Intl.NumberFormat("en-US", { notation: "compact" }).format(n);

export const TOOLTIP = {
  background: "var(--surface)",
  border: "1px solid var(--border)",
  borderRadius: 6,
  color: "var(--text)",
  fontSize: 13,
};

export const AXIS_TICK = { fill: "var(--muted)", fontSize: 12 };
