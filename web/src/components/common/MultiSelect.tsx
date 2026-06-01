import { useEffect, useMemo, useRef, useState } from "react"

export type MultiSelectOption<T> = {
  id: number
  label: string
  meta?: string
  searchHay: string
  raw: T
}

type Props<T> = {
  options: MultiSelectOption<T>[]
  selectedIds: number[]
  onChange: (ids: number[]) => void
  placeholder?: string
  emptyMessage?: string
}

/**
 * Chip + dropdown multi-select.  Mirrors the behaviour of the buildMultiSelect
 * factory in static/index.html:
 *
 *   - Focus / type in the input → dropdown opens, filters by `searchHay`.
 *   - Selected items are excluded from the dropdown.
 *   - Click an option → adds chip, clears input.
 *   - Click the chip's × → removes from selection.
 *   - Blur closes the dropdown with a 120 ms delay so an option click registers.
 */
export function MultiSelect<T>({
  options,
  selectedIds,
  onChange,
  placeholder = "Type to search…",
  emptyMessage = "No matches",
}: Props<T>) {
  const [query, setQuery] = useState("")
  const [open, setOpen] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const closeTimer = useRef<number | null>(null)

  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds])

  const chips = useMemo(
    () => options.filter((o) => selectedSet.has(o.id)),
    [options, selectedSet],
  )

  const dropdown = useMemo(() => {
    const q = query.trim().toLowerCase()
    return options.filter((o) => {
      if (selectedSet.has(o.id)) return false
      if (!q) return true
      return o.searchHay.toLowerCase().includes(q)
    })
  }, [options, selectedSet, query])

  useEffect(() => {
    return () => {
      if (closeTimer.current) window.clearTimeout(closeTimer.current)
    }
  }, [])

  function add(id: number) {
    onChange([...selectedIds, id])
    setQuery("")
    inputRef.current?.focus()
  }

  function remove(id: number) {
    onChange(selectedIds.filter((x) => x !== id))
  }

  function handleBlur() {
    closeTimer.current = window.setTimeout(() => setOpen(false), 120)
  }

  function handleFocus() {
    if (closeTimer.current) window.clearTimeout(closeTimer.current)
    setOpen(true)
  }

  return (
    <div className="ms-wrap" onMouseDown={() => inputRef.current?.focus()}>
      {chips.map((c) => (
        <span key={c.id} className="ms-chip">
          {c.label}
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation()
              remove(c.id)
            }}
            aria-label={`Remove ${c.label}`}
          >
            ×
          </button>
        </span>
      ))}
      <input
        ref={inputRef}
        className="ms-input"
        placeholder={chips.length === 0 ? placeholder : ""}
        value={query}
        onFocus={handleFocus}
        onBlur={handleBlur}
        onChange={(e) => {
          setQuery(e.target.value)
          setOpen(true)
        }}
        onKeyDown={(e) => {
          if (e.key === "Backspace" && !query && chips.length > 0) {
            remove(chips[chips.length - 1].id)
          }
        }}
      />
      {open && (
        <div className="ms-dropdown">
          {dropdown.length === 0 ? (
            <div className="ms-empty">{emptyMessage}</div>
          ) : (
            dropdown.map((o) => (
              <button
                key={o.id}
                type="button"
                className="ms-item w-full text-left"
                // mousedown fires before blur so the click registers before
                // the dropdown auto-closes.
                onMouseDown={(e) => {
                  e.preventDefault()
                  add(o.id)
                }}
              >
                <span>{o.label}</span>
                {o.meta && <span className="meta">{o.meta}</span>}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  )
}
