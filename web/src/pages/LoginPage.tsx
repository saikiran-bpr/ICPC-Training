import { useForm } from "react-hook-form"
import { Link, useLocation, useNavigate } from "react-router-dom"
import { toast } from "sonner"
import type { LoginInput } from "@/types/auth"
import { useAuth } from "@/contexts/AuthContext"
import { ApiError } from "@/lib/api"

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
      </div>
    </div>
  )
}
