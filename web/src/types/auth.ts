import type { User } from "./user"

export type LoginInput = {
  email: string
  password: string
}

export type SignupInput = {
  email: string
  password: string
  name: string
  handle?: string
  institution?: string
  year_of_study?: number
}

export type ChangePasswordInput = {
  current_password: string
  new_password: string
  confirm_password: string
}

export type MeResponse =
  | { authenticated: false }
  | { authenticated: true; user: User }

export type SignupResponse = {
  pending: true
  email: string
  message: string
}
