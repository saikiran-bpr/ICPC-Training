import { api } from "@/lib/api"
import type {
  Problem,
  ProblemFilters,
  ProblemListResponse,
} from "@/types/problem"

export type ProblemWrite = {
  name?: string
  url: string
  platform?: string
  contest_name?: string | null
  contest_type?: string
  contest_year?: number | null
  problem_index?: string | null
  rating?: number | null
  difficulty?: string
  topic?: string
  sub_topic?: string | null
  tags?: string[]
  importance?: string
  suggested_role?: string
  prerequisites?: string | null
  key_idea?: string | null
  editorial_url?: string | null
  status?: string
  notes?: string | null
  assigned_user_ids?: number[]
  assigned_team_ids?: number[]
}

export type AttemptInput = {
  attempt_status?: string
  attempt_phase?: string | null
  problem_faced?: string | null
  time_spent_min?: number | null
  notes?: string | null
}

export type LookupResponse = {
  name?: string
  rating?: number | null
  tags?: string[]
  difficulty?: string
  topic?: string
  platform?: string
  contest_type?: string
  sub_topic?: string
  problem_index?: string
}

export const problemsService = {
  list: (filters: ProblemFilters, opts?: { signal?: AbortSignal }) =>
    api.get<ProblemListResponse>("/problems", {
      params: filters as Record<string, string | number | undefined>,
      signal: opts?.signal,
    }),

  get: (id: number, opts?: { signal?: AbortSignal }) =>
    api.get<Problem>(`/problems/${id}`, { signal: opts?.signal }),

  create: (data: ProblemWrite) => api.post<Problem>("/problems", data),

  update: (id: number, data: ProblemWrite) =>
    api.put<Problem>(`/problems/${id}`, data),

  remove: (id: number) => api.delete<{ ok: true }>(`/problems/${id}`),

  updateAttempt: (id: number, data: AttemptInput) =>
    api.put<unknown>(`/problems/${id}/attempt`, data),

  lookup: (url: string, opts?: { signal?: AbortSignal }) =>
    api.get<LookupResponse>("/lookup", {
      params: { url },
      signal: opts?.signal,
    }),
}
