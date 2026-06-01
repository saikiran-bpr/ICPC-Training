import { Modal } from "@/components/common/Modal"
import { tutorialsService } from "@/services/tutorials"
import type { TutorialStatus } from "@/types/tutorial"

export function TutorialPickerModal({
  open,
  onClose,
  status,
}: {
  open: boolean
  onClose: () => void
  status: TutorialStatus | null
}) {
  if (!status) return null

  function openTab(audience: "student" | "teacher") {
    window.open(
      tutorialsService.viewUrl(status!.problem_id, audience),
      "_blank",
      "noopener",
    )
    onClose()
  }

  return (
    <Modal open={open} onClose={onClose} title="💡 AI Tutorial" size="sm">
      <div className="space-y-3">
        {status.key_insight && (
          <div
            className="rounded border p-3 text-[12px]"
            style={{
              borderColor: "var(--c-border)",
              background: "var(--c-panel-2)",
            }}
          >
            <div className="text-[color:var(--c-muted)] uppercase tracking-wider text-[10px] mb-1">
              Key insight
            </div>
            <div>{status.key_insight.slice(0, 200)}</div>
          </div>
        )}

        <div className="flex flex-wrap gap-3 text-[11px] text-[color:var(--c-muted)]">
          {status.rung_count != null && <span>{status.rung_count} rungs</span>}
          {status.mcq_count != null && <span>{status.mcq_count} MCQs</span>}
          {status.snippet_count != null && (
            <span>{status.snippet_count} snippets</span>
          )}
          {status.generated_at && (
            <span>generated {status.generated_at.split("T")[0]}</span>
          )}
        </div>

        <button
          type="button"
          className="btn w-full text-left"
          onClick={() => openTab("student")}
        >
          <div className="flex flex-col items-start">
            <span className="font-medium">👤 Contestant version</span>
            <span className="text-[11px] text-[color:var(--c-muted)]">
              Socratic — hints, answers, full solution stay hidden until you ask.
            </span>
          </div>
        </button>

        <button
          type="button"
          className="btn btn-primary w-full text-left"
          onClick={() => openTab("teacher")}
        >
          <div className="flex flex-col items-start">
            <span className="font-medium">🧑‍🏫 Coach version</span>
            <span className="text-[11px] opacity-80">
              Everything visible inline. Includes "At a glance" summary.
            </span>
          </div>
        </button>
      </div>
    </Modal>
  )
}
