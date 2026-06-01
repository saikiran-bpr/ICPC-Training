import { api } from "@/lib/api"
import type { User } from "@/types/user"

export const adminService = {
  listRequests: (opts?: { signal?: AbortSignal }) =>
    api.get<User[]>("/admin/requests", opts),

  pendingCount: (opts?: { signal?: AbortSignal }) =>
    api.get<{ count: number }>("/admin/requests/count", opts),

  approve: (uid: number) => api.post<User>(`/admin/requests/${uid}/approve`),

  reject: (uid: number) =>
    api.post<{ ok: true }>(`/admin/requests/${uid}/reject`),
}
