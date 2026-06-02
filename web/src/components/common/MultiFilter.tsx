import { useEffect, useRef, useState } from "react"

/** Normalise a (single | multi | empty) filter value to a string array. */
export function asArr(v: string | string[] | undefined): string[] {
  if (Array.isArray(v)) return v
  return v ? [v] : []
}

/**
 * Multi-select filter: a button summary + a checkbox dropdown. Shared by the
 * Problem Bank toolbar and the Assigned Problems sidebar.
 */
export function MultiFilter({
  label,
  selected,
  options,
  onChange,
}: {
  label: string
  selected: string[]
  options: string[] | undefined
  onChange: (vals: string[]) => void
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function onDown(e: MouseEvent) {
      if (!ref.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener("mousedown", onDown)
    return () => document.removeEventListener("mousedown", onDown)
  }, [open])

  function toggle(o: string) {
    onChange(
      selected.includes(o) ? selected.filter((x) => x !== o) : [...selected, o],
    )
  }

  const summary =
    selected.length === 0
      ? "All"
      : selected.length === 1
        ? selected[0]
        : `${selected.length} selected`

  return (
    <div className="flex flex-col" ref={ref}>
      <label className="filter-label">{label}</label>
      <div className="relative">
        <button
          type="button"
          className="filter-control min-w-[130px] w-full text-left truncate"
          onClick={() => setOpen((o) => !o)}
          title={selected.join(", ")}
        >
          {summary}
        </button>
        {open && (
          <div
            className="absolute z-20 mt-1 max-h-[260px] overflow-auto rounded-md border shadow-lg p-1 min-w-[190px]"
            style={{ background: "var(--c-panel)", borderColor: "var(--c-border)" }}
          >
            {(options ?? []).length === 0 ? (
              <div className="px-2 py-1 text-[12px] text-[color:var(--c-muted)]">
                No options
              </div>
            ) : (
              (options ?? []).map((o) => (
                <label
                  key={o}
                  className="flex items-center gap-2 px-2 py-1 text-[13px] cursor-pointer rounded hover:bg-[color:var(--c-panel-2)]"
                >
                  <input
                    type="checkbox"
                    checked={selected.includes(o)}
                    onChange={() => toggle(o)}
                  />
                  <span className="truncate">{o}</span>
                </label>
              ))
            )}
            {selected.length > 0 && (
              <button
                type="button"
                className="w-full text-left px-2 py-1 mt-1 text-[12px] text-[color:var(--c-muted)] rounded hover:bg-[color:var(--c-panel-2)]"
                onClick={() => onChange([])}
              >
                Clear selection
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
