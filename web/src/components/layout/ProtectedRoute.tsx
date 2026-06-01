import { Navigate, Outlet, useLocation } from "react-router-dom"
import { useAuth } from "@/contexts/AuthContext"
import { Skeleton } from "@/components/ui/skeleton"

export function ProtectedRoute() {
  const { isLoading, isAuthenticated } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center p-8">
        <Skeleton className="h-32 w-72" />
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />
  }

  return <Outlet />
}
