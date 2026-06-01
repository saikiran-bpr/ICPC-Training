import { api } from "@/lib/api"
import type {
  AssignedContest,
  ContestSummary,
  ContestWithProblems,
} from "@/types/contest"

export type ContestWrite = {
  name: string
  platform?: string | null
  contest_type?: string | null
  contest_year?: number | null
  url?: string | null
  notes?: string | null
}

export type ContestAssignInput = {
  assigned_user_ids?: number[]
  assigned_team_ids?: number[]
}

export const contestsService = {
  listAssigned: (opts?: { signal?: AbortSignal }) =>
    api.get<AssignedContest[]>("/contests/assigned", { signal: opts?.signal }),

  listBank: (
    params?: { q?: string },
    opts?: { signal?: AbortSignal },
  ) =>
    api.get<ContestSummary[]>("/bank/contests", {
      params: params as Record<string, string | number | undefined>,
      signal: opts?.signal,
    }),

  get: (id: number, opts?: { signal?: AbortSignal }) =>
    api.get<ContestWithProblems>(`/bank/contests/${id}`, {
      signal: opts?.signal,
    }),

  create: (data: ContestWrite) =>
    api.post<ContestSummary>("/bank/contests", data),

  update: (id: number, data: Partial<ContestWrite>) =>
    api.patch<ContestSummary>(`/bank/contests/${id}`, data),

  remove: (id: number) =>
    api.delete<{ ok: true }>(`/bank/contests/${id}`),

  assign: (id: number, data: ContestAssignInput) =>
    api.post<unknown>(`/bank/contests/${id}/assign`, data),

  removeProblem: (id: number, pid: number) =>
    api.delete<{ ok: true }>(`/bank/contests/${id}/problems/${pid}`),

  generateTutorials: (id: number) =>
    api.post<{ queued_count: number; message: string }>(
      `/contests/${id}/tutorial/generate`,
    ),

  tutorialStatus: (id: number, opts?: { signal?: AbortSignal }) =>
    api.get<{
      total: number
      done: number
      generating: number
      queued: number
      failed: number
      missing: number
    }>(`/contests/${id}/tutorial/status`, { signal: opts?.signal }),
}
