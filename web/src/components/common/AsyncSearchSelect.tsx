import { useEffect, useRef, useState } from "react"
import { useDebouncedValue } from "@/hooks/useDebouncedValue"

export type SearchSelectItem = {
  id: number
  label: string
  meta?: string
}

type SearchResult = { total: number; results: SearchSelectItem[] }

type Props = {
  value: SearchSelectItem | null
  onChange: (item: SearchSelectItem | null) => void
  search: (
    query: string,
    opts: { limit: number; offset: number; signal: AbortSignal },
  ) => Promise<SearchResult>
  placeholder?: string
}

/**
 * Searchable single-select (debounced server-side search). Shows the selected
 * item with a clear (×); opening reveals a search box + results to pick from.
 */
export function AsyncSearchSelect({
  value,
  onChange,
  search,
  placeholder = "Search…",
}: Props) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<SearchSelectItem[]>([])
  const [loading, setLoading] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const debounced = useDebouncedValue(query, 300)

  useEffect(() => {
    if (!open) return
    function onDown(e: MouseEvent) {
      if (!ref.current?.contains(e.target as Node)) setOpen(false)
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false)
    }
    document.addEventListener("mousedown", onDown)
    document.addEventListener("keydown", onKey)
    return () => {
      document.removeEventListener("mousedown", onDown)
      document.removeEventListener("keydown", onKey)
    }
  }, [open])

  // Autofocus the search box when opening.
  useEffect(() => {
    if (open) queueMicrotask(() => inputRef.current?.focus())
  }, [open])

  useEffect(() => {
    if (!open) return
    const ctrl = new AbortController()
    setLoading(true)
    search(debounced, { limit: 20, offset: 0, signal: ctrl.signal })
      .then((r) => setResults(r.results))
      .catch((e: unknown) => {
        if (!ctrl.signal.aborted && (e as { name?: string })?.name !== "AbortError")
          setResults([])
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setLoading(false)
      })
    return () => ctrl.abort()
  }, [open, debounced, search])

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        className="filter-control w-full text-left truncate flex items-center justify-between gap-1"
        onClick={() => setOpen((o) => !o)}
        title={value?.label}
      >
        <span className={value ? "" : "text-[color:var(--c-muted)]"}>
          {value ? value.label : placeholder}
        </span>
        {value && (
          <span
            role="button"
            aria-label="Clear"
            className="text-[color:var(--c-muted)] hover:text-[color:var(--c-text)] px-1"
            onClick={(e) => {
              e.stopPropagation()
              onChange(null)
            }}
          >
            ×
          </span>
        )}
      </button>

      {open && (
        <div
          className="absolute z-20 left-0 right-0 mt-1 rounded-md border shadow-lg p-1"
          style={{ background: "var(--c-panel)", borderColor: "var(--c-border)" }}
        >
          <input
            ref={inputRef}
            type="text"
            className="filter-control w-full mb-1"
            placeholder={placeholder}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <div className="max-h-[220px] overflow-auto">
            {loading && results.length === 0 ? (
              <div className="px-2 py-1.5 text-[12px] text-[color:var(--c-muted)]">
                Searching…
              </div>
            ) : results.length === 0 ? (
              <div className="px-2 py-1.5 text-[12px] text-[color:var(--c-muted)]">
                {debounced ? `No matches for "${debounced}".` : "Type to search…"}
              </div>
            ) : (
              results.map((it) => (
                <button
                  key={it.id}
                  type="button"
                  className="w-full text-left px-2 py-1.5 rounded text-[13px] hover:bg-[color:var(--c-panel-2)]"
                  onClick={() => {
                    onChange(it)
                    setOpen(false)
                    setQuery("")
                  }}
                >
                  <div className="truncate">{it.label}</div>
                  {it.meta && (
                    <div className="text-[11px] text-[color:var(--c-muted)] truncate">
                      {it.meta}
                    </div>
                  )}
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
