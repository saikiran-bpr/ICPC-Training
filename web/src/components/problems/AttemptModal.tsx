import { useEffect, useState } from "react"
import { useForm } from "react-hook-form"
import { toast } from "sonner"
import { Modal } from "@/components/common/Modal"
import { useFetch } from "@/hooks/useFetch"
import { metaService } from "@/services/meta"
import { problemsService, type AttemptInput } from "@/services/problems"
import { ApiError } from "@/lib/api"
import type { Problem } from "@/types/problem"

type FormShape = {
  attempt_status: string
  attempt_phase: string
  problem_faced: string
  time_spent_min: string
  notes: string
}

export function AttemptModal({
  open,
  onClose,
  problem,
  onSaved,
}: {
  open: boolean
  onClose: () => void
  problem: Problem | null
  onSaved?: () => void
}) {
  const meta = useFetch((s) => metaService.get({ signal: s }), [])
  const [saving, setSaving] = useState(false)

  const { register, handleSubmit, watch, reset, formState: { errors } } = useForm<FormShape>({
    defaultValues: {
      attempt_status: "TODO",
      attempt_phase: "During Contest",
      problem_faced: "No Problem Faced",
      time_spent_min: "",
      notes: "",
    },
  })

  useEffect(() => {
    if (!open || !problem) return
    const a = problem.my_attempt
    reset({
      attempt_status: a?.attempt_status ?? "TODO",
      attempt_phase: a?.attempt_phase ?? "During Contest",
      problem_faced: a?.problem_faced ?? "No Problem Faced",
      time_spent_min: a?.time_spent_min != null ? String(a.time_spent_min) : "",
      notes: a?.notes ?? "",
    })
  }, [open, problem, reset])

  const status = watch("attempt_status")
  const isAccepted = status === "Accepted"

  async function onSubmit(values: FormShape) {
    if (!problem) return
    if (isAccepted) {
      if (!values.time_spent_min || !values.notes.trim()) {
        toast.error("Time Spent and Notes are required when marking Accepted")
        return
      }
    }
    setSaving(true)
    try {
      const payload: AttemptInput = {
        attempt_status: values.attempt_status,
        attempt_phase: isAccepted ? values.attempt_phase : null,
        problem_faced: values.problem_faced || null,
        time_spent_min: values.time_spent_min ? Number(values.time_spent_min) : null,
        notes: values.notes.trim() || null,
      }
      await problemsService.updateAttempt(problem.id, payload)
      toast.success("Attempt saved")
      onSaved?.()
      onClose()
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Save failed")
    } finally {
      setSaving(false)
    }
  }

  if (!problem) return null

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Update your attempt"
      size="sm"
      footer={
        <>
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
          <button
            type="submit"
            form="attempt-form"
            className="btn btn-primary"
            disabled={saving}
          >
            {saving ? "Saving…" : "Save"}
          </button>
        </>
      }
    >
      <p className="text-[12px] text-[color:var(--c-muted)] mb-3">{problem.name}</p>

      {isAccepted && (
        <div className="form-amber-box">
          Marking <strong>Accepted</strong> requires both Time Spent and Notes.
        </div>
      )}

      <form id="attempt-form" onSubmit={handleSubmit(onSubmit)} className="space-y-3">
        <div>
          <label className="form-label">Attempt Status</label>
          <select className="form-control" {...register("attempt_status")}>
            {meta.data?.attempt_statuses.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="form-label">Problem Faced</label>
          <select className="form-control" {...register("problem_faced")}>
            {meta.data?.problem_faced.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </div>
        {isAccepted && (
          <div>
            <label className="form-label">When did you solve this?</label>
            <select className="form-control" {...register("attempt_phase")}>
              {meta.data?.attempt_phases.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
            <p className="form-hint">Required for Accepted.</p>
          </div>
        )}
        <div>
          <label className="form-label">Time Spent (minutes)</label>
          <input
            type="number"
            min={0}
            className="form-control"
            placeholder="e.g. 25"
            {...register("time_spent_min", {
              required: isAccepted ? "Required when Accepted" : false,
            })}
          />
          {errors.time_spent_min && (
            <p className="form-error">{errors.time_spent_min.message}</p>
          )}
        </div>
        <div>
          <label className="form-label">Notes / Learning</label>
          <textarea
            className="form-control"
            placeholder="What you learned, key insight, blockers…"
            {...register("notes", {
              required: isAccepted ? "Required when Accepted" : false,
            })}
          />
          {errors.notes && <p className="form-error">{errors.notes.message}</p>}
        </div>
      </form>
    </Modal>
  )
}
