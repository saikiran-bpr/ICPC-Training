import { api } from "@/lib/api"
import type { User, UserRole } from "@/types/user"

export type UserUpdate = Partial<{
  name: string
  handle: string | null
  institution: string | null
  year_of_study: number | null
  email: string
  role: UserRole
  is_active: boolean
}>

export type UserCreate = {
  email: string
  password: string
  name: string
  role: UserRole
  handle?: string
  institution?: string
  year_of_study?: number
}

export type UserSearchResponse = {
  total: number
  results: User[]
}

export const usersService = {
  list: (
    params?: { role?: string; q?: string },
    opts?: { signal?: AbortSignal },
  ) =>
    api.get<User[]>("/users", {
      params: params as Record<string, string | number | undefined>,
      signal: opts?.signal,
    }),

  /** Paginated, server-side search used by the team member picker. */
  search: (
    params: {
      q?: string
      role?: string
      exclude_team_id?: number
      limit?: number
      offset?: number
    },
    opts?: { signal?: AbortSignal },
  ) =>
    api.get<UserSearchResponse>("/users/search", {
      params: params as Record<string, string | number | undefined>,
      signal: opts?.signal,
    }),

  get: (id: number, opts?: { signal?: AbortSignal }) =>
    api.get<User>(`/users/${id}`, { signal: opts?.signal }),

  create: (data: UserCreate) => api.post<User>("/users", data),

  update: (id: number, data: UserUpdate) =>
    api.patch<User>(`/users/${id}`, data),

  listProblems: (id: number, opts?: { signal?: AbortSignal }) =>
    api.get<{ user: User; count: number; results: unknown[] }>(
      `/users/${id}/problems`,
      { signal: opts?.signal },
    ),
}
