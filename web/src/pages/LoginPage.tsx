import { useForm } from "react-hook-form"
import { Link, useLocation, useNavigate } from "react-router-dom"
import { toast } from "sonner"
import type { LoginInput } from "@/types/auth"
import { useAuth } from "@/contexts/AuthContext"
import { ApiError } from "@/lib/api"

const DEMO_ACCOUNTS = [
  { role: "Admin", email: "admin@example.com", password: "admin@123" },
  { role: "Coach", email: "coach@example.com", password: "coach@123" },
  { role: "Contestant", email: "user@example.com", password: "user@123" },
] as const

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from =
    (location.state as { from?: { pathname?: string } } | null)?.from?.pathname ??
    "/"

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<LoginInput>({
    defaultValues: { email: "", password: "" },
  })

  async function onSubmit(values: LoginInput) {
    try {
      const user = await login(values)
      toast.success(`Welcome back, ${user.name}`)
      navigate(from, { replace: true })
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.message : "Login failed. Try again."
      toast.error(msg)
    }
  }

  async function quickLogin(acct: (typeof DEMO_ACCOUNTS)[number]) {
    setValue("email", acct.email)
    setValue("password", acct.password)
    await onSubmit({ email: acct.email, password: acct.password })
  }

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <h1>Sign in</h1>
        <p className="lede">Welcome back. Enter your email and password.</p>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
          <div>
            <label htmlFor="email" className="auth-label">Email</label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              placeholder="you@example.com"
              className="auth-input"
              {...register("email", {
                required: "Email is required",
                pattern: {
                  value: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
                  message: "Enter a valid email",
                },
              })}
            />
            {errors.email && (
              <p className="text-[12px] text-[color:var(--c-red)] mt-1">
                {errors.email.message}
              </p>
            )}
          </div>

          <div>
            <label htmlFor="password" className="auth-label">Password</label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              className="auth-input"
              {...register("password", { required: "Password is required" })}
            />
            {errors.password && (
              <p className="text-[12px] text-[color:var(--c-red)] mt-1">
                {errors.password.message}
              </p>
            )}
          </div>

          <button
            type="submit"
            className="auth-button mt-2"
            disabled={isSubmitting}
          >
            {isSubmitting ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <p className="auth-foot">
          New here?{" "}
          <Link to="/signup" className="auth-link">
            Create an account
          </Link>
        </p>

        <div className="demo-creds">
          <div className="demo-creds-head">
            <span className="demo-creds-title">Demo accounts</span>
            <span className="demo-creds-hint">click a role to sign in</span>
          </div>
          <div className="demo-creds-list">
            {DEMO_ACCOUNTS.map((acct) => (
              <button
                key={acct.role}
                type="button"
                className="demo-cred"
                onClick={() => quickLogin(acct)}
                disabled={isSubmitting}
              >
                <span
                  className={`demo-badge demo-badge--${acct.role.toLowerCase()}`}
                >
                  {acct.role}
                </span>
                <span className="demo-cred-info">
                  <span className="demo-cred-email">{acct.email}</span>
                  <span className="demo-cred-pass">{acct.password}</span>
                </span>
                <span className="demo-cred-go" aria-hidden="true">
                  →
                </span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
