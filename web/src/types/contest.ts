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
  due_date?: string | null
}

export type MemberStatus = "Not started" | "Attempted" | "Completed"

export type ContestMemberEntry = {
  user_id: number
  user_name: string
  status: MemberStatus
  solved_count: number
  feedback: string | null
  mistakes: string | null
  updated_at: string | null
}

export type ContestTeamMember = {
  user_id: number
  name: string
  role_in_team: string | null
  status: MemberStatus
  solved_count: number
  feedback: string | null
  mistakes: string | null
}

export type ContestTeamBreakdown = {
  team_id: number
  team_name: string
  members: ContestTeamMember[]
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
  stars: number | null
  duration_minutes: number | null
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
  my_status: MemberStatus | null
  my_solved_count: number
}
