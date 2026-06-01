import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

export function PlaceholderPage({ title }: { title: string }) {
  return (
    <div className="space-y-4">
      <h1 className="text-3xl font-bold tracking-tight">{title}</h1>
      <Card>
        <CardHeader>
          <CardTitle>Coming soon</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            This view will be implemented in a later phase.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
