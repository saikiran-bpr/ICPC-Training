import { useEffect, useState } from "react"

/**
 * Returns a debounced copy of `value` that only updates after `delayMs` have
 * passed without `value` changing. Useful for search inputs so you fetch /
 * filter on a settled value instead of on every keystroke.
 *
 *   const [q, setQ] = useState("")
 *   const debouncedQ = useDebouncedValue(q, 300)
 *   useEffect(() => { search(debouncedQ) }, [debouncedQ])
 */
export function useDebouncedValue<T>(value: T, delayMs = 300): T {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delayMs)
    return () => clearTimeout(id)
  }, [value, delayMs])

  return debounced
}
