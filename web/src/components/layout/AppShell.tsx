import { Outlet } from "react-router-dom"
import { Topbar } from "./Topbar"

export function AppShell() {
  return (
    <div
      className="min-h-screen flex flex-col"
      style={{ background: "var(--c-bg)", color: "var(--c-text)" }}
    >
      <Topbar />
      <main className="flex-1 min-h-0 overflow-hidden">
        <Outlet />
      </main>
    </div>
  )
}
