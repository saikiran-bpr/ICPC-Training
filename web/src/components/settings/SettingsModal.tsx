import { useState } from "react"
import { useForm } from "react-hook-form"
import { toast } from "sonner"
import { Modal } from "@/components/common/Modal"
import { useAuth } from "@/contexts/AuthContext"
import { usersService } from "@/services/users"
import { authService } from "@/services/auth"
import { ApiError } from "@/lib/api"

type ProfileForm = {
  name: string
  email: string
  handle: string
  institution: string
  year_of_study: number | ""
}

type PasswordForm = {
  current_password: string
  new_password: string
}

export function SettingsModal({
  open,
  onClose,
}: {
  open: boolean
  onClose: () => void
}) {
  const { user, refresh } = useAuth()
  if (!user) return null

  return (
    <Modal open={open} onClose={onClose} title="Settings" size="sm">
      <ProfileSection user={user} onSaved={refresh} />
      <hr className="form-hr" />
      <PasswordSection />
    </Modal>
  )
}

function ProfileSection({
  user,
  onSaved,
}: {
  user: NonNullable<ReturnType<typeof useAuth>["user"]>
  onSaved: () => Promise<void>
}) {
  const isContestant = user.role === "Contestant"
  const [saving, setSaving] = useState(false)

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ProfileForm>({
    defaultValues: {
      name: user.name,
      email: user.email,
      handle: user.handle ?? "",
      institution: user.institution ?? "",
      year_of_study: user.year_of_study ?? "",
    },
  })

  async function onSubmit(values: ProfileForm) {
    setSaving(true)
    try {
      await usersService.update(user.id, {
        name: values.name,
        handle: values.handle.trim() || null,
        institution: values.institution.trim() || null,
        year_of_study:
          typeof values.year_of_study === "number" ? values.year_of_study : null,
      })
      await onSaved()
      toast.success("Profile saved")
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not save")
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
      <div className="form-grid">
        <div className="full">
          <label className="form-label">Name</label>
          <input
            className="form-control"
            {...register("name", { required: "Name is required" })}
          />
          {errors.name && <p className="form-error">{errors.name.message}</p>}
        </div>
        <div className="full">
          <label className="form-label">Email</label>
          <input
            className="form-control"
            disabled
            {...register("email")}
          />
          <p className="form-hint">Email can only be changed by an Admin.</p>
        </div>
        <div>
          <label className="form-label">Codeforces handle</label>
          <input className="form-control" {...register("handle")} />
        </div>
        <div>
          <label className="form-label">Institution</label>
          <input className="form-control" {...register("institution")} />
        </div>
        {isContestant && (
          <div>
            <label className="form-label">Year of study</label>
            <input
              type="number"
              min={1}
              max={10}
              className="form-control"
              {...register("year_of_study", {
                setValueAs: (v) => (v === "" || v == null ? "" : Number(v)),
              })}
            />
          </div>
        )}
      </div>
      <div className="flex justify-end">
        <button type="submit" className="btn btn-primary" disabled={saving}>
          {saving ? "Saving…" : "Save profile"}
        </button>
      </div>
    </form>
  )
}

function PasswordSection() {
  const [saving, setSaving] = useState(false)
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<PasswordForm>({
    defaultValues: { current_password: "", new_password: "" },
  })

  async function onSubmit(values: PasswordForm) {
    setSaving(true)
    try {
      await authService.changePassword({
        current_password: values.current_password,
        new_password: values.new_password,
        confirm_password: values.new_password,
      })
      reset()
      toast.success("Password updated")
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not update")
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
      <h3 className="text-[13px] font-medium uppercase tracking-wider text-[color:var(--c-muted)]">
        Change password
      </h3>
      <div className="form-grid">
        <div className="full">
          <label className="form-label">Current password</label>
          <input
            type="password"
            autoComplete="current-password"
            className="form-control"
            {...register("current_password", { required: "Required" })}
          />
          {errors.current_password && (
            <p className="form-error">{errors.current_password.message}</p>
          )}
        </div>
        <div className="full">
          <label className="form-label">New password (min 8)</label>
          <input
            type="password"
            autoComplete="new-password"
            className="form-control"
            {...register("new_password", {
              required: "Required",
              minLength: { value: 8, message: "At least 8 characters" },
            })}
          />
          {errors.new_password && (
            <p className="form-error">{errors.new_password.message}</p>
          )}
        </div>
      </div>
      <div className="flex justify-end">
        <button type="submit" className="btn btn-primary" disabled={saving}>
          {saving ? "Saving…" : "Update password"}
        </button>
      </div>
    </form>
  )
}
