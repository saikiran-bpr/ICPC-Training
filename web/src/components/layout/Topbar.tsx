import { useEffect, useState } from "react"
import { NavLink, useLocation, useNavigate } from "react-router-dom"
import { toast } from "sonner"
import { useAuth } from "@/contexts/AuthContext"
import { adminService } from "@/services/admin"
import { cn } from "@/lib/utils"
import type { UserRole } from "@/types/user"
import { SettingsModal } from "@/components/settings/SettingsModal"

type Tab = {
  to: string
  label: string
  allow?: UserRole[]
}

const TABS: Tab[] = [
  { to: "/problems", label: "Assigned Problems" },
  { to: "/contests", label: "Assigned Contests" },
  { to: "/teams", label: "Teams" },
  { to: "/bank/problems", label: "Problem Bank", allow: ["Admin", "Coach"] },
  { to: "/bank/contests", label: "Contest Bank", allow: ["Admin", "Coach"] },
  { to: "/users", label: "Users", allow: ["Admin"] },
  { to: "/requests", label: "Requests", allow: ["Admin"] },
]

export function Topbar() {
  const { user, role, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [pendingCount, setPendingCount] = useState(0)

  const tabs = TABS.filter(
    (t) => !t.allow || (role && t.allow.includes(role)),
  )

  // Refresh the pending-requests badge for admins. Re-fetched on route
  // changes so approving on /requests immediately reflects in the badge.
  useEffect(() => {
    if (role !== "Admin") {
      setPendingCount(0)
      return
    }
    const ctrl = new AbortController()
    adminService
      .pendingCount({ signal: ctrl.signal })
      .then((r) => setPendingCount(r.count))
      .catch(() => {
        /* badge is best-effort */
      })
    return () => ctrl.abort()
  }, [role, location.pathname])

  async function onLogout() {
    try {
      await logout()
      toast.success("Signed out")
      navigate("/login", { replace: true })
    } catch {
      toast.error("Could not sign out")
    }
  }

  if (!user) return null

  return (
    <>
      <header
        className="sticky top-0 z-10 flex items-center gap-4 px-5 h-[49px] border-b"
        style={{
          background: "var(--c-panel)",
          borderColor: "var(--c-border)",
        }}
      >
        <div className="text-base font-semibold tracking-tight">
          ICPC Training
        </div>

        <nav className="flex items-center gap-1 ml-2">
          {tabs.map((tab) => (
            <NavLink
              key={tab.to}
              to={tab.to}
              className={({ isActive }) =>
                cn(
                  "px-3 py-1.5 rounded-md text-[13px] transition-colors",
                  isActive
                    ? "border"
                    : "text-[color:var(--c-muted)] hover:text-[color:var(--c-text)]",
                )
              }
              style={({ isActive }) =>
                isActive
                  ? {
                      background: "var(--c-panel-2)",
                      borderColor: "var(--c-border)",
                      color: "var(--c-text)",
                    }
                  : undefined
              }
            >
              {tab.label}
              {tab.to === "/requests" && pendingCount > 0 && (
                <span
                  className="ml-1.5 inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full text-[10px] font-semibold"
                  style={{
                    background: "var(--c-red, #dc2626)",
                    color: "#fff",
                  }}
                >
                  {pendingCount}
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-3 text-[13px]">
          {role && (
            <span
              className={cn(
                "px-2 py-[2px] rounded-[10px] text-[11px] font-medium border",
                `pill pill-${role}`,
              )}
            >
              {role}
            </span>
          )}
          <span className="text-[color:var(--c-text)]">{user.name}</span>
          <button
            type="button"
            onClick={() => setSettingsOpen(true)}
            title="Settings"
            className="h-7 w-7 grid place-items-center rounded-md hover:bg-[color:var(--c-panel-2)] transition-colors"
          >
            ⚙
          </button>
          <button
            type="button"
            onClick={onLogout}
            className="px-3 py-1 rounded-md border text-[13px] hover:bg-[color:var(--c-panel-2)] transition-colors"
            style={{ borderColor: "var(--c-border)" }}
          >
            Logout
          </button>
        </div>
      </header>

      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </>
  )
}
