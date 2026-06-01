import { useState } from "react"
import { toast } from "sonner"
import { useFetch } from "@/hooks/useFetch"
import { contestsService } from "@/services/contests"
import { useAuth } from "@/contexts/AuthContext"
import { ContestCard } from "@/components/contests/ContestCard"
import { ContestModal } from "@/components/contests/ContestModal"
import { ContestProblemsPanel } from "@/components/contests/ContestProblemsPanel"
import { AssignModal, type AssignTarget } from "@/components/bank/AssignModal"
import { Pill } from "@/components/common/Pill"
import { ApiError } from "@/lib/api"
import type { ContestSummary } from "@/types/contest"

export function ContestBankPage() {
  const { role } = useAuth()
  const canManage = role === "Admin" || role === "Coach"
  const canDelete = role === "Admin"

  const [searchInput, setSearchInput] = useState("")
  const [query, setQuery] = useState<string | undefined>(undefined)
  const [reloadTick, setReloadTick] = useState(0)
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<ContestSummary | null>(null)
  const [assignTarget, setAssignTarget] = useState<AssignTarget | null>(null)
  const [expanded, setExpanded] = useState<Set<number>>(new Set())
  const [panelReloadTick, setPanelReloadTick] = useState(0)

  function toggle(id: number) {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const { data, isLoading, error } = useFetch(
    (signal) => contestsService.listBank({ q: query }, { signal }),
    [query, reloadTick],
  )

  const refresh = () => setReloadTick((n) => n + 1)

  async function remove(c: ContestSummary) {
    if (!confirm(`Delete contest "${c.name}"?`)) return
    try {
      await contestsService.remove(c.id)
      toast.success("Contest deleted")
      refresh()
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Failed")
    }
  }

  async function generateTutorials(c: ContestSummary) {
    if (!confirm(`Start AI tutorial generation for every problem in "${c.name}"?`)) return
    try {
      const r = await contestsService.generateTutorials(c.id)
      toast.success(r.message ?? `Queued ${r.queued_count} problems`)
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Failed")
    }
  }

  return (
    <div className="h-full overflow-y-auto px-5 py-4 space-y-4">
      <div className="page-toolbar">
        <h1 className="page-h1">Contest Bank</h1>
        <span className="text-[12px] text-[color:var(--c-muted)]">
          {isLoading ? "Loading…" : `${data?.length ?? 0} contests`}
        </span>
        <div className="ml-auto flex gap-2">
          <input
            type="text"
            className="toolbar-input w-[260px]"
            placeholder="Search contests…"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter")
                setQuery(searchInput.trim() || undefined)
            }}
            onBlur={() => setQuery(searchInput.trim() || undefined)}
          />
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => {
              setEditing(null)
              setModalOpen(true)
            }}
          >
            + New Contest
          </button>
        </div>
      </div>

      {error && <p className="text-[color:var(--c-red)]">{error}</p>}
      {!isLoading && data?.length === 0 && (
        <div className="text-center text-[color:var(--c-muted)] py-12">
          Contest bank is empty. Once you populate it (via scraping or manual
          import), contests will appear here.
        </div>
      )}

      <div className="card-grid">
        {data?.map((c) => (
          <ContestCard
            key={c.id}
            contest={c}
            extraSummary={
              <div className="flex flex-wrap items-center gap-2 text-[12px]">
                <Pill value={c.bank_problem_count > 0 ? "Todo" : "Done"}>
                  {c.problem_count} problem{c.problem_count === 1 ? "" : "s"}
                </Pill>
              </div>
            }
            footer={
              <>
                <button
                  type="button"
                  className="btn btn-sm"
                  onClick={() => toggle(c.id)}
                >
                  {expanded.has(c.id) ? "Hide problems" : "Open"}
                </button>
                <button
                  type="button"
                  className="btn btn-sm"
                  onClick={() => {
                    setEditing(c)
                    setModalOpen(true)
                  }}
                >
                  ✎ Edit
                </button>
                {c.url && (
                  <a
                    href={c.url}
                    target="_blank"
                    rel="noreferrer"
                    className="btn btn-sm"
                  >
                    Go to contest ↗
                  </a>
                )}
                {c.problem_count > 0 && (
                  <button
                    type="button"
                    className="btn btn-sm btn-primary"
                    onClick={() =>
                      setAssignTarget({ kind: "contest", id: c.id, label: c.name })
                    }
                  >
                    Assign contest
                  </button>
                )}
                <button
                  type="button"
                  className="btn btn-sm"
                  onClick={() => generateTutorials(c)}
                >
                  Generate AI tutorials
                </button>
                {canDelete && (
                  <button
                    type="button"
                    className="btn btn-sm btn-danger ml-auto"
                    onClick={() => remove(c)}
                  >
                    Delete
                  </button>
                )}
              </>
            }
          />
        ))}
      </div>

      {data?.map(
        (c) =>
          expanded.has(c.id) && (
            <ContestProblemsPanel
              key={`exp-${c.id}`}
              contestId={c.id}
              name={c.name}
              canManage={canManage}
              reloadKey={panelReloadTick}
              onAssignProblem={(p) =>
                setAssignTarget({ kind: "problem", id: p.id, label: p.name })
              }
              onReload={() => setPanelReloadTick((n) => n + 1)}
            />
          ),
      )}

      <ContestModal
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
          refresh()
          setPanelReloadTick((n) => n + 1)
        }}
      />
    </div>
  )
}
