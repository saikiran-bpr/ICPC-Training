import type { ReactNode } from "react"
import { useAuth } from "@/contexts/AuthContext"
import type { UserRole } from "@/types/user"

export function RoleGate({
  allow,
  children,
  fallback = null,
}: {
  allow: UserRole | UserRole[]
  children: ReactNode
  fallback?: ReactNode
}) {
  const { role } = useAuth()
  const allowed = Array.isArray(allow) ? allow : [allow]
  if (!role || !allowed.includes(role)) {
    return <>{fallback}</>
  }
  return <>{children}</>
}

export function hasRole(
  current: UserRole | null,
  allow: UserRole | UserRole[],
): boolean {
  if (!current) return false
  const allowed = Array.isArray(allow) ? allow : [allow]
  return allowed.includes(current)
}
