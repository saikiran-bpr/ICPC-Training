import { useState } from "react"
import { Link } from "react-router-dom"
import { toast } from "sonner"
import { useFetch } from "@/hooks/useFetch"
import { usersService } from "@/services/users"
import { metaService } from "@/services/meta"
import { useAuth } from "@/contexts/AuthContext"
import { Pill } from "@/components/common/Pill"
import { Tag } from "@/components/common/Tag"
import { UserCreateModal } from "@/components/users/UserCreateModal"
import { ApiError } from "@/lib/api"
import type { User, UserRole } from "@/types/user"

export function UsersPage() {
  const { role, user: me } = useAuth()
  const canCreate = role === "Admin"
  const canManage = role === "Admin"

  const [search, setSearch] = useState("")
  const [query, setQuery] = useState<string | undefined>(undefined)
  const [roleFilter, setRoleFilter] = useState<string | undefined>(undefined)
  const [reloadTick, setReloadTick] = useState(0)
  const [createOpen, setCreateOpen] = useState(false)

  const meta = useFetch((s) => metaService.get({ signal: s }), [])
  const list = useFetch(
    (s) =>
      usersService.list({ q: query, role: roleFilter }, { signal: s }),
    [query, roleFilter, reloadTick],
  )

  const refresh = () => setReloadTick((n) => n + 1)

  async function changeRole(u: User, newRole: UserRole) {
    try {
      await usersService.update(u.id, { role: newRole })
      toast.success("Role updated")
      refresh()
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Failed")
    }
  }

  async function toggleActive(u: User) {
    try {
      await usersService.update(u.id, { is_active: !u.is_active })
      toast.success(u.is_active ? "User disabled" : "User enabled")
      refresh()
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Failed")
    }
  }

  return (
    <div className="h-full overflow-y-auto px-5 py-4 space-y-4">
      <div className="page-toolbar">
        <h1 className="page-h1">Users</h1>
        <span className="text-[12px] text-[color:var(--c-muted)]">
          {list.isLoading ? "Loading…" : `${list.data?.length ?? 0} users`}
        </span>

        <div className="ml-auto flex items-center gap-2">
          <input
            type="text"
            className="toolbar-input w-[240px]"
            placeholder="Search by name, email, handle…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") setQuery(search.trim() || undefined)
            }}
            onBlur={() => setQuery(search.trim() || undefined)}
          />
          <select
            className="filter-control w-[140px]"
            value={roleFilter ?? ""}
            onChange={(e) => setRoleFilter(e.target.value || undefined)}
          >
            <option value="">All roles</option>
            {meta.data?.user_roles.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
          {canCreate && (
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => setCreateOpen(true)}
            >
              + New User
            </button>
          )}
        </div>
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
              <th>Role</th>
              <th>Handle</th>
              <th>Institution</th>
              <th>Status</th>
              <th>Joined</th>
              {canManage && <th>Actions</th>}
            </tr>
          </thead>
          <tbody>
            {list.isLoading ? (
              <tr>
                <td colSpan={canManage ? 8 : 7} className="empty-cell">
                  Loading…
                </td>
              </tr>
            ) : list.data?.length === 0 ? (
              <tr>
                <td colSpan={canManage ? 8 : 7} className="empty-cell">
                  No users found.
                </td>
              </tr>
            ) : (
              list.data?.map((u) => (
                <tr key={u.id}>
                  <td>
                    <Link
                      to={`/users/${u.id}`}
                      className="text-[color:var(--c-accent)] hover:underline"
                    >
                      {u.name}
                    </Link>
                  </td>
                  <td className="text-[12px] text-[color:var(--c-muted)]">{u.email}</td>
                  <td><Pill value={u.role} /></td>
                  <td>{u.handle ? <Tag>{u.handle}</Tag> : <span className="text-[color:var(--c-muted)]">—</span>}</td>
                  <td className="text-[12px]">{u.institution ?? "—"}</td>
                  <td>
                    <Pill value={u.is_active ? "Done" : "Skipped"}>
                      {u.is_active ? "Active" : "Disabled"}
                    </Pill>
                  </td>
                  <td className="text-[12px] text-[color:var(--c-muted)]">
                    {u.date_joined ? (u.date_joined.split("T")[0] ?? u.date_joined.split(" ")[0]) : "—"}
                  </td>
                  {canManage && (
                    <td>
                      {u.id === me?.id ? (
                        <span className="text-[11px] text-[color:var(--c-muted)]">—</span>
                      ) : (
                        <div className="flex gap-1">
                          <select
                            value={u.role}
                            className="filter-control w-[110px]"
                            onChange={(e) => changeRole(u, e.target.value as UserRole)}
                          >
                            <option value="Admin">Admin</option>
                            <option value="Coach">Coach</option>
                            <option value="Contestant">Contestant</option>
                          </select>
                          <button
                            type="button"
                            className={u.is_active ? "btn btn-sm btn-danger" : "btn btn-sm"}
                            onClick={() => toggleActive(u)}
                          >
                            {u.is_active ? "Disable" : "Enable"}
                          </button>
                        </div>
                      )}
                    </td>
                  )}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <UserCreateModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onSaved={refresh}
      />
    </div>
  )
}
