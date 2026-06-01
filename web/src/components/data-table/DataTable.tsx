import type { ReactNode } from "react"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Skeleton } from "@/components/ui/skeleton"

export type Column<T> = {
  key: string
  header: ReactNode
  cell: (row: T) => ReactNode
  className?: string
}

type Props<T> = {
  columns: Column<T>[]
  data: T[] | null | undefined
  isLoading?: boolean
  emptyMessage?: string
  rowKey: (row: T) => string | number
  toolbar?: ReactNode
}

/**
 * Plain HTML table with loading skeletons and empty state. No sorting,
 * filtering, or pagination — do those server-side via query params (the Flask
 * API already accepts ?sort, ?order, filters, etc.) or with local useState if
 * the dataset is small. Keeping this dumb on purpose.
 */
export function DataTable<T>({
  columns,
  data,
  isLoading,
  emptyMessage = "No results.",
  rowKey,
  toolbar,
}: Props<T>) {
  return (
    <div className="space-y-3">
      {toolbar}

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              {columns.map((c) => (
                <TableHead key={c.key} className={c.className}>
                  {c.header}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={`skel-${i}`}>
                  {columns.map((c) => (
                    <TableCell key={c.key}>
                      <Skeleton className="h-4 w-full" />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : data && data.length > 0 ? (
              data.map((row) => (
                <TableRow key={rowKey(row)}>
                  {columns.map((c) => (
                    <TableCell key={c.key} className={c.className}>
                      {c.cell(row)}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className="h-24 text-center text-muted-foreground"
                >
                  {emptyMessage}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
