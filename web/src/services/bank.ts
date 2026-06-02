import { api } from "@/lib/api"
import type { ProblemFilters, ProblemListResponse } from "@/types/problem"

export type BankAssignInput = {
  assigned_user_ids?: number[]
  assigned_team_ids?: number[]
}

export const bankService = {
  listProblems: (
    filters: ProblemFilters,
    opts?: { signal?: AbortSignal },
  ) =>
    api.get<ProblemListResponse>("/bank/problems", {
      params: filters as Record<string, string | number | string[] | undefined>,
      signal: opts?.signal,
    }),

  assignProblem: (id: number, data: BankAssignInput) =>
    api.post<unknown>(`/bank/problems/${id}/assign`, data),
}
