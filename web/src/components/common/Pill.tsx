import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

/**
 * Status / difficulty / importance / role pill. The class name is derived
 * from `value` (spaces and slashes → hyphens) to match the .pill-* CSS rules
 * in index.css. New variants only need a CSS rule, no TS change.
 */
export function Pill({
  value,
  children,
  className,
}: {
  value: string | null | undefined
  children?: ReactNode
  className?: string
}) {
  if (!value) return null
  const slug = value.replace(/[\s/]+/g, "-")
  return (
    <span className={cn("pill", `pill-${slug}`, className)}>
      {children ?? value}
    </span>
  )
}
