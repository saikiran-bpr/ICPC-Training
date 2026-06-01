import { useState } from "react"
import { Pill } from "@/components/common/Pill"
import { Tag } from "@/components/common/Tag"
import { AITutorialCell } from "@/components/tutorials/AITutorialCell"
import type { Problem, TeamSummary, TeamMemberAttempt } from "@/types/problem"
import type { UserRole } from "@/types/user"

type Props = {
  problems: Problem[]
  role: UserRole
  onAttempt?: (p: Problem) => void
}

/**
 * Mirrors the contestant vs coach/admin tables from static/index.html.
 *  - Contestant: per-row attempt fields + who assigned the problem.
 *  - Coach/Admin: aggregated solved/total, click a row to expand a per-team /
 *    per-member status breakdown.
 */
export function ProblemsTable({ problems, role, onAttempt }: Props) {
  const isCoach = role === "Coach" || role === "Admin"
  const colCount = isCoach ? 9 : 13

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
                <th>Assigned By</th>
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
              <td colSpan={colCount} className="empty-cell">
                No problems yet.
              </td>
            </tr>
          ) : (
            problems.map((p) =>
              isCoach ? (
                <CoachRow key={p.id} p={p} colCount={colCount} />
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
        onClick={(e) => e.stopPropagation()}
        className="text-[color:var(--c-accent)] hover:underline truncate max-w-[280px]"
      >
        {p.name || p.url}
      </a>
    </div>
  )
}

function PlatformCell({ p }: { p: Problem }) {
  return (
    <div className="flex flex-col text-[12px]">
      <span>{p.platform ?? "—"}</span>
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
      <td>
        {p.assigned_by ? (
          <div className="flex flex-col text-[12px]">
            <span>{p.assigned_by.name}</span>
            {p.assigned_via && (
              <span className="text-[11px] text-[color:var(--c-muted)]">
                {p.assigned_via === "Direct" ? "Directly assigned" : `via ${p.assigned_via}`}
              </span>
            )}
          </div>
        ) : (
          <span className="text-[color:var(--c-muted)]">—</span>
        )}
      </td>
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

function solvedPillClass(solved: number, total: number): string {
  if (total > 0 && solved >= total) return "pill-Done"
  if (solved > 0) return "pill-In-Progress"
  return "pill-Todo"
}

function CoachRow({ p, colCount }: { p: Problem; colCount: number }) {
  const [expanded, setExpanded] = useState(false)
  const totals = p.team_summary.reduce(
    (acc, t) => {
      acc.solved += t.solved
      acc.total += t.total
      return acc
    },
    { solved: 0, total: 0 },
  )

  return (
    <>
      <tr className="cursor-pointer" onClick={() => setExpanded((v) => !v)}>
        <td><NameCell p={p} /></td>
        <td><PlatformCell p={p} /></td>
        <td>{p.rating ?? "—"}</td>
        <td><Pill value={p.difficulty} /></td>
        <td>{p.topic ?? "—"}</td>
        <td><TagsCell p={p} /></td>
        <td><Pill value={p.importance} /></td>
        <td>
          <div className="flex items-center gap-1.5">
            <span className="text-[color:var(--c-muted)] text-[11px]">
              {expanded ? "▾" : "▸"}
            </span>
            <span className="text-[12px]">
              {totals.solved} / {totals.total || "—"}
            </span>
          </div>
        </td>
        <td onClick={(e) => e.stopPropagation()}>
          <AITutorialCell problemId={p.id} />
        </td>
      </tr>
      {expanded && (
        <tr className="expanded-row">
          <td colSpan={colCount} style={{ background: "var(--c-panel-2)", padding: "14px 16px" }}>
            {p.team_summary.length ? (
              p.team_summary.map((t) => (
                <TeamBreakdown key={`${t.team_id ?? "direct"}-${t.team_name}`} team={t} />
              ))
            ) : (
              <div className="text-[color:var(--c-muted)] text-[13px]">No assignments yet.</div>
            )}
          </td>
        </tr>
      )}
    </>
  )
}

function TeamBreakdown({ team }: { team: TeamSummary }) {
  return (
    <div className="mb-4 last:mb-0">
      <div className="flex items-center gap-2.5 mb-1.5">
        <strong className="text-[13px]">{team.team_name}</strong>
        <span className={`pill ${solvedPillClass(team.solved, team.total)}`}>
          {team.solved}/{team.total}
        </span>
        {team.reserve_total > 0 && (
          <span className="text-[11px] text-[color:var(--c-muted)]">
            Reserve {team.reserve_solved}/{team.reserve_total}
          </span>
        )}
      </div>
      <table
        className="data-table w-full"
        style={{ background: "var(--c-panel)" }}
      >
        <thead>
          <tr>
            <th>Member</th>
            <th>Status</th>
            <th>Phase</th>
            <th>Problem Faced</th>
            <th>Time</th>
            <th>Notes / Learning</th>
          </tr>
        </thead>
        <tbody>
          {team.members.length === 0 ? (
            <tr>
              <td colSpan={6} className="text-[color:var(--c-muted)] text-[12px]">
                No members
              </td>
            </tr>
          ) : (
            team.members.map((m) => <MemberRow key={m.id} m={m} />)
          )}
        </tbody>
      </table>
    </div>
  )
}

function MemberRow({ m }: { m: TeamMemberAttempt }) {
  return (
    <tr>
      <td>
        {m.name}
        {m.role_in_team === "Reserve" && <Tag>Reserve</Tag>}
      </td>
      <td>
        {m.attempt_status ? (
          <Pill value={m.attempt_status} />
        ) : (
          <span className="text-[color:var(--c-muted)]">—</span>
        )}
      </td>
      <td>
        {m.attempt_phase ? (
          <span className="text-[12px]">{m.attempt_phase}</span>
        ) : (
          <span className="text-[color:var(--c-muted)]">—</span>
        )}
      </td>
      <td className="text-[12px] text-[color:var(--c-muted)]">{m.problem_faced || "—"}</td>
      <td>{m.time_spent_min != null ? `${m.time_spent_min}m` : "—"}</td>
      <td>
        {m.notes ? (
          <span
            className="text-[12px] line-clamp-2 max-w-[260px] inline-block"
            title={m.notes}
          >
            {m.notes}
          </span>
        ) : (
          <span className="text-[color:var(--c-muted)]">—</span>
        )}
      </td>
    </tr>
  )
}
