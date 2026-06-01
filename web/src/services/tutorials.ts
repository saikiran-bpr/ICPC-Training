import { api } from "@/lib/api"
import type { TutorialAudience, TutorialStatus } from "@/types/tutorial"

export const tutorialsService = {
  status: (problemId: number, opts?: { signal?: AbortSignal }) =>
    api.get<TutorialStatus>(`/problems/${problemId}/tutorial/status`, {
      signal: opts?.signal,
    }),

  generate: (problemId: number) =>
    api.post<{ message?: string; status?: string }>(
      `/problems/${problemId}/tutorial/generate`,
    ),

  unlock: (problemId: number, claimedMinutes: number) =>
    api.post<{ ok: boolean }>(`/problems/${problemId}/tutorial/unlock`, {
      confirm: true,
      claimed_minutes: claimedMinutes,
    }),

  /** Returns the URL to open in a new tab to view the tutorial HTML. */
  viewUrl: (problemId: number, audience: TutorialAudience): string =>
    `/api/problems/${problemId}/tutorial?audience=${audience}`,

  pdfUrl: (problemId: number, audience: TutorialAudience): string =>
    `/api/problems/${problemId}/tutorial.pdf?audience=${audience}`,
}
