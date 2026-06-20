import { api } from "@/lib/api"
import type {
  AssignedContest,
  ContestMemberEntry,
  ContestSummary,
  ContestTeamBreakdown,
  ContestWithProblems,
  MemberStatus,
} from "@/types/contest"

export type ContestWrite = {
  name: string
  platform?: string | null
  contest_type?: string | null
  contest_year?: number | null
  url?: string | null
  notes?: string | null
  stars?: number | null
  duration_minutes?: number | null
}

export type ContestAssignInput = {
  assigned_team_ids: number[]
  due_date?: string | null
}

export type MemberEntryInput = {
  status: MemberStatus
  solved_count: number
  feedback?: string | null
  mistakes?: string | null
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

  unassignTeam: (id: number, teamId: number) =>
    api.delete<{ contest_id: number; removed_team_id: number }>(
      `/bank/contests/${id}/teams/${teamId}`,
    ),

  listEntries: (id: number, opts?: { signal?: AbortSignal }) =>
    api.get<ContestMemberEntry[]>(`/contests/${id}/entries`, {
      signal: opts?.signal,
    }),

  breakdown: (id: number, opts?: { signal?: AbortSignal }) =>
    api.get<ContestTeamBreakdown[]>(`/contests/${id}/breakdown`, {
      signal: opts?.signal,
    }),

  saveEntry: (id: number, data: MemberEntryInput) =>
    api.put<ContestMemberEntry>(`/contests/${id}/entry`, data),

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
