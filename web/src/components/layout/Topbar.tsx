import { useEffect, useRef, useState } from "react"
import { NavLink, useLocation, useNavigate } from "react-router-dom"
import { toast } from "sonner"
import { useAuth } from "@/contexts/AuthContext"
import { adminService } from "@/services/admin"
import { cn } from "@/lib/utils"
import type { UserRole } from "@/types/user"
import { SettingsModal } from "@/components/settings/SettingsModal"

const BUG_REPORT_URL =
  "https://docs.google.com/forms/d/e/1FAIpQLSf9ApfYP8ExYHtPV0VHJn6z6RT3-a35QCXEbEeIGV2k8JzfLw/viewform?usp=sharing&ouid=108270920106753806595"

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
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  const tabs = TABS.filter(
    (t) => !t.allow || (role && t.allow.includes(role)),
  )

  // Close the account dropdown on outside click / Escape.
  useEffect(() => {
    if (!menuOpen) return
    function onDown(e: MouseEvent) {
      if (!menuRef.current?.contains(e.target as Node)) setMenuOpen(false)
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setMenuOpen(false)
    }
    document.addEventListener("mousedown", onDown)
    document.addEventListener("keydown", onKey)
    return () => {
      document.removeEventListener("mousedown", onDown)
      document.removeEventListener("keydown", onKey)
    }
  }, [menuOpen])

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
        <div className="ml-auto flex items-center gap-3">
          <a
            href={BUG_REPORT_URL}
            target="_blank"
            rel="noopener noreferrer"
            title="Report a bug or give feedback"
            className="px-3 py-1 rounded-md border text-[13px] hover:bg-[color:var(--c-panel-2)] transition-colors"
            style={{ borderColor: "var(--c-border)" }}
          >
            🐞 Report a Bug
          </a>
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
          <div className="relative" ref={menuRef}>
            <button
              type="button"
              onClick={() => setMenuOpen((o) => !o)}
              title={user.name}
              aria-haspopup="menu"
              aria-expanded={menuOpen}
              className="h-8 w-8 rounded-full grid place-items-center text-[13px] font-semibold transition-transform hover:scale-105"
              style={{
                background: "var(--c-panel-2)",
                border: "2px solid var(--c-accent)",
                color: "var(--c-text)",
              }}
            >
              {(user.name.trim().charAt(0) || "?").toUpperCase()}
            </button>

            {menuOpen && (
              <div
                role="menu"
                className="absolute right-0 mt-2 w-56 rounded-md border shadow-lg py-1 z-20"
                style={{
                  background: "var(--c-panel)",
                  borderColor: "var(--c-border)",
                }}
              >
                <div
                  className="px-3 py-2.5 border-b"
                  style={{ borderColor: "var(--c-border)" }}
                >
                  <div className="text-[13px] font-medium text-[color:var(--c-text)] truncate">
                    {user.name}
                  </div>
                  {user.email && (
                    <div className="text-[11px] text-[color:var(--c-muted)] truncate mt-0.5">
                      {user.email}
                    </div>
                  )}
                </div>
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setMenuOpen(false)
                    setSettingsOpen(true)
                  }}
                  className="w-full text-left px-3 py-2 text-[13px] flex items-center gap-2 hover:bg-[color:var(--c-panel-2)] transition-colors"
                >
                  <span>⚙</span> Settings
                </button>
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setMenuOpen(false)
                    onLogout()
                  }}
                  className="w-full text-left px-3 py-2 text-[13px] flex items-center gap-2 hover:bg-[color:var(--c-panel-2)] transition-colors"
                  style={{ color: "var(--c-red)" }}
                >
                  <span>⎋</span> Logout
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </>
  )
}
