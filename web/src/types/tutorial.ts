export type TutorialAudience = "student" | "teacher"

export type TutorialStatus = {
  problem_id: number
  tutorial_exists: boolean
  tutorial_status: "missing" | "queued" | "generating" | "done" | "failed"
  user_role: string
  is_contestant: boolean
  unlocked: boolean
  needs_time_gate: boolean
  time_threshold_minutes: number
  difficulty: string | null
  // Present only when tutorial_status === "done"
  slug?: string
  key_insight?: string | null
  rung_count?: number | null
  mcq_count?: number | null
  snippet_count?: number | null
  generated_at?: string | null
  editorial_found?: boolean
  audiences_available?: TutorialAudience[]
  error_message?: string | null
}
