import { useEffect, useState } from "react"
import { useForm } from "react-hook-form"
import { toast } from "sonner"
import { Modal } from "@/components/common/Modal"
import { useFetch } from "@/hooks/useFetch"
import { metaService } from "@/services/meta"
import { usersService, type UserCreate } from "@/services/users"
import { ApiError } from "@/lib/api"
import type { User, UserRole } from "@/types/user"
import colleges from "@/data/colleges.json"

type FormShape = {
  name: string
  email: string
  password: string
  role: UserRole | ""
  handle: string
  institution: string
}

export function UserCreateModal({
  open,
  onClose,
  onSaved,
}: {
  open: boolean
  onClose: () => void
  onSaved?: (u: User) => void
}) {
  const [saving, setSaving] = useState(false)
  const meta = useFetch((s) => metaService.get({ signal: s }), [])
  const { register, handleSubmit, reset, formState: { errors } } = useForm<FormShape>({
    defaultValues: {
      name: "",
      email: "",
      password: "",
      role: "Contestant",
      handle: "",
      institution: "",
    },
  })

  useEffect(() => {
    if (open) reset()
  }, [open, reset])

  async function onSubmit(values: FormShape) {
    if (!values.role) return
    setSaving(true)
    try {
      const payload: UserCreate = {
        email: values.email.trim().toLowerCase(),
        password: values.password,
        name: values.name.trim(),
        role: values.role,
        handle: values.handle.trim() || undefined,
        institution: values.institution.trim() || undefined,
      }
      const saved = await usersService.create(payload)
      toast.success("User created")
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
      title="New user"
      size="sm"
      footer={
        <>
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
          <button
            type="submit"
            form="user-form"
            className="btn btn-primary"
            disabled={saving}
          >
            {saving ? "Creating…" : "Create"}
          </button>
        </>
      }
    >
      <form id="user-form" onSubmit={handleSubmit(onSubmit)} className="space-y-3">
        <div>
          <label className="form-label">Full name</label>
          <input
            className="form-control"
            {...register("name", { required: "Required" })}
          />
          {errors.name && <p className="form-error">{errors.name.message}</p>}
        </div>
        <div>
          <label className="form-label">Email</label>
          <input
            type="email"
            className="form-control"
            {...register("email", {
              required: "Required",
              pattern: { value: /^[^\s@]+@[^\s@]+\.[^\s@]+$/, message: "Invalid email" },
            })}
          />
          {errors.email && <p className="form-error">{errors.email.message}</p>}
        </div>
        <div>
          <label className="form-label">Password (min 8)</label>
          <input
            type="password"
            className="form-control"
            {...register("password", {
              required: "Required",
              minLength: { value: 8, message: "At least 8 characters" },
            })}
          />
          {errors.password && <p className="form-error">{errors.password.message}</p>}
        </div>
        <div>
          <label className="form-label">Role</label>
          <select className="form-control" {...register("role", { required: true })}>
            {meta.data?.user_roles.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="form-label">Codeforces handle</label>
          <input className="form-control" {...register("handle")} />
        </div>
        <div>
          <label className="form-label">Institution</label>
          <select className="form-control" {...register("institution")}>
            <option value="">Select institution</option>
            {colleges.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
      </form>
    </Modal>
  )
}
