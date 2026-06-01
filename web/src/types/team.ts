export type TeamMember = {
  id: number
  name: string
  email: string
  handle: string | null
  institution: string | null
  role_in_team: "Member" | "Reserve"
  joined_at: string | null
}

export type TeamCoach = {
  id: number
  name: string
  email: string
  role: string
  assigned_at: string | null
}

export type Team = {
  id: number
  name: string
  institution: string | null
  description: string | null
  is_active: boolean
  created_at: string | null
  created_by: number | null
  members: TeamMember[]
  coaches: TeamCoach[]
  member_count: number
  reserve_count: number
}
