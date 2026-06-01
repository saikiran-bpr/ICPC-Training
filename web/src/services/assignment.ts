import { api } from "@/lib/api"
import type { AssignmentOptions } from "@/types/assignment"

export const assignmentService = {
  get: (opts?: { signal?: AbortSignal }) =>
    api.get<AssignmentOptions>("/assignment-options", { signal: opts?.signal }),
}
