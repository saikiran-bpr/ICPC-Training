import { toast } from "sonner"
import { useFetch } from "@/hooks/useFetch"
import { contestsService } from "@/services/contests"
import { Tag } from "@/components/common/Tag"
import { Pill } from "@/components/common/Pill"
import { AITutorialCell } from "@/components/tutorials/AITutorialCell"
import { ApiError } from "@/lib/api"
import type { Problem } from "@/types/problem"

type Props = {
  contestId: number
  name: string
  canManage: boolean
  onAssignProblem: (p: Problem) => void
  onReload: () => void
  reloadKey: number
}

/**
 * Bank-context expand panel: shows all problems in a contest with per-row
 * Assign + Remove buttons.  Used in Contest Bank cards.
 */
export function ContestProblemsPanel({
  contestId,
  name,
  canManage,
  onAssignProblem,
  onReload,
  reloadKey,
}: Props) {
  const { data, isLoading, error } = useFetch(
    (signal) => contestsService.get(contestId, { signal }),
    [contestId, reloadKey],
  )

  async function removeProblem(p: Problem) {
    if (!confirm(`Remove "${p.name}" from this contest?`)) return
    try {
      await contestsService.removeProblem(contestId, p.id)
      toast.success("Removed from contest")
      onReload()
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Failed")
    }
  }

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
              <th>Platform</th>
              <th>Rating</th>
              <th>Topic</th>
              <th>Assigned to</th>
              <th>AI Tutorial</th>
              {canManage && <th>Actions</th>}
            </tr>
          </thead>
          <tbody>
            {data?.problems.length === 0 ? (
              <tr>
                <td
                  colSpan={canManage ? 8 : 7}
                  className="empty-cell"
                >
                  No problems in this contest yet.
                </td>
              </tr>
            ) : (
              data?.problems.map((p, idx) => (
                <tr key={p.id}>
                  <td>
                    <Tag>
                      {p.problem_index || String.fromCharCode(65 + idx)}
                    </Tag>
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
                  <td className="text-[12px]">{p.platform ?? "—"}</td>
                  <td>{p.rating ?? "—"}</td>
                  <td>{p.topic ?? "—"}</td>
                  <td>
                    <div className="flex flex-wrap gap-1 max-w-[200px]">
                      {p.assigned_teams.map((t) => (
                        <Tag key={`t-${t.id}`}>{t.name}</Tag>
                      ))}
                      {p.assigned_users.map((u) => (
                        <Pill key={`u-${u.id}`} value={u.role}>
                          {u.name}
                        </Pill>
                      ))}
                      {p.assigned_teams.length === 0 &&
                        p.assigned_users.length === 0 && (
                          <span className="text-[color:var(--c-muted)] text-[12px]">
                            —
                          </span>
                        )}
                    </div>
                  </td>
                  <td>
                    <AITutorialCell problemId={p.id} />
                  </td>
                  {canManage && (
                    <td>
                      <div className="flex gap-1">
                        <button
                          type="button"
                          className="btn btn-sm btn-primary"
                          onClick={() => onAssignProblem(p)}
                        >
                          Assign
                        </button>
                        <button
                          type="button"
                          className="btn btn-sm btn-danger"
                          onClick={() => removeProblem(p)}
                        >
                          Remove
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
              ))
            )}
          </tbody>
        </table>
      )}
    </div>
  )
}
