import { useCallback, useEffect, useMemo, useRef, useState } from "react"

export type AsyncMultiSelectItem = {
  id: number
  label: string
  /** Secondary line shown under the label (e.g. handle / institution). */
  meta?: string
}

export type AsyncSearchResult = {
  total: number
  results: AsyncMultiSelectItem[]
}

type Props = {
  /** Currently-selected items (controlled).  Carried as full objects so chips
   *  render even when the selection isn't on the current search page. */
  selected: AsyncMultiSelectItem[]
  onChange: (items: AsyncMultiSelectItem[]) => void
  /** Server-side search.  Receives the (debounced) query + page window. */
  search: (
    query: string,
    opts: { limit: number; offset: number; signal: AbortSignal },
  ) => Promise<AsyncSearchResult>
  placeholder?: string
  /** Rows fetched per page (loaded incrementally as the list is scrolled). */
  pageSize?: number
  /** Debounce window for the search input, in ms. */
  debounceMs?: number
  emptyMessage?: string
}

/**
 * Chip + dropdown multi-select backed by a **server-side** search with
 * **infinite scroll**.
 *
 * Scales to large rosters:
 *  - The search box matches whatever the `search` callback supports (for the
 *    user picker that's name *or* Codeforces handle, resolved server-side).
 *  - Typing is debounced (`debounceMs`, default 300ms); an AbortController
 *    cancels any in-flight request when the query changes.
 *  - Results accumulate and the next page loads automatically as the dropdown
 *    is scrolled near the bottom — no Prev/Next buttons.
 *  - Already-selected ids are filtered out of the list.
 *
 * Closing: outside-click is detected on a **capture-phase** document listener
 * (the surrounding Modal stops bubble-phase mousedown, so a bubble listener
 * would never see clicks made inside the modal) plus Escape.
 */
export function AsyncMultiSelect({
  selected,
  onChange,
  search,
  placeholder = "Type to search…",
  pageSize = 20,
  debounceMs = 300,
  emptyMessage = "No matches",
}: Props) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const [debouncedQuery, setDebouncedQuery] = useState("")
  const [items, setItems] = useState<AsyncMultiSelectItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const rootRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const ctrlRef = useRef<AbortController | null>(null)
  const loadingRef = useRef(false)

  const selectedSet = useMemo(() => new Set(selected.map((s) => s.id)), [selected])

  // Close on outside click (capture phase) / Escape.
  useEffect(() => {
    if (!open) return
    function onDown(e: MouseEvent) {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false)
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false)
    }
    document.addEventListener("mousedown", onDown, true)
    document.addEventListener("keydown", onKey)
    return () => {
      document.removeEventListener("mousedown", onDown, true)
      document.removeEventListener("keydown", onKey)
    }
  }, [open])

  // Debounce `query` -> `debouncedQuery`.
  useEffect(() => {
    if (query === debouncedQuery) return
    const t = setTimeout(() => setDebouncedQuery(query), debounceMs)
    return () => clearTimeout(t)
  }, [query, debouncedQuery, debounceMs])

  const loadPage = useCallback(
    (offset: number, replace: boolean) => {
      // A scroll-triggered append must not stack on an in-flight request;
      // a query-change replace always interrupts whatever is running.
      if (!replace && loadingRef.current) return
      ctrlRef.current?.abort()
      const ctrl = new AbortController()
      ctrlRef.current = ctrl
      loadingRef.current = true
      setLoading(true)
      setError(null)
      search(debouncedQuery, { limit: pageSize, offset, signal: ctrl.signal })
        .then((res) => {
          setTotal(res.total)
          setItems((prev) => (replace ? res.results : [...prev, ...res.results]))
        })
        .catch((e: unknown) => {
          if (ctrl.signal.aborted) return
          if ((e as { name?: string })?.name === "AbortError") return
          setError(e instanceof Error ? e.message : "Search failed")
        })
        .finally(() => {
          if (ctrl.signal.aborted) return
          loadingRef.current = false
          setLoading(false)
        })
    },
    [search, debouncedQuery, pageSize],
  )

  // (Re)load the first page whenever opened or the debounced query changes.
  useEffect(() => {
    if (!open) return
    if (listRef.current) listRef.current.scrollTop = 0
    loadPage(0, true)
  }, [open, debouncedQuery, loadPage])

  function onScroll() {
    const el = listRef.current
    if (!el || loadingRef.current) return
    if (items.length >= total) return
    if (el.scrollHeight - el.scrollTop - el.clientHeight < 48) {
      loadPage(items.length, false)
    }
  }

  const visible = items.filter((r) => !selectedSet.has(r.id))
  const hasMore = items.length < total

  // If every loaded row is already selected there's nothing to scroll, so the
  // scroll handler can't fire — pull the next page until something shows or the
  // results are exhausted.
  useEffect(() => {
    if (!open || loading) return
    if (visible.length === 0 && hasMore) {
      loadPage(items.length, false)
    }
  }, [open, loading, visible.length, hasMore, items.length, loadPage])

  function add(item: AsyncMultiSelectItem) {
    if (selectedSet.has(item.id)) return
    onChange([...selected, item])
    setQuery("")
    inputRef.current?.focus()
  }

  function remove(id: number) {
    onChange(selected.filter((x) => x.id !== id))
  }

  return (
    <div ref={rootRef} className="ms-wrap" onMouseDown={() => inputRef.current?.focus()}>
      {selected.map((c) => (
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
        placeholder={selected.length === 0 ? placeholder : ""}
        value={query}
        onFocus={() => setOpen(true)}
        onChange={(e) => {
          setQuery(e.target.value)
          setOpen(true)
        }}
        onKeyDown={(e) => {
          if (e.key === "Backspace" && !query && selected.length > 0) {
            remove(selected[selected.length - 1].id)
          }
        }}
      />
      {open && (
        <div ref={listRef} className="ms-dropdown" onScroll={onScroll}>
          {error ? (
            <div className="ms-empty" style={{ color: "var(--c-red)" }}>
              {error}
            </div>
          ) : visible.length === 0 && loading ? (
            <div className="ms-empty">Searching…</div>
          ) : visible.length === 0 ? (
            <div className="ms-empty">
              {debouncedQuery ? `${emptyMessage} for "${debouncedQuery}".` : emptyMessage}
            </div>
          ) : (
            <>
              {visible.map((o) => (
                <button
                  key={o.id}
                  type="button"
                  className="ms-item w-full text-left"
                  // mousedown fires before blur so the click registers.
                  onMouseDown={(e) => {
                    e.preventDefault()
                    add(o)
                  }}
                >
                  <span>{o.label}</span>
                  {o.meta && <span className="meta">{o.meta}</span>}
                </button>
              ))}
              {loading && <div className="ms-empty">Loading…</div>}
              {!loading && !hasMore && total > pageSize && (
                <div className="ms-empty">All {total} shown</div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
