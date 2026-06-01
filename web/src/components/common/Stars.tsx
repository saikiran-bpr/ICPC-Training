/**
 * Renders a 0–5 numeric score as star glyphs (★ ½ ☆), like the original
 * static/index.html does for CF / Universal Cup difficulty.
 */
export function Stars({
  value,
  label,
  color,
}: {
  value: number | null | undefined
  label: string
  color?: string
}) {
  if (value == null) return null
  const full = Math.floor(value)
  const half = value - full >= 0.25 && value - full < 0.75 ? 1 : 0
  const empty = 5 - full - half
  return (
    <span
      title={`${label}: ${value.toFixed(1)} / 5`}
      className="inline-flex items-center gap-1 px-2 py-[2px] text-[11px] rounded border"
      style={{ borderColor: "var(--c-border)", color: color ?? "var(--c-muted)" }}
    >
      <span className="font-medium opacity-80">{label}</span>
      <span>
        {"★".repeat(full)}
        {half ? "½" : ""}
        {"☆".repeat(empty)}
      </span>
    </span>
  )
}
