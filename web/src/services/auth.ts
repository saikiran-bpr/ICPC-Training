import { api } from "@/lib/api"
import type {
  ChangePasswordInput,
  LoginInput,
  MeResponse,
  SignupInput,
  SignupResponse,
} from "@/types/auth"
import type { User } from "@/types/user"

export const authService = {
  me: () => api.get<MeResponse>("/auth/me"),

  login: (input: LoginInput) => api.post<User>("/auth/login", input),

  signup: (input: SignupInput) => {
    const body = {
      email: input.email,
      password: input.password,
      name: input.name,
      handle: input.handle?.trim() || undefined,
      institution: input.institution?.trim() || undefined,
      year_of_study:
        typeof input.year_of_study === "number" ? input.year_of_study : undefined,
    }
    return api.post<SignupResponse>("/auth/signup", body)
  },

  logout: () => api.post<{ ok: true }>("/auth/logout"),

  changePassword: (input: ChangePasswordInput) =>
    api.post<{ ok: true }>("/auth/password", {
      current_password: input.current_password,
      new_password: input.new_password,
    }),
}
