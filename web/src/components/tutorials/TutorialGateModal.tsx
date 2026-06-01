import { useState } from "react"
import { toast } from "sonner"
import { Modal } from "@/components/common/Modal"
import { tutorialsService } from "@/services/tutorials"
import { ApiError } from "@/lib/api"
import type { TutorialStatus } from "@/types/tutorial"

export function TutorialGateModal({
  open,
  onClose,
  status,
}: {
  open: boolean
  onClose: () => void
  status: TutorialStatus | null
}) {
  const [busy, setBusy] = useState(false)
  if (!status) return null

  async function confirm() {
    setBusy(true)
    try {
      await tutorialsService.unlock(
        status!.problem_id,
        status!.time_threshold_minutes,
      )
      toast.success("Tutorial unlocked")
      window.open(
        tutorialsService.viewUrl(status!.problem_id, "student"),
        "_blank",
        "noopener",
      )
      onClose()
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Failed")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="💡 AI Coach"
      size="sm"
      footer={
        <>
          <button type="button" className="btn" onClick={onClose}>
            Not yet
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={confirm}
            disabled={busy}
          >
            {busy ? "Unlocking…" : "Yes, open the tutorial"}
          </button>
        </>
      }
    >
      <div className="space-y-3 text-[13px]">
        <p>
          Have you spent enough time wrestling with this problem? The Socratic
          tutorial works best after you've genuinely tried.
        </p>
        <div className="form-amber-box">
          We recommend at least <strong>{status.time_threshold_minutes}{" "}
          minutes</strong> for a{" "}
          <strong>{status.difficulty ?? "this"}</strong> problem before opening
          the tutorial.
        </div>
        <p className="text-[12px] text-[color:var(--c-muted)]">
          Confirming records your time so we don't ask again.
        </p>
      </div>
    </Modal>
  )
}
