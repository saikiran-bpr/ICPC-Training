const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ""

export class ApiError extends Error {
  status: number
  payload: unknown
  constructor(status: number, message: string, payload: unknown) {
    super(message)
    this.status = status
    this.payload = payload
  }
}

type RequestOptions = {
  params?: Record<string, string | number | boolean | undefined | null>
  body?: unknown
  signal?: AbortSignal
  headers?: Record<string, string>
}

async function request<T>(
  method: string,
  path: string,
  opts: RequestOptions = {},
): Promise<T> {
  const url = new URL(`${BASE_URL}/api${path}`, window.location.origin)
  if (opts.params) {
    for (const [k, v] of Object.entries(opts.params)) {
      if (v === undefined || v === null || v === "") continue
      url.searchParams.append(k, String(v))
    }
  }

  const headers: Record<string, string> = {
    Accept: "application/json",
    ...opts.headers,
  }
  let body: BodyInit | undefined
  if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json"
    body = JSON.stringify(opts.body)
  }

  const res = await fetch(url.toString(), {
    method,
    headers,
    body,
    credentials: "include",
    signal: opts.signal,
  })

  const text = await res.text()
  const payload = text ? safeJson(text) : null

  if (!res.ok) {
    const msg =
      (payload && typeof payload === "object" && "error" in payload
        ? String((payload as { error: unknown }).error)
        : null) ?? res.statusText
    throw new ApiError(res.status, msg, payload)
  }
  return payload as T
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

export const api = {
  get: <T>(path: string, opts?: RequestOptions) => request<T>("GET", path, opts),
  post: <T>(path: string, body?: unknown, opts?: RequestOptions) =>
    request<T>("POST", path, { ...opts, body }),
  put: <T>(path: string, body?: unknown, opts?: RequestOptions) =>
    request<T>("PUT", path, { ...opts, body }),
  patch: <T>(path: string, body?: unknown, opts?: RequestOptions) =>
    request<T>("PATCH", path, { ...opts, body }),
  delete: <T>(path: string, opts?: RequestOptions) =>
    request<T>("DELETE", path, opts),
}
