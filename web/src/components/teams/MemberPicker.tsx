import { useEffect, useRef, useState } from "react"
import { usersService } from "@/services/users"
import type { User } from "@/types/user"

type Props = {
  /** The team being added to — server excludes existing members/coaches. */
  teamId: number
  canAddMember: boolean
  canAddReserve: boolean
  onAdd: (userId: number, role: "Member" | "Reserve") => Promise<void> | void
  /** How many rows to show per page inside the dropdown. */
  pageSize?: number
  /** Debounce window for the search input, in ms. */
  debounceMs?: number
}

/**
 * Collapsed-by-default dropdown picker for adding a Contestant to a team.
 *
 * Server-side search + pagination:
 *  - Hits GET /api/users/search?q=&role=Contestant&exclude_team_id=&limit=&offset=
 *    so the page count stays accurate as the user base grows.
 *  - Search input is debounced (`debounceMs`, default 300ms) — typing does
 *    NOT fire one request per keystroke, and an AbortController cancels any
 *    in-flight request when the user types again or changes page.
 *  - Each row has explicit "+ Member" / "+ Reserve" actions, cap-disabled.
 *
 * Closes on Escape, outside click, or after a successful add (so the team
 * card refreshes underneath).
 */
export function MemberPicker({
  teamId,
  canAddMember,
  canAddReserve,
  onAdd,
  pageSize = 6,
  debounceMs = 300,
}: Props) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const [debouncedQuery, setDebouncedQuery] = useState("")
  const [page, setPage] = useState(0)
  const [results, setResults] = useState<User[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<number | null>(null)
  const rootRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Close on outside click / Escape.
  useEffect(() => {
    if (!open) return
    function onDocClick(e: MouseEvent) {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false)
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false)
    }
    document.addEventListener("mousedown", onDocClick)
    document.addEventListener("keydown", onKey)
    return () => {
      document.removeEventListener("mousedown", onDocClick)
      document.removeEventListener("keydown", onKey)
    }
  }, [open])

  // Reset search + autofocus when reopening.
  useEffect(() => {
    if (open) {
      setQuery("")
      setDebouncedQuery("")
      setPage(0)
      queueMicrotask(() => inputRef.current?.focus())
    }
  }, [open])

  // Debounce `query` -> `debouncedQuery`.  Also resets to the first page so a
  // new search starts fresh.
  useEffect(() => {
    if (query === debouncedQuery) return
    const t = setTimeout(() => {
      setDebouncedQuery(query)
      setPage(0)
    }, debounceMs)
    return () => clearTimeout(t)
  }, [query, debouncedQuery, debounceMs])

  // Fetch a page whenever the panel is open and (debounced query | page)
  // changes.  AbortController makes the previous request a no-op if the user
  // types again or clicks Next before it resolves.
  useEffect(() => {
    if (!open) return
    const ctrl = new AbortController()
    setLoading(true)
    setError(null)
    usersService
      .search(
        {
          q: debouncedQuery || undefined,
          role: "Contestant",
          exclude_team_id: teamId,
          limit: pageSize,
          offset: page * pageSize,
        },
        { signal: ctrl.signal },
      )
      .then((res) => {
        setResults(res.results)
        setTotal(res.total)
      })
      .catch((e: unknown) => {
        if (ctrl.signal.aborted) return
        if ((e as { name?: string })?.name === "AbortError") return
        setError(
          e instanceof Error ? e.message : "Failed to load contestants",
        )
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setLoading(false)
      })
    return () => ctrl.abort()
  }, [open, debouncedQuery, page, teamId, pageSize])

  async function add(c: User, role: "Member" | "Reserve") {
    setBusyId(c.id)
    try {
      await onAdd(c.id, role)
      setOpen(false)
    } finally {
      setBusyId(null)
    }
  }

  const triggerDisabled = !canAddMember && !canAddReserve
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const fromIdx = total === 0 ? 0 : page * pageSize + 1
  const toIdx = Math.min((page + 1) * pageSize, total)

  return (
    <div ref={rootRef} className="relative mt-2">
      <button
        type="button"
        className="btn btn-sm w-full text-left"
        onClick={() => setOpen((o) => !o)}
        disabled={triggerDisabled}
        title={
          triggerDisabled
            ? "Team is at member and reserve capacity"
            : "Add a contestant to this team"
        }
      >
        + Add member…
      </button>

      {open && (
        <div
          className="absolute z-20 left-0 right-0 mt-1 rounded-md border shadow-lg p-2 space-y-2"
          style={{
            background: "var(--c-panel-2)",
            borderColor: "var(--c-border)",
          }}
        >
          <input
            ref={inputRef}
            type="text"
            className="toolbar-input w-full"
            placeholder="Search contestants by name or Codeforces handle…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />

          {error ? (
            <div
              className="text-[12px] px-1 py-2"
              style={{ color: "var(--c-red)" }}
            >
              {error}
            </div>
          ) : loading && results.length === 0 ? (
            <div className="text-[12px] text-[color:var(--c-muted)] px-1 py-2">
              Searching…
            </div>
          ) : results.length === 0 ? (
            <div className="text-[12px] text-[color:var(--c-muted)] px-1 py-2">
              {debouncedQuery
                ? `No matches for "${debouncedQuery}".`
                : "No contestants available to add."}
            </div>
          ) : (
            <ul className="space-y-1">
              {results.map((c) => (
                <li
                  key={c.id}
                  className="flex items-center gap-2 text-[13px] px-1 py-[3px] rounded"
                  style={{ background: "var(--c-panel)" }}
                >
                  <div className="flex-1 min-w-0">
                    <div className="truncate">{c.name}</div>
                    <div
                      className="text-[11px] truncate"
                      style={{ color: "var(--c-muted)" }}
                    >
                      {c.handle ? `@${c.handle}` : "no handle"}
                      {c.institution ? ` · ${c.institution}` : ""}
                    </div>
                  </div>
                  <button
                    type="button"
                    className="btn btn-sm"
                    onClick={() => add(c, "Member")}
                    disabled={!canAddMember || busyId === c.id}
                    title={
                      canAddMember
                        ? "Add as Member"
                        : "Team already has the max members"
                    }
                  >
                    + Member
                  </button>
                  <button
                    type="button"
                    className="btn btn-sm"
                    onClick={() => add(c, "Reserve")}
                    disabled={!canAddReserve || busyId === c.id}
                    title={
                      canAddReserve
                        ? "Add as Reserve"
                        : "Team already has a reserve"
                    }
                  >
                    + Reserve
                  </button>
                </li>
              ))}
            </ul>
          )}

          {total > pageSize && (
            <div
              className="flex items-center justify-between text-[11px]"
              style={{ color: "var(--c-muted)" }}
            >
              <span>
                {loading
                  ? "Loading…"
                  : `Showing ${fromIdx}–${toIdx} of ${total}`}
              </span>
              <div className="flex gap-1">
                <button
                  type="button"
                  className="btn btn-sm"
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0 || loading}
                >
                  ‹ Prev
                </button>
                <button
                  type="button"
                  className="btn btn-sm"
                  onClick={() =>
                    setPage((p) => Math.min(totalPages - 1, p + 1))
                  }
                  disabled={page >= totalPages - 1 || loading}
                >
                  Next ›
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
