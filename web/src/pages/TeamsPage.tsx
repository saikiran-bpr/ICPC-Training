import { useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"
import { toast } from "sonner"
import { useFetch } from "@/hooks/useFetch"
import { teamsService } from "@/services/teams"
import { assignmentService } from "@/services/assignment"
import { useAuth } from "@/contexts/AuthContext"
import { TeamCard } from "@/components/teams/TeamCard"
import { TeamModal } from "@/components/teams/TeamModal"
import { ApiError } from "@/lib/api"
import type { Team } from "@/types/team"

export function TeamsPage() {
  const { role } = useAuth()
  // Edit team meta + manage members + delete: Admin always; Coach for teams
  // they coach. The backend list endpoint already filters teams to the ones
  // the Coach coaches, so every card a Coach sees is one they can manage.
  const canManage = role === "Admin" || role === "Coach"
  // Coach assignment is admin-only (matches POST /teams/{id}/coaches).
  const canManageCoaches = role === "Admin"
  const canDelete = canManage

  const navigate = useNavigate()
  const [reloadTick, setReloadTick] = useState(0)
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<Team | null>(null)

  const list = useFetch(
    (signal) => teamsService.list(undefined, { signal }),
    [reloadTick],
  )
  const opts = useFetch((s) => assignmentService.get({ signal: s }), [reloadTick])

  const refresh = () => setReloadTick((n) => n + 1)

  const allUsers = useMemo(() => opts.data?.users ?? [], [opts.data])
  const candidateOf = (team: Team, predicate: (u: { role: string }) => boolean) => {
    const onTeam = new Set([
      ...team.members.map((m) => m.id),
      ...team.coaches.map((c) => c.id),
    ])
    return allUsers.filter((u) => predicate(u) && !onTeam.has(u.id))
  }

  async function withRefresh(fn: () => Promise<unknown>, success: string) {
    try {
      await fn()
      toast.success(success)
      refresh()
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Failed")
    }
  }

  return (
    <div className="h-full overflow-y-auto px-5 py-4 space-y-4">
      <div className="page-toolbar">
        <h1 className="page-h1">Teams</h1>
        <span className="text-[12px] text-[color:var(--c-muted)]">
          {list.isLoading ? "Loading…" : `${list.data?.length ?? 0} teams`}
        </span>

        {canManage && (
          <button
            type="button"
            className="btn btn-primary ml-auto"
            onClick={() => {
              setEditing(null)
              setModalOpen(true)
            }}
          >
            + New Team
          </button>
        )}
      </div>

      {list.error && <p className="text-[color:var(--c-red)]">{list.error}</p>}

      {!list.isLoading && list.data?.length === 0 && (
        <div className="text-center text-[color:var(--c-muted)] py-12">
          No teams yet. {canManage && "Click + New Team to create one."}
        </div>
      )}

      <div className="card-grid">
        {list.data?.map((t) => (
          <TeamCard
            key={t.id}
            team={t}
            canManage={canManage}
            canManageCoaches={canManageCoaches}
            canDelete={canDelete}
            coachCandidates={candidateOf(
              t,
              (u) => u.role === "Admin" || u.role === "Coach",
            )}
            onClickName={() => navigate(`/teams/${t.id}`)}
            onEdit={() => {
              setEditing(t)
              setModalOpen(true)
            }}
            onDelete={() => {
              if (!confirm(`Delete team "${t.name}"?`)) return
              withRefresh(() => teamsService.remove(t.id), "Team deleted")
            }}
            onAddMember={(uid, r) =>
              withRefresh(
                () =>
                  teamsService.addMember(t.id, {
                    user_id: uid,
                    role_in_team: r,
                  }),
                "Member added",
              )
            }
            onRemoveMember={(uid) =>
              withRefresh(
                () => teamsService.removeMember(t.id, uid),
                "Member removed",
              )
            }
            onToggleMemberRole={(uid, current) =>
              withRefresh(
                () =>
                  teamsService.updateMember(t.id, uid, {
                    role_in_team: current === "Member" ? "Reserve" : "Member",
                  }),
                "Role updated",
              )
            }
            onAddCoach={(uid) =>
              withRefresh(
                () => teamsService.addCoach(t.id, { user_id: uid }),
                "Coach added",
              )
            }
            onRemoveCoach={(uid) =>
              withRefresh(
                () => teamsService.removeCoach(t.id, uid),
                "Coach removed",
              )
            }
          />
        ))}
      </div>

      <TeamModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        initial={editing}
        onSaved={refresh}
      />
    </div>
  )
}
