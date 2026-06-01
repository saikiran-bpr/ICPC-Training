import { Link } from "react-router-dom"
import { Button } from "@/components/ui/button"

export function NotFoundPage() {
  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center gap-4">
      <h1 className="text-5xl font-bold tracking-tight">404</h1>
      <p className="text-muted-foreground">This page does not exist.</p>
      <Button asChild>
        <Link to="/">Go home</Link>
      </Button>
    </div>
  )
}
