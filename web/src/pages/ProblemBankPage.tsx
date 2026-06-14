import { useEffect, useMemo, useState } from "react"
import { toast } from "sonner"
import { useFetch } from "@/hooks/useFetch"
import { useDebouncedValue } from "@/hooks/useDebouncedValue"
import { useAuth } from "@/contexts/AuthContext"
import { bankService } from "@/services/bank"
import { metaService } from "@/services/meta"
import { problemsService } from "@/services/problems"
import { Pill } from "@/components/common/Pill"
import { Tag } from "@/components/common/Tag"
import { ProblemModal } from "@/components/problems/ProblemModal"
import { AssignModal, type AssignTarget } from "@/components/bank/AssignModal"
import { MultiFilter, asArr } from "@/components/common/MultiFilter"
import { ApiError } from "@/lib/api"
import type { ProblemFilters, Problem } from "@/types/problem"

const DEFAULT_FILTERS: ProblemFilters = {
  sort: "rating",
  order: "asc",
}

const PAGE_SIZE = 100
const SEARCH_DEBOUNCE_MS = 600

export function ProblemBankPage() {
  const { user, role } = useAuth()
  const [filters, setFilters] = useState<ProblemFilters>(DEFAULT_FILTERS)
  const [searchInput, setSearchInput] = useState("")
  const [page, setPage] = useState(0)
  const [reloadTick, setReloadTick] = useState(0)
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<Problem | null>(null)
  const [assignTarget, setAssignTarget] = useState<AssignTarget | null>(null)
  // Ids of problems ticked for batch-assign.  Persists across pages/filters so
  // a coach can build a selection while browsing; cleared after a successful
  // assign or via the "Clear" button.
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())

  const meta = useFetch((signal) => metaService.get({ signal }), [])
  const debouncedSearch = useDebouncedValue(searchInput, SEARCH_DEBOUNCE_MS)

  // A settled search term starts a fresh result set from page 1.
  useEffect(() => {
    setPage(0)
  }, [debouncedSearch])

  const effective = useMemo<ProblemFilters>(
    () => ({
      ...filters,
      q: debouncedSearch.trim() || undefined,
      limit: PAGE_SIZE,
      offset: page * PAGE_SIZE,
    }),
    [filters, debouncedSearch, page],
  )

  const list = useFetch(
    (signal) => bankService.listProblems(effective, { signal }),
    [JSON.stringify(effective), reloadTick],
  )

  const refresh = () => setReloadTick((n) => n + 1)

  const pageRows = list.data?.results ?? []
  const pageIds = pageRows.map((p) => p.id)
  const allPageSelected =
    pageIds.length > 0 && pageIds.every((id) => selectedIds.has(id))
  const somePageSelected = pageIds.some((id) => selectedIds.has(id))

  function toggleOne(id: number, checked: boolean) {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (checked) next.add(id)
      else next.delete(id)
      return next
    })
  }

  function togglePage(checked: boolean) {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      for (const id of pageIds) {
        if (checked) next.add(id)
        else next.delete(id)
      }
      return next
    })
  }

  function clearSelection() {
    setSelectedIds(new Set())
  }

  function set<K extends keyof ProblemFilters>(
    k: K,
    v: ProblemFilters[K] | "",
  ) {
    setPage(0)
    setFilters((f) => {
      const next = { ...f }
      if (v === "" || v == null || (Array.isArray(v) && v.length === 0))
        delete next[k]
      else next[k] = v as ProblemFilters[K]
      return next
    })
  }

  async function remove(p: Problem) {
    if (!confirm(`Delete problem "${p.name}"?`)) return
    try {
      await problemsService.remove(p.id)
      toast.success("Problem deleted")
      refresh()
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Failed")
    }
  }

  return (
    <div className="h-full overflow-y-auto px-5 py-4 space-y-4">
      <div className="page-toolbar">
        <h1 className="page-h1">Problem Bank</h1>
        <span className="text-[12px] text-[color:var(--c-muted)]">
          {list.isLoading ? "Loading…" : `${list.data?.total ?? 0} problems`}
        </span>

        <div className="ml-auto">
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => {
              setEditing(null)
              setModalOpen(true)
            }}
          >
            + New Problem
          </button>
        </div>
      </div>

      {selectedIds.size > 0 && (
        <div className="flex justify-end">
          <div
            className="inline-flex items-center gap-2 rounded-md border px-3 py-1.5"
            style={{
              background: "var(--c-panel)",
              borderColor: "var(--c-accent)",
            }}
          >
            <span className="text-[12px] font-medium whitespace-nowrap">
              {selectedIds.size} problem{selectedIds.size === 1 ? "" : "s"} selected
            </span>
            <button
              type="button"
              className="btn btn-sm btn-primary"
              onClick={() =>
                setAssignTarget({
                  kind: "problems",
                  ids: [...selectedIds],
                  label: `${selectedIds.size} problem${
                    selectedIds.size === 1 ? "" : "s"
                  } selected`,
                })
              }
            >
              Assign selected
            </button>
            <button type="button" className="btn btn-sm" onClick={clearSelection}>
              Clear
            </button>
          </div>
        </div>
      )}

      <div className="flex flex-wrap items-end gap-2">
        <div className="flex-1 min-w-[340px]">
          <input
            type="text"
            className="toolbar-input w-full"
            style={{ padding: "11px 14px", fontSize: "15px" }}
            placeholder="Search by name, tag, key idea..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
          />
        </div>
        <MultiFilter
          label="Platform"
          selected={asArr(filters.platform)}
          options={meta.data?.platforms}
          onChange={(v) => set("platform", v)}
        />
        <MultiFilter
          label="Topic"
          selected={asArr(filters.topic)}
          options={meta.data?.topics}
          onChange={(v) => set("topic", v)}
        />
        <MultiFilter
          label="Difficulty"
          selected={asArr(filters.difficulty)}
          options={meta.data?.difficulties}
          onChange={(v) => set("difficulty", v)}
        />
        <MultiFilter
          label="Importance"
          selected={asArr(filters.importance)}
          options={meta.data?.importance}
          onChange={(v) => set("importance", v)}
        />
        <div className="flex flex-col">
          <label className="filter-label">Sort by</label>
          <select
            className="filter-control min-w-[150px]"
            value={`${filters.sort ?? "rating"}:${filters.order ?? "asc"}`}
            onChange={(e) => {
              const [s, o] = e.target.value.split(":")
              setPage(0)
              setFilters((f) => ({ ...f, sort: s, order: o as "asc" | "desc" }))
            }}
          >
            <option value="rating:asc">Rating ↑ (low→high)</option>
            <option value="rating:desc">Rating ↓ (high→low)</option>
            <option value="date_added:desc">Newest</option>
            <option value="name:asc">Name (A→Z)</option>
          </select>
        </div>
        <div className="flex flex-col">
          <label className="filter-label">Rating</label>
          <div className="flex gap-1">
            <input
              type="number"
              placeholder="Min"
              className="filter-control w-[70px]"
              value={filters.rating_min ?? ""}
              onChange={(e) =>
                set("rating_min", e.target.value === "" ? "" : Number(e.target.value))
              }
            />
            <input
              type="number"
              placeholder="Max"
              className="filter-control w-[70px]"
              value={filters.rating_max ?? ""}
              onChange={(e) =>
                set("rating_max", e.target.value === "" ? "" : Number(e.target.value))
              }
            />
          </div>
        </div>
        <button
          type="button"
          className="btn"
          onClick={() => {
            setPage(0)
            setFilters(DEFAULT_FILTERS)
            setSearchInput("")
          }}
        >
          Clear
        </button>
      </div>

      <div
        className="rounded-md border overflow-x-auto"
        style={{ background: "var(--c-panel)", borderColor: "var(--c-border)" }}
      >
        <table className="data-table w-full">
          <thead>
            <tr>
              <th style={{ width: 36 }}>
                <input
                  type="checkbox"
                  className="h-4 w-4 cursor-pointer align-middle accent-[color:var(--c-accent)]"
                  aria-label="Select all problems on this page"
                  checked={allPageSelected}
                  ref={(el) => {
                    if (el)
                      el.indeterminate = somePageSelected && !allPageSelected
                  }}
                  onChange={(e) => togglePage(e.target.checked)}
                  disabled={pageIds.length === 0}
                />
              </th>
              <th>Name</th>
              <th>Platform / Contest</th>
              <th>Rating</th>
              <th>Difficulty</th>
              <th>Topic</th>
              <th>Tags</th>
              <th>Importance</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {list.isLoading ? (
              <tr>
                <td colSpan={9} className="empty-cell">Loading…</td>
              </tr>
            ) : list.data?.results.length === 0 ? (
              <tr>
                <td colSpan={9} className="empty-cell">
                  Problem bank is empty.
                </td>
              </tr>
            ) : (
              list.data?.results.map((p) => {
                // Admin manages every problem; Coach only their own creations.
                // Same predicate the backend enforces (can_manage_problem):
                // ownership check is authoritative server-side; this just
                // hides UI a Coach couldn't successfully use anyway.
                const canManage =
                  role === "Admin" ||
                  (role === "Coach" && p.created_by === user?.id)
                return (
                  <BankRow
                    key={p.id}
                    p={p}
                    canManage={canManage}
                    selected={selectedIds.has(p.id)}
                    onToggleSelect={(checked) => toggleOne(p.id, checked)}
                    onAssign={() =>
                      setAssignTarget({ kind: "problem", id: p.id, label: p.name })
                    }
                    onEdit={() => {
                      setEditing(p)
                      setModalOpen(true)
                    }}
                    onDelete={() => remove(p)}
                  />
                )
              })
            )}
          </tbody>
        </table>
      </div>

      {!list.isLoading && (list.data?.total ?? 0) > PAGE_SIZE && (
        <div className="flex items-center justify-between text-[12px] text-[color:var(--c-muted)]">
          <span>
            Showing {page * PAGE_SIZE + 1}–
            {Math.min((page + 1) * PAGE_SIZE, list.data?.total ?? 0)} of{" "}
            {list.data?.total ?? 0}
          </span>
          <div className="flex gap-1">
            <button
              type="button"
              className="btn btn-sm"
              disabled={page === 0}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
            >
              ‹ Prev
            </button>
            <button
              type="button"
              className="btn btn-sm"
              disabled={(page + 1) * PAGE_SIZE >= (list.data?.total ?? 0)}
              onClick={() => setPage((p) => p + 1)}
            >
              Next ›
            </button>
          </div>
        </div>
      )}

      <ProblemModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        initial={editing}
        onSaved={refresh}
      />
      <AssignModal
        open={assignTarget !== null}
        onClose={() => setAssignTarget(null)}
        target={assignTarget}
        onAssigned={() => {
          // A batch assign consumes the current selection; clear it so the
          // action bar collapses and stale ids don't linger.
          if (assignTarget?.kind === "problems") clearSelection()
          refresh()
        }}
      />
    </div>
  )
}

