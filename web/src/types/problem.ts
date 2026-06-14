export type AssignedUser = {
  id: number
  name: string
  role: string
}

export type AssignedTeam = {
  id: number
  name: string
}

export type Attempt = {
  attempt_status: string | null
  attempt_phase: string | null
  problem_faced: string | null
  time_spent_min: number | null
  notes: string | null
  updated_at: string | null
} | null

export type TeamMemberAttempt = {
  id: number
  name: string
  role_in_team: "Member" | "Reserve"
  attempt_status: string | null
  attempt_phase: string | null
  problem_faced: string | null
  time_spent_min: number | null
  notes: string | null
  updated_at: string | null
}

export type TeamSummary = {
  team_id: number | null
  team_name: string
  solved: number
  total: number
  reserve_solved: number
  reserve_total: number
  members: TeamMemberAttempt[]
}

export type Problem = {
  id: number
  name: string
  url: string
  platform: string | null
  contest_type: string | null
  rating: number | null
  difficulty: string | null
  topic: string | null
  sub_topic: string | null
  tags: string[]
  importance: string | null
  key_idea: string | null
  status: string | null
  created_by: number | null
  notes: string | null
  date_added: string | null
  date_updated: string | null
  assigned_users: AssignedUser[]
  assigned_teams: AssignedTeam[]
  my_attempt: Attempt
  team_summary: TeamSummary[]
  /** Contestant view: who assigned this to the viewer, and how. */
  assigned_by: AssignedUser | null
  assigned_via: string | null
}

export type ProblemListResponse = {
  total: number
  count: number
  results: Problem[]
}

export type ProblemFilters = {
  q?: string
  // Multi-select capable: the Problem Bank passes arrays; the Assigned
  // sidebar passes single strings. The API client serialises both.
  platform?: string | string[]
  topic?: string | string[]
  difficulty?: string | string[]
  importance?: string | string[]
  status?: string | string[]
  contest_type?: string | string[]
  assigned_user_id?: number
  assigned_team_id?: number
  rating_min?: number
  rating_max?: number
  sort?: string
  order?: "asc" | "desc"
  limit?: number
  offset?: number
}
