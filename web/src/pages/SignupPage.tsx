import { useForm } from "react-hook-form"
import { Link, useNavigate } from "react-router-dom"
import { toast } from "sonner"
import type { SignupInput } from "@/types/auth"
import { useAuth } from "@/contexts/AuthContext"
import { ApiError } from "@/lib/api"

type SignupForm = {
  email: string
  password: string
  name: string
  handle?: string
  institution?: string
  year_of_study: number | ""
}

export function SignupPage() {
  const { signup } = useAuth()
  const navigate = useNavigate()

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<SignupForm>({
    defaultValues: {
      email: "",
      password: "",
      name: "",
      handle: "",
      institution: "",
      year_of_study: "",
    },
  })

  async function onSubmit(values: SignupForm) {
    const payload: SignupInput = {
      ...values,
      year_of_study:
        typeof values.year_of_study === "number" ? values.year_of_study : undefined,
    }
    try {
      const res = await signup(payload)
      toast.success(res.message, { duration: 8000 })
      navigate("/login", { replace: true })
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.message : "Sign-up failed. Try again."
      toast.error(msg)
    }
  }

  return (
    <div className="auth-wrap">
      <div className="auth-card" style={{ width: "min(480px, 92vw)" }}>
        <h1>Request access</h1>
        <p className="lede">
          New contestants sign up here. Your request will be sent to an admin
          for approval — you'll be able to sign in once it's approved.
        </p>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
          <Field
            label="Full name"
            error={errors.name?.message}
          >
            <input
              type="text"
              autoComplete="name"
              className="auth-input"
              {...register("name", { required: "Name is required" })}
            />
          </Field>

          <Field label="Email" error={errors.email?.message}>
            <input
              type="email"
              autoComplete="email"
              className="auth-input"
              {...register("email", {
                required: "Email is required",
                pattern: {
                  value: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
                  message: "Enter a valid email",
                },
              })}
            />
          </Field>

          <Field
            label="Password"
            error={errors.password?.message}
            hint="At least 8 characters."
          >
            <input
              type="password"
              autoComplete="new-password"
              className="auth-input"
              {...register("password", {
                required: "Password is required",
                minLength: {
                  value: 8,
                  message: "Password must be at least 8 characters",
                },
              })}
            />
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Codeforces handle">
              <input
                type="text"
                placeholder="optional"
                className="auth-input"
                {...register("handle")}
              />
            </Field>
            <Field label="Institution">
              <input
                type="text"
                placeholder="optional"
                className="auth-input"
                {...register("institution")}
              />
            </Field>
          </div>

          <Field label="Year of study" error={errors.year_of_study?.message}>
            <input
              type="number"
              min={1}
              max={8}
              placeholder="optional"
              className="auth-input"
              {...register("year_of_study", {
                setValueAs: (v) => (v === "" || v == null ? "" : Number(v)),
                min: { value: 1, message: "Must be between 1 and 8" },
                max: { value: 8, message: "Must be between 1 and 8" },
              })}
            />
          </Field>

          <button
            type="submit"
            className="auth-button mt-2"
            disabled={isSubmitting}
          >
            {isSubmitting ? "Creating…" : "Create account"}
          </button>
        </form>

        <p className="auth-foot">
          Already have an account?{" "}
          <Link to="/login" className="auth-link">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  )
}

function Field({
  label,
  hint,
  error,
  children,
}: {
  label: string
  hint?: string
  error?: string
  children: React.ReactNode
}) {
  return (
    <div>
      <label className="auth-label">{label}</label>
      {children}
      {hint && !error && (
        <p className="text-[11px] text-[color:var(--c-muted)] mt-1">{hint}</p>
      )}
      {error && (
        <p className="text-[12px] text-[color:var(--c-red)] mt-1">{error}</p>
      )}
    </div>
  )
}
