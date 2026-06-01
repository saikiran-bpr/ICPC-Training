import type { Problem } from "./problem"

export type ContestAssignedUser = {
  id: number
  name: string
  role: string
}

export type ContestAssignedTeam = {
  id: number
  name: string
  institution?: string | null
}

export type ContestSummary = {
  id: number
  name: string
  platform: string | null
  contest_type: string | null
  contest_year: number | null
  url: string | null
  notes: string | null
  tutorial_pdf: string | null
  tutorial_translated: string | null
  tutorial_lang: string | null
  cf_stars: number | null
  ucup_stars: number | null
  created_by: number | null
  date_added: string | null
  problem_count: number
  bank_problem_count: number
  assigned_users: ContestAssignedUser[]
  assigned_teams: ContestAssignedTeam[]
}

export type ContestWithProblems = ContestSummary & {
  problems: Problem[]
}

export type AssignedContest = ContestSummary & {
  my_solved: number
  during_count: number
  upsolve_count: number
  unphased_solved: number
}
