import { useCallback, useEffect, useRef, useState } from "react"
import { toast } from "sonner"
import { tutorialsService } from "@/services/tutorials"
import { TutorialPickerModal } from "./TutorialPickerModal"
import { TutorialGateModal } from "./TutorialGateModal"
import { ApiError } from "@/lib/api"
import type { TutorialStatus } from "@/types/tutorial"

/**
 * Renders the right button for a single problem's tutorial based on status,
 * and polls every 5s while the worker is queued/generating.
 *
 * - missing  → "💡 Generate"   (admin/coach can click to start)
 * - queued   → "queued…"
 * - generating → "⏳ Generating…"
 * - failed   → "⚠ Retry"
 * - done     → coach: opens picker (audience choice)
 *              contestant + unlocked: opens student tab directly
 *              contestant + locked: opens time-gate modal
 */
export function AITutorialCell({ problemId }: { problemId: number }) {
  const [status, setStatus] = useState<TutorialStatus | null>(null)
  const [picking, setPicking] = useState(false)
  const [gating, setGating] = useState(false)
  const pollRef = useRef<number | null>(null)

  const fetchStatus = useCallback(
    async (signal?: AbortSignal) => {
      try {
        const s = await tutorialsService.status(problemId, { signal })
        setStatus(s)
        return s
      } catch (e) {
        if ((e as { name?: string })?.name === "AbortError") return null
        return null
      }
    },
    [problemId],
  )

  useEffect(() => {
    const ctrl = new AbortController()
    fetchStatus(ctrl.signal)
    return () => ctrl.abort()
  }, [fetchStatus])

  useEffect(() => {
    // Poll only while transient.
    if (!status) return
    const transient =
      status.tutorial_status === "queued" ||
      status.tutorial_status === "generating"
    if (!transient) {
      if (pollRef.current) {
        window.clearInterval(pollRef.current)
        pollRef.current = null
      }
      return
    }
    if (pollRef.current) return
    pollRef.current = window.setInterval(() => {
      fetchStatus()
    }, 5000)
    return () => {
      if (pollRef.current) {
        window.clearInterval(pollRef.current)
        pollRef.current = null
      }
    }
  }, [status, fetchStatus])

  async function startGeneration() {
    try {
      await tutorialsService.generate(problemId)
      toast.success("Generation queued")
      fetchStatus()
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Failed to queue")
    }
  }

  function handleClickDone() {
    if (!status) return
    if (status.is_contestant) {
      if (status.unlocked) {
        window.open(
          tutorialsService.viewUrl(problemId, "student"),
          "_blank",
          "noopener",
        )
      } else {
        setGating(true)
      }
    } else {
      setPicking(true)
    }
  }

  if (!status) {
    return <span className="text-[11px] text-[color:var(--c-muted)]">…</span>
  }

  const s = status.tutorial_status

  if (s === "missing") {
    return status.is_contestant ? (
      <span className="text-[11px] text-[color:var(--c-muted)]">—</span>
    ) : (
      <button type="button" className="btn btn-sm" onClick={startGeneration}>
        💡 Generate
      </button>
    )
  }
  if (s === "queued") {
    return (
      <span className="text-[11px] text-[color:var(--c-muted)]">queued…</span>
    )
  }
  if (s === "generating") {
    return (
      <span className="text-[11px] text-[color:var(--c-accent)]">
        ⏳ Generating…
      </span>
    )
  }
  if (s === "failed") {
    return (
      <button
        type="button"
        className="btn btn-sm btn-danger"
        onClick={startGeneration}
        title={status.error_message ?? "Generation failed"}
      >
        ⚠ Retry
      </button>
    )
  }

  // done
  const label = status.is_contestant ? "💡 AI Coach" : "💡 View"
  return (
    <>
      <button type="button" className="btn btn-sm btn-primary" onClick={handleClickDone}>
        {label}
      </button>
      <TutorialPickerModal
        open={picking}
        onClose={() => setPicking(false)}
        status={status}
      />
      <TutorialGateModal
        open={gating}
        onClose={() => setGating(false)}
        status={status}
      />
    </>
  )
}
