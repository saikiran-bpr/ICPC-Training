import type { AsyncSearchResult } from "@/components/common/AsyncMultiSelect"
import { usersService } from "@/services/users"
import { teamsService } from "@/services/teams"

type Window = { limit: number; offset: number; signal: AbortSignal }

/**
 * Search callbacks shared by the assignment pickers (New Problem modal +
 * bank/contest Assign modal).  Module-level so their identity is stable —
 * `AsyncMultiSelect` keys its fetch effect on the `search` prop.
 *
 * Both are re-enforced on the server at save time: users must be Contestants,
 * and the teams endpoint scopes results to teams the caller coaches.
 */

/** Paginated Contestant search — matches name or Codeforces handle. */
export function searchContestants(q: string, o: Window): Promise<AsyncSearchResult> {
  return usersService
    .search(
      { q: q || undefined, role: "Contestant", limit: o.limit, offset: o.offset },
      { signal: o.signal },
    )
    .then((r) => ({
      total: r.total,
      results: r.results.map((u) => ({
        id: u.id,
        label: u.name,
        meta: u.handle ? `@${u.handle}` : u.email,
      })),
    }))
}

/** Paginated team search — server scopes results to teams the caller coaches. */
export function searchAssignableTeams(q: string, o: Window): Promise<AsyncSearchResult> {
  return teamsService
    .search({ q: q || undefined, limit: o.limit, offset: o.offset }, { signal: o.signal })
    .then((r) => ({
      total: r.total,
      results: r.results.map((t) => ({
        id: t.id,
        label: t.name,
        meta: t.institution ?? undefined,
      })),
    }))
}
