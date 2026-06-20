import { useState } from "react"
import { toast } from "sonner"
import { useFetch } from "@/hooks/useFetch"
import { contestsService } from "@/services/contests"
import { useAuth } from "@/contexts/AuthContext"
import { ContestCard } from "@/components/contests/ContestCard"
import { ContestModal } from "@/components/contests/ContestModal"
import { AssignModal, type AssignTarget } from "@/components/bank/AssignModal"
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
            showAssignedTo={false}
            footer={
              <>
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
                {canManage && (
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
        onAssigned={refresh}
      />
    </div>
  )
}
