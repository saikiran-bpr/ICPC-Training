import { useEffect, useState, useCallback } from "react"
import { ApiError } from "@/lib/api"

type State<T> = {
  data: T | null
  isLoading: boolean
  error: string | null
}

/**
 * Tiny wrapper around fetch-returning functions.
 *
 *   const { data, isLoading, error, refetch } = useFetch(() => api.get("/problems"))
 *
 * Re-runs whenever any value in `deps` changes. Includes an AbortController so
 * an unmounted component doesn't update state after the request resolves.
 */
export function useFetch<T>(
  fn: (signal: AbortSignal) => Promise<T>,
  deps: unknown[] = [],
) {
  const [state, setState] = useState<State<T>>({
    data: null,
    isLoading: true,
    error: null,
  })

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback(fn, deps)

  const load = useCallback(
    (signal: AbortSignal) => {
      setState((s) => ({ ...s, isLoading: true, error: null }))
      run(signal)
        .then((data) => {
          if (signal.aborted) return
          setState({ data, isLoading: false, error: null })
        })
        .catch((err: unknown) => {
          if (signal.aborted || (err as { name?: string })?.name === "AbortError")
            return
          const message =
            err instanceof ApiError ? err.message : "Something went wrong"
          setState({ data: null, isLoading: false, error: message })
        })
    },
    [run],
  )

  useEffect(() => {
    const ctrl = new AbortController()
    load(ctrl.signal)
    return () => ctrl.abort()
  }, [load])

  const refetch = useCallback(() => {
    const ctrl = new AbortController()
    load(ctrl.signal)
  }, [load])

  return { ...state, refetch }
}
