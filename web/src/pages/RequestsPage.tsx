import { useState } from "react"
import { toast } from "sonner"
import { useFetch } from "@/hooks/useFetch"
import { adminService } from "@/services/admin"
import { RequestDetailModal } from "@/components/admin/RequestDetailModal"
import { ApiError } from "@/lib/api"
import type { User } from "@/types/user"

export function RequestsPage() {
  const [reloadTick, setReloadTick] = useState(0)
  const [busyId, setBusyId] = useState<number | null>(null)
  const [viewing, setViewing] = useState<User | null>(null)

  const list = useFetch((s) => adminService.listRequests({ signal: s }), [
    reloadTick,
  ])

  const refresh = () => setReloadTick((n) => n + 1)

  async function approve(u: User) {
    setBusyId(u.id)
    try {
      await adminService.approve(u.id)
      toast.success(`${u.name} approved`)
      setViewing(null)
      refresh()
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Approve failed")
    } finally {
      setBusyId(null)
    }
  }

  async function reject(u: User) {
    if (
      !window.confirm(
        `Reject signup request from ${u.name} (${u.email})? This will delete the request.`,
      )
    ) {
      return
    }
    setBusyId(u.id)
    try {
      await adminService.reject(u.id)
      toast.success(`${u.name}'s request rejected`)
      setViewing(null)
      refresh()
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Reject failed")
    } finally {
      setBusyId(null)
    }
  }

  const rows = list.data ?? []

  return (
    <div className="h-full overflow-y-auto px-5 py-4 space-y-4">
      <div className="page-toolbar">
        <h1 className="page-h1">Signup Requests</h1>
        <span className="text-[12px] text-[color:var(--c-muted)]">
          {list.isLoading
            ? "Loading…"
            : `${rows.length} pending`}
        </span>
      </div>

      <div
        className="rounded-md border overflow-x-auto"
        style={{ background: "var(--c-panel)", borderColor: "var(--c-border)" }}
      >
        <table className="data-table w-full">
          <thead>
            <tr>
              <th>Name</th>
              <th>Email</th>
              <th>Handle</th>
              <th>Institution</th>
              <th>Year</th>
              <th>Requested</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {list.isLoading ? (
              <tr>
                <td colSpan={7} className="empty-cell">Loading…</td>
              </tr>
            ) : list.error ? (
              <tr>
                <td colSpan={7} className="empty-cell">
                  Failed to load: {list.error}
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={7} className="empty-cell">
                  No pending requests.
                </td>
              </tr>
            ) : (
              rows.map((u) => (
                <tr key={u.id}>
                  <td>
                    <button
                      type="button"
                      className="text-[color:var(--c-accent)] hover:underline text-left"
                      onClick={() => setViewing(u)}
                    >
                      {u.name}
                    </button>
                  </td>
                  <td className="text-[12px] text-[color:var(--c-muted)]">
                    {u.email}
                  </td>
                  <td className="text-[12px]">{u.handle ?? "—"}</td>
                  <td className="text-[12px]">{u.institution ?? "—"}</td>
                  <td className="text-[12px]">{u.year_of_study ?? "—"}</td>
                  <td className="text-[12px] text-[color:var(--c-muted)]">
                    {u.date_joined
                      ? u.date_joined.split("T")[0] ??
                        u.date_joined.split(" ")[0]
                      : "—"}
                  </td>
                  <td>
                    <div className="flex gap-1">
                      <button
                        type="button"
                        className="btn btn-sm"
                        onClick={() => setViewing(u)}
                      >
                        Details
                      </button>
                      <button
                        type="button"
                        className="btn btn-sm btn-primary"
                        disabled={busyId === u.id}
                        onClick={() => approve(u)}
                      >
                        Approve
                      </button>
                      <button
                        type="button"
                        className="btn btn-sm btn-danger"
                        disabled={busyId === u.id}
                        onClick={() => reject(u)}
                      >
                        Reject
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <RequestDetailModal
        request={viewing}
        onClose={() => setViewing(null)}
        onApprove={approve}
        onReject={reject}
        busy={viewing != null && busyId === viewing.id}
      />
    </div>
  )
}
