import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react"
import { authService } from "@/services/auth"
import type { LoginInput, SignupInput, SignupResponse } from "@/types/auth"
import type { User, UserRole } from "@/types/user"

type AuthState = {
  user: User | null
  role: UserRole | null
  isLoading: boolean
  isAuthenticated: boolean
  login: (input: LoginInput) => Promise<User>
  signup: (input: SignupInput) => Promise<SignupResponse>
  logout: () => Promise<void>
  refresh: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const refresh = useCallback(async () => {
    setIsLoading(true)
    try {
      const me = await authService.me()
      setUser(me.authenticated ? me.user : null)
    } catch {
      setUser(null)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const login = useCallback(async (input: LoginInput) => {
    const u = await authService.login(input)
    setUser(u)
    return u
  }, [])

  const signup = useCallback(async (input: SignupInput) => {
    // Signup creates a pending request — admin must approve before login.
    // We deliberately do NOT update user state here.
    return await authService.signup(input)
  }, [])

  const logout = useCallback(async () => {
    await authService.logout()
    setUser(null)
  }, [])

  const value: AuthState = {
    user,
    role: user?.role ?? null,
    isLoading,
    isAuthenticated: !!user,
    login,
    signup,
    logout,
    refresh,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error("useAuth must be used inside <AuthProvider>")
  }
  return ctx
}
