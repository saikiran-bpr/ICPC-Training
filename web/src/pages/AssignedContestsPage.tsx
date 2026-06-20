import { useMemo, useState } from "react"
import { useFetch } from "@/hooks/useFetch"
import { contestsService } from "@/services/contests"
import { metaService } from "@/services/meta"
import { useAuth } from "@/contexts/AuthContext"
import { ReflectionModal } from "@/components/contests/ReflectionModal"
import {
  ContestFiltersSidebar,
  type ContestFilters,
} from "@/components/contests/ContestFiltersSidebar"
import { Pill } from "@/components/common/Pill"
import { Tag } from "@/components/common/Tag"
import type {
  AssignedContest,
  ContestMemberEntry,
  ContestTeamBreakdown,
  MemberStatus,
} from "@/types/contest"

const STATUS_PILL: Record<MemberStatus, string> = {
  "Not started": "Todo",
  Attempted: "In Progress",
  Completed: "Done",
}

function formatDuration(minutes: number | null): string {
  if (minutes == null) return "—"
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  if (h && m) return `${h}h ${m}m`
  if (h) return `${h}h`
  return `${m}m`
}

function earliestDue(c: AssignedContest): string | null {
  const dates = (c.assigned_teams ?? [])
    .map((t) => t.due_date)
    .filter((d): d is string => !!d)
  if (dates.length === 0) return null
  return dates.sort()[0]
}

