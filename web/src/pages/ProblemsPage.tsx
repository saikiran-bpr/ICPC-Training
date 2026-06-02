import { useMemo, useState } from "react"
import { toast } from "sonner"
import { useFetch } from "@/hooks/useFetch"
import { metaService } from "@/services/meta"
import { problemsService } from "@/services/problems"
import { useAuth } from "@/contexts/AuthContext"
import { ProblemFiltersSidebar } from "@/components/problems/ProblemFiltersSidebar"
import { ProblemsTable } from "@/components/problems/ProblemsTable"
import { AttemptModal } from "@/components/problems/AttemptModal"
import type { Problem, ProblemFilters } from "@/types/problem"

const DEFAULT_FILTERS: ProblemFilters = {
  sort: "date_added",
  order: "desc",
}

export function ProblemsPage() {
  const { role } = useAuth()
  const [filters, setFilters] = useState<ProblemFilters>(DEFAULT_FILTERS)
  const [searchInput, setSearchInput] = useState("")
  const [reloadTick, setReloadTick] = useState(0)
  const [attemptProblem, setAttemptProblem] = useState<Problem | null>(null)

  const effective = useMemo<ProblemFilters>(
    () => ({ ...filters, q: filters.q || undefined }),
    [filters],
  )

  const meta = useFetch((signal) => metaService.get({ signal }), [])

  const list = useFetch(
    (signal) => problemsService.list(effective, { signal }),
    [JSON.stringify(effective), reloadTick],
  )

  function applySearch() {
    setFilters((f) => ({ ...f, q: searchInput.trim() || undefined }))
  }

  function clearAll() {
    setFilters(DEFAULT_FILTERS)
    setSearchInput("")
  }

  function exportXlsx() {
    // Hit the API origin (same backend as fetches); falls back to same-origin
    // in dev where Vite proxies /api.
    const base = import.meta.env.VITE_API_BASE_URL || window.location.origin
    const url = new URL("/api/export/xlsx", base)
    for (const [k, v] of Object.entries(effective)) {
      if (v === undefined || v === null || v === "") continue
      if (Array.isArray(v)) {
        for (const item of v) {
          if (item !== undefined && item !== null && item !== "")
            url.searchParams.append(k, String(item))
        }
        continue
      }
      url.searchParams.append(k, String(v))
    }
    window.open(url.toString(), "_blank")
    toast.success("Export started")
  }

  return (
    <div className="flex h-full min-h-0">
      <ProblemFiltersSidebar
        meta={meta.data}
        filters={filters}
        onChange={setFilters}
        onClear={clearAll}
        role={role}
      />

      <div className="flex-1 min-w-0 overflow-y-auto px-5 py-4 space-y-4">
        <div className="flex gap-3">
          <input
            type="text"
            className="toolbar-input"
            placeholder="Search by name, tag, key idea..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") applySearch()
            }}
            onBlur={applySearch}
          />
          <button
            type="button"
            onClick={exportXlsx}
            className="btn"
          >
            Export Excel
          </button>
        </div>

        <div className="text-[12px] text-[color:var(--c-muted)]">
          {list.isLoading
            ? "Loading…"
            : list.error
              ? list.error
              : `${list.data?.total ?? 0} problems`}
        </div>

        {list.isLoading ? (
          <div
            className="rounded-md border p-10 text-center text-[color:var(--c-muted)]"
            style={{ borderColor: "var(--c-border)", background: "var(--c-panel)" }}
          >
            Loading problems…
          </div>
        ) : (
          <ProblemsTable
            problems={list.data?.results ?? []}
            role={role ?? "Contestant"}
            onAttempt={(p) => setAttemptProblem(p)}
          />
        )}
      </div>

      <AttemptModal
        open={attemptProblem !== null}
        onClose={() => setAttemptProblem(null)}
        problem={attemptProblem}
        onSaved={() => setReloadTick((n) => n + 1)}
      />
    </div>
  )
}
