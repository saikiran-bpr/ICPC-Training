import { useEffect, useMemo, useState } from "react"
import { toast } from "sonner"
import { Modal } from "@/components/common/Modal"
import { MultiSelect, type MultiSelectOption } from "@/components/common/MultiSelect"
import { useFetch } from "@/hooks/useFetch"
import { assignmentService } from "@/services/assignment"
import { bankService } from "@/services/bank"
import { contestsService } from "@/services/contests"
import { ApiError } from "@/lib/api"

export type AssignTarget =
  | { kind: "problem"; id: number; label: string }
  | { kind: "contest"; id: number; label: string }

export function AssignModal({
  open,
  onClose,
  target,
  onAssigned,
}: {
  open: boolean
  onClose: () => void
  target: AssignTarget | null
  onAssigned?: () => void
}) {
  const opts = useFetch((s) => assignmentService.get({ signal: s }), [])

  const [userIds, setUserIds] = useState<number[]>([])
  const [teamIds, setTeamIds] = useState<number[]>([])
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (open) {
      setUserIds([])
      setTeamIds([])
    }
  }, [open, target])

  const userOptions: MultiSelectOption<unknown>[] = useMemo(
    () =>
      opts.data?.users.map((u) => ({
        id: u.id,
        label: u.name,
        meta: u.role,
        searchHay: `${u.name} ${u.email} ${u.role}`,
        raw: u,
      })) ?? [],
    [opts.data],
  )
  const teamOptions: MultiSelectOption<unknown>[] = useMemo(
    () =>
      opts.data?.teams.map((t) => ({
        id: t.id,
        label: t.name,
        meta: t.institution ?? "",
        searchHay: `${t.name} ${t.institution ?? ""}`,
        raw: t,
      })) ?? [],
    [opts.data],
  )

  async function onSubmit() {
    if (!target) return
    if (userIds.length === 0 && teamIds.length === 0) {
      toast.error("Pick at least one user or team")
      return
    }
    setSaving(true)
    try {
      const payload = {
        assigned_user_ids: userIds.length ? userIds : undefined,
        assigned_team_ids: teamIds.length ? teamIds : undefined,
      }
      if (target.kind === "problem") {
        await bankService.assignProblem(target.id, payload)
      } else {
        await contestsService.assign(target.id, payload)
      }
      toast.success("Assigned")
      onAssigned?.()
      onClose()
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Assign failed")
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={target?.kind === "contest" ? "Assign contest" : "Assign problem"}
      size="sm"
      footer={
        <>
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-primary"
            disabled={saving}
            onClick={onSubmit}
          >
            {saving ? "Assigning…" : "Assign"}
          </button>
        </>
      }
    >
      {target && (
        <p className="text-[12px] text-[color:var(--c-muted)] mb-3">
          {target.label}
        </p>
      )}
      <div className="space-y-3">
        <div>
          <label className="form-label">Assign to users</label>
          <MultiSelect
            options={userOptions}
            selectedIds={userIds}
            onChange={setUserIds}
            placeholder="Search users…"
          />
        </div>
        <div>
          <label className="form-label">Assign to teams</label>
          <MultiSelect
            options={teamOptions}
            selectedIds={teamIds}
            onChange={setTeamIds}
            placeholder="Search teams…"
          />
        </div>
        <p className="form-hint">
          {target?.kind === "contest"
            ? "Every problem in the contest will be assigned to the chosen users/teams."
            : "The problem is added to the chosen users/teams; the bank entry stays."}
        </p>
      </div>
    </Modal>
  )
}
