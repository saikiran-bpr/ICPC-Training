import { useEffect, useState } from "react"
import { useForm } from "react-hook-form"
import { toast } from "sonner"
import { Modal } from "@/components/common/Modal"
import { teamsService, type TeamWrite } from "@/services/teams"
import { ApiError } from "@/lib/api"
import type { Team } from "@/types/team"

type FormShape = {
  name: string
  institution: string
  description: string
}

export function TeamModal({
  open,
  onClose,
  initial,
  onSaved,
}: {
  open: boolean
  onClose: () => void
  initial?: Team | null
  onSaved?: (t: Team) => void
}) {
  const [saving, setSaving] = useState(false)
  const { register, handleSubmit, reset, formState: { errors } } = useForm<FormShape>({
    defaultValues: {
      name: initial?.name ?? "",
      institution: initial?.institution ?? "",
      description: initial?.description ?? "",
    },
  })

  useEffect(() => {
    if (open) {
      reset({
        name: initial?.name ?? "",
        institution: initial?.institution ?? "",
        description: initial?.description ?? "",
      })
    }
  }, [open, initial, reset])

  async function onSubmit(values: FormShape) {
    setSaving(true)
    try {
      const payload: TeamWrite = {
        name: values.name.trim(),
        institution: values.institution.trim() || null,
        description: values.description.trim() || null,
      }
      const saved = initial
        ? await teamsService.update(initial.id, payload)
        : await teamsService.create(payload)
      toast.success(initial ? "Team updated" : "Team created")
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
      title={initial ? "Edit team" : "New team"}
      size="sm"
      footer={
        <>
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
          <button
            type="submit"
            form="team-form"
            className="btn btn-primary"
            disabled={saving}
          >
            {saving ? "Saving…" : "Save"}
          </button>
        </>
      }
    >
      <form id="team-form" onSubmit={handleSubmit(onSubmit)} className="space-y-3">
        <div>
          <label className="form-label">Team Name</label>
          <input
            className="form-control"
            {...register("name", { required: "Required" })}
          />
          {errors.name && <p className="form-error">{errors.name.message}</p>}
        </div>
        <div>
          <label className="form-label">Institution</label>
          <input className="form-control" {...register("institution")} />
        </div>
        <div>
          <label className="form-label">Description</label>
          <textarea className="form-control" {...register("description")} />
        </div>
      </form>
    </Modal>
  )
}
