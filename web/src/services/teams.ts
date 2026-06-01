import { api } from "@/lib/api"
import type { Team } from "@/types/team"

export type TeamWrite = {
  name: string
  institution?: string | null
  description?: string | null
}

/** Lightweight team shape returned by the paginated search/picker endpoint. */
export type TeamPicker = {
  id: number
  name: string
  institution: string | null
}

export type TeamSearchResponse = {
  total: number
  results: TeamPicker[]
}

export const teamsService = {
  list: (
    params?: { mine?: "1" },
    opts?: { signal?: AbortSignal },
  ) =>
    api.get<Team[]>("/teams", {
      params: params as Record<string, string | number | undefined>,
      signal: opts?.signal,
    }),

  /**
   * Paginated, server-side team search for assignment pickers.  The server
   * scopes results to teams the caller coaches (Admins see all).
   */
  search: (
    params: { q?: string; limit?: number; offset?: number },
    opts?: { signal?: AbortSignal },
  ) =>
    api.get<TeamSearchResponse>("/teams/search", {
      params: params as Record<string, string | number | undefined>,
      signal: opts?.signal,
    }),

  get: (id: number, opts?: { signal?: AbortSignal }) =>
    api.get<Team>(`/teams/${id}`, { signal: opts?.signal }),

  create: (data: TeamWrite) => api.post<Team>("/teams", data),

  update: (id: number, data: Partial<TeamWrite>) =>
    api.patch<Team>(`/teams/${id}`, data),

  remove: (id: number) => api.delete<{ ok: true }>(`/teams/${id}`),

  addMember: (id: number, data: { user_id: number; role_in_team: "Member" | "Reserve" }) =>
    api.post<Team>(`/teams/${id}/members`, data),

  updateMember: (id: number, uid: number, data: { role_in_team: "Member" | "Reserve" }) =>
    api.patch<Team>(`/teams/${id}/members/${uid}`, data),

  removeMember: (id: number, uid: number) =>
    api.delete<{ ok: true }>(`/teams/${id}/members/${uid}`),

  addCoach: (id: number, data: { user_id: number }) =>
    api.post<Team>(`/teams/${id}/coaches`, data),

  removeCoach: (id: number, uid: number) =>
    api.delete<{ ok: true }>(`/teams/${id}/coaches/${uid}`),

  listProblems: (id: number, opts?: { signal?: AbortSignal }) =>
    api.get<{ team: Team; count: number; results: unknown[] }>(
      `/teams/${id}/problems`,
      { signal: opts?.signal },
    ),
}
