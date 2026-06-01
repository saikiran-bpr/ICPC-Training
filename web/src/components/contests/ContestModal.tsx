import { useEffect, useState } from "react"
import { useForm } from "react-hook-form"
import { toast } from "sonner"
import { Modal } from "@/components/common/Modal"
import { useFetch } from "@/hooks/useFetch"
import { metaService } from "@/services/meta"
import { contestsService, type ContestWrite } from "@/services/contests"
import { ApiError } from "@/lib/api"
import type { ContestSummary } from "@/types/contest"

type FormShape = {
  name: string
  platform: string
  contest_type: string
  contest_year: string
  url: string
  notes: string
}

export function ContestModal({
  open,
  onClose,
  initial,
  onSaved,
}: {
  open: boolean
  onClose: () => void
  initial?: ContestSummary | null
  onSaved?: (c: ContestSummary) => void
}) {
  const [saving, setSaving] = useState(false)
  const meta = useFetch((s) => metaService.get({ signal: s }), [])

  const { register, handleSubmit, reset, formState: { errors } } = useForm<FormShape>({
    defaultValues: {
      name: "",
      platform: "",
      contest_type: "",
      contest_year: "",
      url: "",
      notes: "",
    },
  })

  useEffect(() => {
    if (open) {
      reset({
        name: initial?.name ?? "",
        platform: initial?.platform ?? "",
        contest_type: initial?.contest_type ?? "",
        contest_year: initial?.contest_year != null ? String(initial.contest_year) : "",
        url: initial?.url ?? "",
        notes: initial?.notes ?? "",
      })
    }
  }, [open, initial, reset])

  async function onSubmit(values: FormShape) {
    setSaving(true)
    try {
      const payload: ContestWrite = {
        name: values.name.trim(),
        platform: values.platform || null,
        contest_type: values.contest_type || null,
        contest_year: values.contest_year ? Number(values.contest_year) : null,
        url: values.url.trim() || null,
        notes: values.notes.trim() || null,
      }
      const saved = initial
        ? await contestsService.update(initial.id, payload)
        : await contestsService.create(payload)
      toast.success(initial ? "Contest updated" : "Contest created")
      onSaved?.(saved)
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
      title={initial ? "Edit contest" : "New contest"}
      size="sm"
      footer={
        <>
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
          <button
            type="submit"
            form="contest-form"
            className="btn btn-primary"
            disabled={saving}
          >
            {saving ? "Saving…" : "Save"}
          </button>
        </>
      }
    >
      <form id="contest-form" onSubmit={handleSubmit(onSubmit)} className="space-y-3">
        <div>
          <label className="form-label">Name</label>
          <input
            className="form-control"
            {...register("name", { required: "Required" })}
          />
          {errors.name && <p className="form-error">{errors.name.message}</p>}
        </div>
        <div className="form-grid">
          <div>
            <label className="form-label">Platform</label>
            <select className="form-control" {...register("platform")}>
              <option value="">—</option>
              {meta.data?.platforms.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="form-label">Contest Type</label>
            <select className="form-control" {...register("contest_type")}>
              <option value="">—</option>
              {meta.data?.contest_types.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="form-label">Year</label>
            <input
              type="number"
              className="form-control"
              {...register("contest_year")}
            />
          </div>
          <div>
            <label className="form-label">URL</label>
            <input className="form-control" {...register("url")} />
          </div>
        </div>
        <div>
          <label className="form-label">Notes</label>
          <textarea className="form-control" {...register("notes")} />
        </div>
      </form>
    </Modal>
  )
}
