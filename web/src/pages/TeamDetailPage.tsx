import { Link, useParams } from "react-router-dom"
import { useFetch } from "@/hooks/useFetch"
import { teamsService } from "@/services/teams"
import { ProblemsTable } from "@/components/problems/ProblemsTable"
import { Pill } from "@/components/common/Pill"
import { useAuth } from "@/contexts/AuthContext"
import type { Problem } from "@/types/problem"
import type { Team } from "@/types/team"

type TeamProblems = {
  team: Team
  count: number
  results: Problem[]
}

export function TeamDetailPage() {
  const { id } = useParams<{ id: string }>()
  const teamId = Number(id)
  const { role } = useAuth()

  const { data, isLoading, error } = useFetch<TeamProblems>(
    (signal) =>
      teamsService.listProblems(teamId, { signal }) as Promise<TeamProblems>,
    [teamId],
  )

  return (
    <div className="h-full overflow-y-auto px-5 py-4 space-y-4">
      <div className="page-toolbar">
        <Link
          to="/teams"
          className="btn btn-sm"
          aria-label="Back to teams"
        >
          ← Back to teams
        </Link>
        <h1 className="page-h1">{data?.team.name ?? "Team"}</h1>
        {data?.team && (
          <div className="flex items-center gap-2 text-[12px] text-[color:var(--c-muted)]">
            <span>
              {data.team.member_count} members + {data.team.reserve_count} reserve
            </span>
            <Pill value="Done">{data.count} problems</Pill>
          </div>
        )}
      </div>

      {error && <p className="text-[color:var(--c-red)]">{error}</p>}

      {isLoading ? (
        <div
          className="rounded-md border p-10 text-center text-[color:var(--c-muted)]"
          style={{ borderColor: "var(--c-border)", background: "var(--c-panel)" }}
        >
          Loading…
        </div>
      ) : data?.results.length === 0 ? (
        <div className="text-center text-[color:var(--c-muted)] py-12">
          No problems assigned to this team yet.
        </div>
      ) : (
        <ProblemsTable
          problems={data?.results ?? []}
          role={role ?? "Coach"}
        />
      )}
    </div>
  )
}
