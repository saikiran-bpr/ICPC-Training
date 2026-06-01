import { api } from "@/lib/api"
import type { Meta } from "@/types/meta"

export const metaService = {
  get: (opts?: { signal?: AbortSignal }) =>
    api.get<Meta>("/meta", { signal: opts?.signal }),
}
