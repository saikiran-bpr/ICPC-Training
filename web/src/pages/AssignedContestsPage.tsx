import { useState } from "react"
import { toast } from "sonner"
import { useFetch } from "@/hooks/useFetch"
import { contestsService } from "@/services/contests"
import { useAuth } from "@/contexts/AuthContext"
import { ContestCard } from "@/components/contests/ContestCard"
import { Pill } from "@/components/common/Pill"
import { Tag } from "@/components/common/Tag"
import { AttemptModal } from "@/components/problems/AttemptModal"
import { ApiError } from "@/lib/api"
import type { AssignedContest, ContestWithProblems } from "@/types/contest"
import type { Problem } from "@/types/problem"

export function AssignedContestsPage() {
  const { role } = useAuth()
  const canGenerate = role === "Admin" || role === "Coach"

  const { data, isLoading, error } = useFetch(
    (signal) => contestsService.listAssigned({ signal }),
    [],
  )

  const [expanded, setExpanded] = useState<Set<number>>(new Set())
  const [attempt, setAttempt] = useState<Problem | null>(null)
  const [contestReloadTick, setContestReloadTick] = useState(0)

  function toggle(id: number) {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  async function generateTutorials(c: AssignedContest) {
    if (!confirm(`Start AI tutorial generation for every problem in "${c.name}"?`)) return
    try {
      const r = await contestsService.generateTutorials(c.id)
      toast.success(r.message ?? `Queued ${r.queued_count}`)
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Failed")
    }
  }

  return (
    <div className="h-full overflow-y-auto px-5 py-4 space-y-4">
      <div className="page-toolbar">
        <h1 className="page-h1">Assigned Contests</h1>
        <span className="text-[12px] text-[color:var(--c-muted)]">
          {isLoading ? "Loading…" : `${data?.length ?? 0} contests`}
        </span>
      </div>

      {error && <p className="text-[color:var(--c-red)]">{error}</p>}

      {!isLoading && data?.length === 0 && (
        <div className="text-center text-[color:var(--c-muted)] py-12">
          No contests assigned yet.
        </div>
      )}

      <div className="card-grid">
        {data?.map((c) => (
          <ContestCard
            key={c.id}
            contest={c}
            extraSummary={<ContestProgressSummary c={c} />}
            footer={
              <>
                <button
                  type="button"
                  className="btn btn-sm"
                  onClick={() => toggle(c.id)}
                >
                  {expanded.has(c.id) ? "Hide problems" : "Show problems"}
                </button>
                {canGenerate && (
                  <button
                    type="button"
                    className="btn btn-sm"
                    onClick={() => generateTutorials(c)}
                  >
                    Generate AI tutorials
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
              key={`exp-${c.id}-${contestReloadTick}`}
              contestId={c.id}
              name={c.name}
              onAttempt={(p) => setAttempt(p)}
            />
          ),
      )}

      <AttemptModal
        open={attempt !== null}
        onClose={() => setAttempt(null)}
        problem={attempt}
        onSaved={() => setContestReloadTick((n) => n + 1)}
      />
    </div>
  )
}

function ContestProgressSummary({ c }: { c: AssignedContest }) {
  const total = c.problem_count
  return (
    <div className="flex flex-wrap items-center gap-2 text-[12px]">
      <span className="text-[color:var(--c-muted)]">Solved</span>
      <Pill value="Done">
        {c.my_solved}/{total || "—"}
      </Pill>
      {c.during_count > 0 && <Pill value="Done">during {c.during_count}</Pill>}
      {c.upsolve_count > 0 && (
        <Pill value="Upsolve">upsolve {c.upsolve_count}</Pill>
      )}
    </div>
  )
}

function ContestProblemsPanel({
  contestId,
  name,
  onAttempt,
}: {
  contestId: number
  name: string
  onAttempt: (p: Problem) => void
}) {
  const { data, isLoading, error } = useFetch<ContestWithProblems>(
    (signal) => contestsService.get(contestId, { signal }),
    [contestId],
  )

  return (
    <div
      className="rounded-md border overflow-hidden"
      style={{ borderColor: "var(--c-border)", background: "var(--c-panel)" }}
    >
      <div
        className="px-4 py-2 text-[12px] font-medium uppercase tracking-wider"
        style={{
          color: "var(--c-muted)",
          background: "var(--c-panel-2)",
          borderBottom: "1px solid var(--c-border)",
        }}
      >
        {name} — problems
      </div>
      {isLoading ? (
        <div className="p-6 text-[color:var(--c-muted)]">Loading…</div>
      ) : error ? (
        <div className="p-6 text-[color:var(--c-red)]">{error}</div>
      ) : (
        <table className="data-table w-full">
          <thead>
            <tr>
              <th>#</th>
              <th>Name</th>
              <th>Rating</th>
              <th>Topic</th>
              <th>Status</th>
              <th>Phase</th>
              <th>Update</th>
            </tr>
          </thead>
          <tbody>
            {data?.problems.map((p, idx) => (
              <ContestProblemRow
                key={p.id}
                p={p}
                idx={idx}
                onAttempt={onAttempt}
              />
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

function ContestProblemRow({
  p,
  idx,
  onAttempt,
}: {
  p: Problem
  idx: number
  onAttempt: (p: Problem) => void
}) {
  const letter = String.fromCharCode(65 + idx)
  const a = p.my_attempt
  return (
    <tr>
      <td className="font-mono text-[12px]">
        <Tag>{letter}</Tag>
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
      <td>{p.rating ?? "—"}</td>
      <td>{p.topic ?? "—"}</td>
      <td>
        <Pill value={a?.attempt_status ?? "Todo"} />
      </td>
      <td>
        {a?.attempt_phase ? (
          <Pill value={a.attempt_phase === "During Contest" ? "Done" : "Upsolve"}>
            {a.attempt_phase}
          </Pill>
        ) : (
          <span className="text-[color:var(--c-muted)]">—</span>
        )}
      </td>
      <td>
        <button
          type="button"
          className="btn btn-sm"
          onClick={() => onAttempt(p)}
        >
          Update
        </button>
      </td>
    </tr>
  )
}
