// Shared risk color scale + labels (mirrors backend routing.core.risk).
export const RISK = [
  { label: "Low", color: "#22c55e" },
  { label: "Moderate", color: "#eab308" },
  { label: "High", color: "#f97316" },
  { label: "Severe", color: "#ef4444" },
  { label: "No Travel", color: "#1f2937" },
];

export const riskColor = (level) => (RISK[level] || RISK[0]).color;
export const riskLabel = (level) => (RISK[level] || RISK[0]).label;

export function fmtTime(iso) {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    weekday: "short",
    hour: "numeric",
    minute: "2-digit",
    month: "short",
    day: "numeric",
  });
}
