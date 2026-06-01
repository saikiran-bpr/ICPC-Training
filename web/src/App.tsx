import { Routes, Route, Navigate } from "react-router-dom"
import { AppShell } from "@/components/layout/AppShell"
import { ProtectedRoute } from "@/components/layout/ProtectedRoute"
import { RoleGate } from "@/components/layout/RoleGate"
import { LoginPage } from "@/pages/LoginPage"
import { SignupPage } from "@/pages/SignupPage"
import { ProblemsPage } from "@/pages/ProblemsPage"
import { AssignedContestsPage } from "@/pages/AssignedContestsPage"
import { TeamsPage } from "@/pages/TeamsPage"
import { ProblemBankPage } from "@/pages/ProblemBankPage"
import { ContestBankPage } from "@/pages/ContestBankPage"
import { UsersPage } from "@/pages/UsersPage"
import { RequestsPage } from "@/pages/RequestsPage"
import { TeamDetailPage } from "@/pages/TeamDetailPage"
import { UserDetailPage } from "@/pages/UserDetailPage"
import { NotFoundPage } from "@/pages/NotFoundPage"
import { PlaceholderPage } from "@/pages/PlaceholderPage"

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<AppShell />}>
          <Route index element={<Navigate to="/problems" replace />} />

          <Route path="problems" element={<ProblemsPage />} />
          <Route
            path="problems/:id"
            element={<PlaceholderPage title="Problem detail" />}
          />

          <Route path="contests" element={<AssignedContestsPage />} />

          <Route path="teams" element={<TeamsPage />} />
          <Route path="teams/:id" element={<TeamDetailPage />} />

          <Route
            path="bank/problems"
            element={
              <RoleGate
                allow={["Admin", "Coach"]}
                fallback={<PlaceholderPage title="Forbidden" />}
              >
                <ProblemBankPage />
              </RoleGate>
            }
          />
          <Route
            path="bank/contests"
            element={
              <RoleGate
                allow={["Admin", "Coach"]}
                fallback={<PlaceholderPage title="Forbidden" />}
              >
                <ContestBankPage />
              </RoleGate>
            }
          />
          <Route
            path="requests"
            element={
              <RoleGate
                allow={["Admin"]}
                fallback={<PlaceholderPage title="Forbidden" />}
              >
                <RequestsPage />
              </RoleGate>
            }
          />
          <Route
            path="users"
            element={
              <RoleGate
                allow={["Admin"]}
                fallback={<PlaceholderPage title="Forbidden" />}
              >
                <UsersPage />
              </RoleGate>
            }
          />
          <Route
            path="users/:id"
            element={
              <RoleGate
                allow={["Admin"]}
                fallback={<PlaceholderPage title="Forbidden" />}
              >
                <UserDetailPage />
              </RoleGate>
            }
          />

          <Route path="settings" element={<PlaceholderPage title="Settings" />} />
        </Route>
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
