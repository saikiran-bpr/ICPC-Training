import { useEffect, useState } from "react"
import type { Meta } from "@/types/meta"
import type { UserRole } from "@/types/user"
import type { MemberStatus } from "@/types/contest"
import { MultiFilter, asArr } from "@/components/common/MultiFilter"
import {
  AsyncSearchSelect,
  type SearchSelectItem,
} from "@/components/common/AsyncSearchSelect"
import { searchAssignableTeams } from "@/services/assignmentSearch"

export type ContestFilters = {
  platform?: string[]
  contest_type?: string[]
  status?: string[]
  team_id?: number | null
}

const STATUS_OPTIONS: MemberStatus[] = ["Not started", "Attempted", "Completed"]

type Props = {
  meta: Meta | null
  filters: ContestFilters
  onChange: (next: ContestFilters) => void
  onClear: () => void
  role?: UserRole | null
}

export function ContestFiltersSidebar({
  meta,
  filters,
  onChange,
  onClear,
  role,
}: Props) {
  const isStaff = role === "Admin" || role === "Coach"
  const [team, setTeam] = useState<SearchSelectItem | null>(null)

  // Reflect external clears (Clear button) in the local team picker.
  useEffect(() => {
    if (filters.team_id == null) setTeam(null)
  }, [filters.team_id])

  function set<K extends keyof ContestFilters>(
    key: K,
    value: ContestFilters[K] | "",
  ) {
    const next = { ...filters }
    if (
      value === "" ||
      value === undefined ||
      value === null ||
      (Array.isArray(value) && value.length === 0)
    ) {
      delete next[key]
    } else {
      next[key] = value as ContestFilters[K]
    }
    onChange(next)
  }

  return (
    <aside
      className="w-[240px] shrink-0 overflow-y-auto border-r p-4 space-y-4"
      style={{ background: "var(--c-panel)", borderColor: "var(--c-border)" }}
    >
      <h2 className="filter-heading">Filters</h2>

      {isStaff && (
        <div className="space-y-1">
          <label className="filter-label">Assigned to team</label>
          <AsyncSearchSelect
            value={team}
            search={searchAssignableTeams}
            placeholder="Search team…"
            onChange={(item) => {
              setTeam(item)
              set("team_id", item ? item.id : "")
            }}
          />
        </div>
      )}

      <MultiFilter
        label="Platform"
        selected={asArr(filters.platform)}
        options={meta?.platforms}
        onChange={(v) => set("platform", v)}
      />
      <MultiFilter
        label="Contest Type"
        selected={asArr(filters.contest_type)}
        options={meta?.contest_types}
        onChange={(v) => set("contest_type", v)}
      />
      <MultiFilter
        label="My Status"
        selected={asArr(filters.status)}
        options={STATUS_OPTIONS}
        onChange={(v) => set("status", v)}
      />

      <button
        type="button"
        onClick={onClear}
        className="w-full px-3 py-2 mt-2 rounded-md border text-[13px] hover:bg-[color:var(--c-panel-2)] transition-colors"
        style={{ borderColor: "var(--c-border)" }}
      >
        Clear filters
      </button>
    </aside>
  )
}
