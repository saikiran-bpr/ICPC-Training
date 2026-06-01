export type UserRole = "Admin" | "Coach" | "Contestant"

export const USER_ROLES: UserRole[] = ["Admin", "Coach", "Contestant"]

export type UserStatus = "pending" | "approved" | "rejected"

export type User = {
  id: number
  email: string
  name: string
  role: UserRole
  handle?: string | null
  institution?: string | null
  year_of_study?: number | null
  is_active: boolean
  status: UserStatus
  date_joined?: string | null
  last_login?: string | null
}
