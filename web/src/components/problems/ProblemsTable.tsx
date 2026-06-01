import { Pill } from "@/components/common/Pill"
import { Tag } from "@/components/common/Tag"
import { AITutorialCell } from "@/components/tutorials/AITutorialCell"
import type { Problem } from "@/types/problem"
import type { UserRole } from "@/types/user"

type Props = {
  problems: Problem[]
  role: UserRole
  onAttempt?: (p: Problem) => void
}

/**
 * Mirrors the contestant vs coach/admin tables from static/index.html.
 */
export function ProblemsTable({ problems, role, onAttempt }: Props) {
  const isCoach = role === "Coach" || role === "Admin"

  return (
    <div
      className="rounded-md border overflow-x-auto"
      style={{ background: "var(--c-panel)", borderColor: "var(--c-border)" }}
    >
      <table className="data-table w-full">
        <thead>
          <tr>
            <th>Name</th>
            <th>Platform / Contest</th>
            <th>Rating</th>
            <th>Difficulty</th>
            <th>Topic</th>
            <th>Tags</th>
            <th>Importance</th>
            {isCoach ? (
              <>
                <th>Solved</th>
                <th>AI Tutorial</th>
              </>
            ) : (
              <>
                <th>Status</th>
                <th>Problem Faced</th>
                <th>Time</th>
                <th>Notes / Learning</th>
                <th>Update</th>
              </>
            )}
          </tr>
        </thead>
        <tbody>
          {problems.length === 0 ? (
            <tr>
              <td colSpan={isCoach ? 9 : 12} className="empty-cell">
                No problems yet.
              </td>
            </tr>
          ) : (
            problems.map((p) =>
              isCoach ? (
                <CoachRow key={p.id} p={p} />
              ) : (
                <ContestantRow key={p.id} p={p} onAttempt={onAttempt} />
              ),
            )
          )}
        </tbody>
      </table>
    </div>
  )
}

function NameCell({ p }: { p: Problem }) {
  return (
    <div className="flex flex-col gap-0.5">
      <a
        href={p.url}
        target="_blank"
        rel="noreferrer"
        className="text-[color:var(--c-accent)] hover:underline truncate max-w-[280px]"
      >
        {p.name || p.url}
      </a>
      {p.problem_index && <Tag>{p.problem_index}</Tag>}
    </div>
  )
}

function PlatformCell({ p }: { p: Problem }) {
  return (
    <div className="flex flex-col text-[12px]">
      <span>{p.platform ?? "—"}</span>
      {p.contest_name && (
        <span className="text-[color:var(--c-muted)] truncate max-w-[240px]">
          {p.contest_name}
        </span>
      )}
    </div>
  )
}

function TagsCell({ p }: { p: Problem }) {
  if (!p.tags?.length) return <span className="text-[color:var(--c-muted)]">—</span>
  return (
    <div className="flex flex-wrap max-w-[200px]">
      {p.tags.slice(0, 4).map((t) => (
        <Tag key={t}>{t}</Tag>
      ))}
      {p.tags.length > 4 && (
        <span className="text-[11px] text-[color:var(--c-muted)] ml-1">
          +{p.tags.length - 4}
        </span>
      )}
    </div>
  )
}

function ContestantRow({
  p,
  onAttempt,
}: {
  p: Problem
  onAttempt?: (p: Problem) => void
}) {
  const a = p.my_attempt
  return (
    <tr>
      <td><NameCell p={p} /></td>
      <td><PlatformCell p={p} /></td>
      <td>{p.rating ?? "—"}</td>
      <td><Pill value={p.difficulty} /></td>
      <td>{p.topic ?? "—"}</td>
      <td><TagsCell p={p} /></td>
      <td><Pill value={p.importance} /></td>
      <td><Pill value={a?.attempt_status ?? "Todo"} /></td>
      <td>
        {a?.problem_faced ? (
          <span className="text-[12px]">{a.problem_faced}</span>
        ) : (
          <span className="text-[color:var(--c-muted)]">—</span>
        )}
      </td>
      <td>{a?.time_spent_min != null ? `${a.time_spent_min}m` : "—"}</td>
      <td>
        {a?.notes ? (
          <span
            className="text-[12px] line-clamp-2 max-w-[220px] inline-block"
            title={a.notes}
          >
            {a.notes}
          </span>
        ) : (
          <span className="text-[color:var(--c-muted)]">—</span>
        )}
      </td>
      <td>
        <button
          type="button"
          className="btn btn-sm"
          onClick={() => onAttempt?.(p)}
        >
          Update
        </button>
      </td>
    </tr>
  )
}

function CoachRow({ p }: { p: Problem }) {
  const totals = p.team_summary.reduce(
    (acc, t) => {
      acc.solved += t.primary_solved
      acc.total += t.primary_total
      return acc
    },
    { solved: 0, total: 0 },
  )

  return (
    <tr>
      <td><NameCell p={p} /></td>
      <td><PlatformCell p={p} /></td>
      <td>{p.rating ?? "—"}</td>
      <td><Pill value={p.difficulty} /></td>
      <td>{p.topic ?? "—"}</td>
      <td><TagsCell p={p} /></td>
      <td><Pill value={p.importance} /></td>
      <td>
        <span className="text-[12px]">
          {totals.solved} / {totals.total || "—"}
        </span>
      </td>
      <td>
        <AITutorialCell problemId={p.id} />
      </td>
    </tr>
  )
}