function BankRow({
  p,
  canManage,
  selected,
  onToggleSelect,
  onAssign,
  onEdit,
  onDelete,
}: {
  p: Problem
  canManage: boolean
  selected: boolean
  onToggleSelect: (checked: boolean) => void
  onAssign: () => void
  onEdit: () => void
  onDelete: () => void
}) {
  return (
    <tr style={selected ? { background: "var(--c-accent-soft, rgba(59,130,246,0.08))" } : undefined}>
      <td>
        <input
          type="checkbox"
          className="h-4 w-4 cursor-pointer align-middle accent-[color:var(--c-accent)]"
          aria-label={`Select ${p.name}`}
          checked={selected}
          onChange={(e) => onToggleSelect(e.target.checked)}
        />
      </td>
      <td>
        <a
          href={p.url}
          target="_blank"
          rel="noreferrer"
          className="text-[color:var(--c-accent)] hover:underline"
        >
          {p.name}
        </a>
      </td>
      <td>
        <div className="flex flex-col text-[12px]">
          <span>{p.platform ?? "—"}</span>
        </div>
      </td>
      <td>{p.rating ?? "—"}</td>
      <td><Pill value={p.difficulty} /></td>
      <td>{p.topic ?? "—"}</td>
      <td>
        <div className="flex flex-wrap max-w-[200px]">
          {p.tags.slice(0, 3).map((t) => (
            <Tag key={t}>{t}</Tag>
          ))}
          {p.tags.length > 3 && (
            <span className="text-[11px] text-[color:var(--c-muted)] ml-1">
              +{p.tags.length - 3}
            </span>
          )}
        </div>
      </td>
      <td><Pill value={p.importance} /></td>
      <td>
        <div className="flex gap-1">
          <button type="button" className="btn btn-sm btn-primary" onClick={onAssign}>
            Assign
          </button>
          {canManage && (
            <>
              <button type="button" className="btn btn-sm" onClick={onEdit}>
                Edit
              </button>
              <button type="button" className="btn btn-sm btn-danger" onClick={onDelete}>
                Delete
              </button>
            </>
          )}
        </div>
      </td>
    </tr>
  )
}
