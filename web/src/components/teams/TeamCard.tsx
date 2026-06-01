import { useMemo, useState, type ReactNode } from "react"
import type { Team } from "@/types/team"
import { Pill } from "@/components/common/Pill"
import { Tag } from "@/components/common/Tag"
import { MemberPicker } from "@/components/teams/MemberPicker"

type Candidate = { id: number; name: string; email: string; role?: string }

type Props = {
  team: Team
  memberCap?: number
  reserveCap?: number
  /** Allowed to edit team meta + add/remove members. Admin OR Coach-of-team. */
  canManage?: boolean
  /** Allowed to add/remove coaches on this team. Admin-only (matches backend). */
  canManageCoaches?: boolean
  canDelete?: boolean
  /** Users who could be added as coaches (active Admin/Coach users not already on the team). */
  coachCandidates?: Candidate[]
  onClickName?: () => void
  onEdit?: () => void
  onDelete?: () => void
  onAddMember?: (userId: number, role: "Member" | "Reserve") => Promise<void> | void
  onRemoveMember?: (userId: number) => Promise<void> | void
  onToggleMemberRole?: (userId: number, currentRole: "Member" | "Reserve") => Promise<void> | void
  onAddCoach?: (userId: number) => Promise<void> | void
  onRemoveCoach?: (userId: number) => Promise<void> | void
  footer?: ReactNode
}

export function TeamCard({
  team,
  memberCap = 3,
  reserveCap = 1,
  canManage,
  canManageCoaches,
  canDelete,
  coachCandidates = [],
  onClickName,
  onEdit,
  onDelete,
  onAddMember,
  onRemoveMember,
  onToggleMemberRole,
  onAddCoach,
  onRemoveCoach,
  footer,
}: Props) {
  const primary = useMemo(
    () => team.members.filter((m) => m.role_in_team === "Member"),
    [team.members],
  )
  const reserve = useMemo(
    () => team.members.filter((m) => m.role_in_team === "Reserve"),
    [team.members],
  )
  const meta = [team.institution, team.description].filter(Boolean).join(" · ")

  return (
    <div className="card">
      <div className="flex items-start justify-between gap-3">
        <h3 className="card-title flex-1">
          {onClickName ? (
            <button
              type="button"
              onClick={onClickName}
              className="text-left hover:underline"
            >
              {team.name}
            </button>
          ) : (
            team.name
          )}
        </h3>
        <div className="flex items-center gap-1">
          {canManage && onEdit && (
            <button type="button" onClick={onEdit} title="Edit team" className="btn btn-icon">
              ✎
            </button>
          )}
          {canDelete && onDelete && (
            <button
              type="button"
              onClick={onDelete}
              title="Delete team"
              className="btn btn-icon btn-danger"
            >
              ×
            </button>
          )}
        </div>
      </div>

      {meta && <div className="card-meta">{meta}</div>}

      <PersonSection
        title={`Members ${primary.length}/${memberCap}`}
        capFilled={primary.length}
        cap={memberCap}
        capVariant="member"
        rows={primary}
        emptyMessage="No members yet."
        canManage={canManage}
        showRoleToggle
        roleToggleTo="Reserve"
        onToggleRole={onToggleMemberRole}
        onRemove={onRemoveMember}
      />

      <PersonSection
        title={`Reserve ${reserve.length}/${reserveCap}`}
        capFilled={reserve.length}
        cap={reserveCap}
        capVariant="reserve"
        rows={reserve}
        emptyMessage="No reserve yet."
        canManage={canManage}
        showRoleToggle
        roleToggleTo="Member"
        onToggleRole={onToggleMemberRole}
        onRemove={onRemoveMember}
      />

      {canManage && onAddMember && (
        <MemberPicker
          teamId={team.id}
          canAddMember={primary.length < memberCap}
          canAddReserve={reserve.length < reserveCap}
          onAdd={onAddMember}
        />
      )}

      <div>
        <div className="card-section-h">Coaches</div>
        <ul className="space-y-1">
          {team.coaches.length === 0 && (
            <li className="text-[12px] text-[color:var(--c-muted)]">
              No coaches yet.
            </li>
          )}
          {team.coaches.map((c) => (
            <li
              key={c.id}
              className="flex items-center gap-2 text-[13px]"
            >
              <span className="flex-1">{c.name}</span>
              <Pill value={c.role} />
              {canManageCoaches && onRemoveCoach && (
                <button
                  type="button"
                  className="btn btn-icon btn-danger"
                  title="Remove coach"
                  onClick={() => onRemoveCoach(c.id)}
                >
                  ×
                </button>
              )}
            </li>
          ))}
        </ul>
        {canManageCoaches && onAddCoach && coachCandidates.length > 0 && (
          <AddCoachRow candidates={coachCandidates} onAdd={onAddCoach} />
        )}
      </div>

      {footer && <div className="card-footer">{footer}</div>}
    </div>
  )
}

function PersonSection({
  title,
  capFilled,
  cap,
  capVariant,
  rows,
  emptyMessage,
  canManage,
  showRoleToggle,
  roleToggleTo,
  onToggleRole,
  onRemove,
}: {
  title: string
  capFilled: number
  cap: number
  capVariant: "member" | "reserve"
  rows: Team["members"]
  emptyMessage: string
  canManage?: boolean
  showRoleToggle?: boolean
  roleToggleTo?: "Member" | "Reserve"
  onToggleRole?: (uid: number, current: "Member" | "Reserve") => Promise<void> | void
  onRemove?: (uid: number) => Promise<void> | void
}) {
  return (
    <div>
      <div className="card-section-h">{title}</div>
      <div className="cap-bar">
        {Array.from({ length: cap }).map((_, i) => (
          <div
            key={i}
            className={
              i < capFilled
                ? capVariant === "member"
                  ? "cap-slot filled"
                  : "cap-slot filled-reserve"
                : "cap-slot"
            }
          />
        ))}
      </div>
      <ul className="mt-2 space-y-1">
        {rows.length === 0 && (
          <li className="text-[12px] text-[color:var(--c-muted)]">{emptyMessage}</li>
        )}
        {rows.map((m) => (
          <li key={m.id} className="flex items-center gap-2 text-[13px]">
            <span className="flex-1">{m.name}</span>
            {m.handle && <Tag>{m.handle}</Tag>}
            {canManage && showRoleToggle && onToggleRole && roleToggleTo && (
              <button
                type="button"
                className="btn btn-icon"
                title={`Make ${roleToggleTo}`}
                onClick={() => onToggleRole(m.id, m.role_in_team)}
              >
                ⇅
              </button>
            )}
            {canManage && onRemove && (
              <button
                type="button"
                className="btn btn-icon btn-danger"
                title="Remove"
                onClick={() => onRemove(m.id)}
              >
                ×
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}

function AddCoachRow({
  candidates,
  onAdd,
}: {
  candidates: Candidate[]
  onAdd: (userId: number) => Promise<void> | void
}) {
  const [userId, setUserId] = useState<number | "">("")
  const [busy, setBusy] = useState(false)

  async function submit() {
    if (!userId) return
    setBusy(true)
    try {
      await onAdd(userId as number)
      setUserId("")
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex items-center gap-1 mt-2">
      <select
        className="filter-control flex-1 min-w-0"
        value={userId}
        onChange={(e) => setUserId(e.target.value ? Number(e.target.value) : "")}
      >
        <option value="">+ Add coach…</option>
        {candidates.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name}
          </option>
        ))}
      </select>
      <button
        type="button"
        className="btn btn-sm"
        onClick={submit}
        disabled={!userId || busy}
      >
        Add
      </button>
    </div>
  )
}
