export type AssignmentOptions = {
  users: { id: number; name: string; email: string; role: string }[]
  teams: { id: number; name: string; institution: string | null }[]
}