export function AssignedContestsPage() {
  const { user, role } = useAuth()
  const isStaff = role === "Admin" || role === "Coach"
  const colCount = isStaff ? 7 : 9

  const [searchInput, setSearchInput] = useState("")
  const [query, setQuery] = useState("")
  const [filters, setFilters] = useState<ContestFilters>({})
  const [listReloadTick, setListReloadTick] = useState(0)

  const meta = useFetch((signal) => metaService.get({ signal }), [])

  const { data, isLoading, error } = useFetch(
    (signal) => contestsService.listAssigned({ signal }),
    [listReloadTick],
  )

  const [reflectFor, setReflectFor] = useState<AssignedContest | null>(null)
  const [myEntry, setMyEntry] = useState<ContestMemberEntry | null>(null)

  const filtered = useMemo(() => {
    if (!data) return []
    const q = query.trim().toLowerCase()
    return data.filter((c) => {
      if (
        q &&
        !c.name.toLowerCase().includes(q) &&
        !(c.platform ?? "").toLowerCase().includes(q)
      )
        return false
      if (filters.platform?.length && !filters.platform.includes(c.platform ?? ""))
        return false
      if (
        filters.contest_type?.length &&
        !filters.contest_type.includes(c.contest_type ?? "")
      )
        return false
      if (
        filters.status?.length &&
        !filters.status.includes(c.my_status ?? "Not started")
      )
        return false
      if (
        filters.team_id != null &&
        !(c.assigned_teams ?? []).some((t) => t.id === filters.team_id)
      )
        return false
      return true
    })
  }, [data, query, filters])

  async function openReflection(c: AssignedContest) {
    setReflectFor(c)
    setMyEntry(null)
    try {
      const entries = await contestsService.listEntries(c.id)
      setMyEntry(entries.find((e) => e.user_id === user?.id) ?? null)
    } catch {
      setMyEntry(null)
    }
  }

  return (
    <div className="flex h-full min-h-0">
      <ContestFiltersSidebar
        meta={meta.data}
        filters={filters}
        onChange={setFilters}
        onClear={() => setFilters({})}
        role={role}
      />

      <div className="flex-1 min-w-0 overflow-y-auto px-5 py-4 space-y-4">
        <div className="page-toolbar">
          <h1 className="page-h1">Assigned Contests</h1>
          <span className="text-[12px] text-[color:var(--c-muted)]">
            {isLoading ? "Loading…" : `${filtered.length} contests`}
          </span>
          <div className="ml-auto">
            <input
              type="text"
              className="toolbar-input w-[260px]"
              placeholder="Search by name or platform…"
              value={searchInput}
              onChange={(e) => {
                setSearchInput(e.target.value)
                setQuery(e.target.value)
              }}
            />
          </div>
        </div>

        {error && <p className="text-[color:var(--c-red)]">{error}</p>}

        <div
          className="rounded-md border overflow-x-auto"
          style={{ background: "var(--c-panel)", borderColor: "var(--c-border)" }}
        >
          <table className="data-table w-full">
            <thead>
              <tr>
                <th>Contest</th>
                <th>Platform</th>
                <th>Year</th>
                <th>Stars</th>
                <th>Length</th>
                <th>Due</th>
                {isStaff ? (
                  <th>Teams</th>
                ) : (
                  <>
                    <th>Solved</th>
                    <th>My status</th>
                    <th></th>
                  </>
                )}
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={colCount} className="empty-cell">
                    Loading…
                  </td>
                </tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={colCount} className="empty-cell">
                    No contests assigned yet.
                  </td>
                </tr>
              ) : (
                filtered.map((c) => (
                  <ContestRow
                    key={c.id}
                    c={c}
                    isStaff={isStaff}
                    colCount={colCount}
                    onEditReflection={() => openReflection(c)}
                  />
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <ReflectionModal
        open={reflectFor !== null}
        onClose={() => setReflectFor(null)}
        contestId={reflectFor?.id ?? null}
        contestName={reflectFor?.name ?? ""}
        initial={myEntry}
        onSaved={() => setListReloadTick((n) => n + 1)}
      />
    </div>
  )
}

function ContestRow({
  c,
  isStaff,
  colCount,
  onEditReflection,
}: {
  c: AssignedContest
  isStaff: boolean
  colCount: number
  onEditReflection: () => void
}) {
  const [expanded, setExpanded] = useState(false)
  const due = earliestDue(c)

  return (
    <>
      <tr className="cursor-pointer" onClick={() => setExpanded((v) => !v)}>
        <td>
          <div className="flex items-center gap-1.5">
            <span className="text-[color:var(--c-muted)] text-[11px]">
              {expanded ? "▾" : "▸"}
            </span>
            {c.url ? (
              <a
                href={c.url}
                target="_blank"
                rel="noreferrer"
                onClick={(e) => e.stopPropagation()}
                className="text-[color:var(--c-accent)] hover:underline truncate max-w-[260px]"
              >
                {c.name}
              </a>
            ) : (
              <span className="truncate max-w-[260px]">{c.name}</span>
            )}
          </div>
          {c.contest_type && (
            <div className="text-[11px] text-[color:var(--c-muted)] ml-[18px]">
              {c.contest_type}
            </div>
          )}
        </td>
        <td className="text-[12px]">{c.platform ?? "—"}</td>
        <td className="text-[12px]">{c.contest_year ?? "—"}</td>
        <td>
          {c.stars != null ? (
            <span
              className="text-[color:var(--c-amber)] text-[12px]"
              title={`${c.stars} stars`}
            >
              {"★".repeat(c.stars)}
            </span>
          ) : (
            <span className="text-[color:var(--c-muted)]">—</span>
          )}
        </td>
        <td className="text-[12px]">{formatDuration(c.duration_minutes)}</td>
        <td className="text-[12px]">
          {due ? due : <span className="text-[color:var(--c-muted)]">—</span>}
        </td>
        {isStaff ? (
          <td className="text-[12px]">
            {c.assigned_teams?.length ? (
              `${c.assigned_teams.length} team${c.assigned_teams.length === 1 ? "" : "s"}`
            ) : (
              <span className="text-[color:var(--c-muted)]">—</span>
            )}
          </td>
        ) : (
          <>
            <td className="text-[12px]">
              {c.my_solved_count}
              {c.problem_count ? `/${c.problem_count}` : ""}
            </td>
            <td>
              <Pill value={STATUS_PILL[c.my_status ?? "Not started"]}>
                {c.my_status ?? "Not started"}
              </Pill>
            </td>
            <td>
              <button
                type="button"
                className="btn btn-sm btn-primary"
                onClick={(e) => {
                  e.stopPropagation()
                  onEditReflection()
                }}
              >
                Reflection
              </button>
            </td>
          </>
        )}
      </tr>
      {expanded && (
        <tr className="expanded-row">
          <td
            colSpan={colCount}
            style={{ background: "var(--c-panel-2)", padding: "14px 16px" }}
          >
            <TeamBreakdownBlock contestId={c.id} />
          </td>
        </tr>
      )}
    </>
  )
}

function TeamBreakdownBlock({ contestId }: { contestId: number }) {
  const { data, isLoading, error } = useFetch<ContestTeamBreakdown[]>(
    (signal) => contestsService.breakdown(contestId, { signal }),
    [contestId],
  )

  if (isLoading)
    return <div className="text-[color:var(--c-muted)] text-[13px]">Loading…</div>
  if (error) return <div className="text-[color:var(--c-red)] text-[13px]">{error}</div>
  if (!data || data.length === 0)
    return (
      <div className="text-[color:var(--c-muted)] text-[13px]">
        No teams assigned.
      </div>
    )

  return (
    <div className="space-y-4">
      {data.map((team) => (
        <TeamSection key={team.team_id} team={team} />
      ))}
    </div>
  )
}

function TeamSection({ team }: { team: ContestTeamBreakdown }) {
  const completed = team.members.filter((m) => m.status === "Completed").length
  const totalSolved = team.members.reduce((s, m) => s + m.solved_count, 0)

  return (
    <div>
      <div className="flex items-center gap-2.5 mb-1.5">
        <strong className="text-[13px]">{team.team_name}</strong>
        <span
          className={`pill ${
            completed === team.members.length && team.members.length > 0
              ? "pill-Done"
              : completed > 0
                ? "pill-In-Progress"
                : "pill-Todo"
          }`}
        >
          {completed}/{team.members.length} completed
        </span>
        <span className="text-[11px] text-[color:var(--c-muted)]">
          {totalSolved} problems solved
        </span>
      </div>
      <table className="data-table w-full" style={{ background: "var(--c-panel)" }}>
        <thead>
          <tr>
            <th>Member</th>
            <th>Status</th>
            <th>Solved</th>
            <th>How it went</th>
            <th>Mistakes</th>
          </tr>
        </thead>
        <tbody>
          {team.members.length === 0 ? (
            <tr>
              <td colSpan={5} className="text-[color:var(--c-muted)] text-[12px]">
                No members
              </td>
            </tr>
          ) : (
            team.members.map((m) => (
              <tr key={m.user_id}>
                <td className="text-[13px]">
                  {m.name}
                  {m.role_in_team === "Reserve" && <Tag>Reserve</Tag>}
                </td>
                <td>
                  <Pill value={STATUS_PILL[m.status]}>{m.status}</Pill>
                </td>
                <td className="text-[12px]">{m.solved_count}</td>
                <td className="text-[12px] max-w-[280px]">
                  {m.feedback || (
                    <span className="text-[color:var(--c-muted)]">—</span>
                  )}
                </td>
                <td className="text-[12px] max-w-[280px]">
                  {m.mistakes || (
                    <span className="text-[color:var(--c-muted)]">—</span>
                  )}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}
