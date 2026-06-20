import { useEffect, useState } from "react"
import { toast } from "sonner"
import { Modal } from "@/components/common/Modal"
import { contestsService } from "@/services/contests"
import { ApiError } from "@/lib/api"
import type { ContestMemberEntry, MemberStatus } from "@/types/contest"

const STATUSES: MemberStatus[] = ["Not started", "Attempted", "Completed"]

export function ReflectionModal({
  open,
  onClose,
  contestId,
  contestName,
  initial,
  onSaved,
}: {
  open: boolean
  onClose: () => void
  contestId: number | null
  contestName: string
  initial: ContestMemberEntry | null
  onSaved?: () => void
}) {
  const [status, setStatus] = useState<MemberStatus>("Not started")
  const [solved, setSolved] = useState("")
  const [feedback, setFeedback] = useState("")
  const [mistakes, setMistakes] = useState("")
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!open) return
    setStatus(initial?.status ?? "Not started")
    setSolved(initial?.solved_count != null ? String(initial.solved_count) : "")
    setFeedback(initial?.feedback ?? "")
    setMistakes(initial?.mistakes ?? "")
  }, [open, initial])

  async function onSubmit() {
    if (contestId == null) return
    setSaving(true)
    try {
      await contestsService.saveEntry(contestId, {
        status,
        solved_count: solved ? Number(solved) : 0,
        feedback: feedback.trim() || null,
        mistakes: mistakes.trim() || null,
      })
      toast.success("Reflection saved")
      onSaved?.()
      onClose()
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Save failed")
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="My status & reflection"
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
            {saving ? "Saving…" : "Save"}
          </button>
        </>
      }
    >
      <p className="text-[12px] text-[color:var(--c-muted)] mb-3">{contestName}</p>
      <div className="space-y-3">
        <div>
          <label className="form-label">Status</label>
          <select
            className="form-control"
            value={status}
            onChange={(e) => setStatus(e.target.value as MemberStatus)}
          >
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="form-label">Problems solved</label>
          <input
            type="number"
            min={0}
            className="form-control"
            placeholder="e.g. 3"
            value={solved}
            onChange={(e) => setSolved(e.target.value)}
          />
        </div>
        <div>
          <label className="form-label">How did it go?</label>
          <textarea
            className="form-control"
            rows={3}
            placeholder="What you felt about this contest…"
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
          />
        </div>
        <div>
          <label className="form-label">Mistakes made</label>
          <textarea
            className="form-control"
            rows={3}
            placeholder="What went wrong / what to improve…"
            value={mistakes}
            onChange={(e) => setMistakes(e.target.value)}
          />
        </div>
      </div>
    </Modal>
  )
}
