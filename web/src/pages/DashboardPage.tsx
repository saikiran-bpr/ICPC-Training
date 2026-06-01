import { useAuth } from "@/contexts/AuthContext"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

export function DashboardPage() {
  const { user, role } = useAuth()

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground">
          Welcome back{user ? `, ${user.name}` : ""}.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Role</CardTitle>
            <CardDescription>Your current access level</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold">{role}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Problems</CardTitle>
            <CardDescription>Coming soon</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Phase 2 will show your assigned problem stats here.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Contests</CardTitle>
            <CardDescription>Coming soon</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Active contest assignments and progress will appear here.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
