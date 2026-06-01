import { Link, useParams } from "react-router-dom"
import { useFetch } from "@/hooks/useFetch"
import { usersService } from "@/services/users"
import { ProblemsTable } from "@/components/problems/ProblemsTable"
import { Pill } from "@/components/common/Pill"
import type { Problem } from "@/types/problem"
import type { User } from "@/types/user"

type UserProblems = {
  user: User
  count: number
  results: Problem[]
}

export function UserDetailPage() {
  const { id } = useParams<{ id: string }>()
  const userId = Number(id)

  const { data, isLoading, error } = useFetch<UserProblems>(
    (signal) =>
      usersService.listProblems(userId, { signal }) as Promise<UserProblems>,
    [userId],
  )

  return (
    <div className="h-full overflow-y-auto px-5 py-4 space-y-4">
      <div className="page-toolbar">
        <Link to="/users" className="btn btn-sm">
          ← Back to users
        </Link>
        <h1 className="page-h1">{data?.user.name ?? "User"}</h1>
        {data?.user && (
          <div className="flex items-center gap-2 text-[12px] text-[color:var(--c-muted)]">
            <Pill value={data.user.role} />
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
          No problems assigned to this user yet.
        </div>
      ) : (
        <ProblemsTable
          problems={data?.results ?? []}
          role="Contestant"
        />
      )}
    </div>
  )
}
