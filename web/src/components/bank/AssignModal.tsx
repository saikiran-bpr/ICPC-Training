import { useEffect, useState } from "react"
import { toast } from "sonner"
import { Modal } from "@/components/common/Modal"
import {
  AsyncMultiSelect,
  type AsyncMultiSelectItem,
} from "@/components/common/AsyncMultiSelect"
import { searchContestants, searchAssignableTeams } from "@/services/assignmentSearch"
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
  const [selUsers, setSelUsers] = useState<AsyncMultiSelectItem[]>([])
  const [selTeams, setSelTeams] = useState<AsyncMultiSelectItem[]>([])
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!open) return
    setSelUsers([])
    setSelTeams([])
  }, [open, target])

  async function onSubmit() {
    if (!target) return
    if (selUsers.length === 0 && selTeams.length === 0) {
      toast.error("Pick at least one contestant or team")
      return
    }
    setSaving(true)
    try {
      const payload = {
        assigned_user_ids: selUsers.length ? selUsers.map((u) => u.id) : undefined,
        assigned_team_ids: selTeams.length ? selTeams.map((t) => t.id) : undefined,
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
          <label className="form-label">Assign to contestants</label>
          <AsyncMultiSelect
            selected={selUsers}
            onChange={setSelUsers}
            search={searchContestants}
            placeholder="Search contestants by name or handle…"
            emptyMessage="No contestants found"
          />
        </div>
        <div>
          <label className="form-label">Assign to teams</label>
          <AsyncMultiSelect
            selected={selTeams}
            onChange={setSelTeams}
            search={searchAssignableTeams}
            placeholder="Search teams…"
            emptyMessage="No teams found"
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
