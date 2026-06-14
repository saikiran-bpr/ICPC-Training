import { api } from "@/lib/api"
import type { ProblemFilters, ProblemListResponse } from "@/types/problem"

export type BankAssignInput = {
  assigned_user_ids?: number[]
  assigned_team_ids?: number[]
}

export type BankBatchAssignInput = BankAssignInput & {
  problem_ids: number[]
}

export type BankBatchAssignResult = {
  problems_assigned: number
  users_assigned: number
  teams_assigned: number
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

  // Batch-assign several bank problems to users/teams in one call.
  batchAssign: (data: BankBatchAssignInput) =>
    api.post<BankBatchAssignResult>("/bank/problems/assign", data),
}
