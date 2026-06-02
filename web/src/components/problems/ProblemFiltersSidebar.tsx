import { useEffect, useState } from "react"
import type { Meta } from "@/types/meta"
import type { ProblemFilters } from "@/types/problem"
import type { UserRole } from "@/types/user"
import { MultiFilter, asArr } from "@/components/common/MultiFilter"
import {
  AsyncSearchSelect,
  type SearchSelectItem,
} from "@/components/common/AsyncSearchSelect"
import {
  searchContestants,
  searchAssignableTeams,
} from "@/services/assignmentSearch"

type Props = {
  meta: Meta | null
  filters: ProblemFilters
  onChange: (next: ProblemFilters) => void
  onClear: () => void
  role?: UserRole | null
}

const SORT_KEYS: { value: string; label: string }[] = [
  { value: "date_added", label: "Date added" },
  { value: "name", label: "Name" },
  { value: "rating", label: "Rating" },
  { value: "importance", label: "Importance" },
  { value: "id", label: "Id" },
]

export function ProblemFiltersSidebar({
  meta,
  filters,
  onChange,
  onClear,
  role,
}: Props) {
  const isStaff = role === "Admin" || role === "Coach"
  const [contestant, setContestant] = useState<SearchSelectItem | null>(null)
  const [team, setTeam] = useState<SearchSelectItem | null>(null)

  // Reflect external clears (e.g. the Clear button) in the local pickers.
  useEffect(() => {
    if (filters.assigned_user_id == null) setContestant(null)
  }, [filters.assigned_user_id])
  useEffect(() => {
    if (filters.assigned_team_id == null) setTeam(null)
  }, [filters.assigned_team_id])

  function set<K extends keyof ProblemFilters>(
    key: K,
    value: ProblemFilters[K] | "",
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
      next[key] = value as ProblemFilters[K]
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
        <>
          <div className="space-y-1">
            <label className="filter-label">Assigned to contestant</label>
            <AsyncSearchSelect
              value={contestant}
              search={searchContestants}
              placeholder="Search contestant…"
              onChange={(item) => {
                setContestant(item)
                set("assigned_user_id", item ? item.id : "")
              }}
            />
          </div>
          <div className="space-y-1">
            <label className="filter-label">Assigned to team</label>
            <AsyncSearchSelect
              value={team}
              search={searchAssignableTeams}
              placeholder="Search team…"
              onChange={(item) => {
                setTeam(item)
                set("assigned_team_id", item ? item.id : "")
              }}
            />
          </div>
        </>
      )}

      <MultiFilter
        label="Platform"
        selected={asArr(filters.platform)}
        options={meta?.platforms}
        onChange={(v) => set("platform", v)}
      />
      <MultiFilter
        label="Topic"
        selected={asArr(filters.topic)}
        options={meta?.topics}
        onChange={(v) => set("topic", v)}
      />
      <MultiFilter
        label="Difficulty"
        selected={asArr(filters.difficulty)}
        options={meta?.difficulties}
        onChange={(v) => set("difficulty", v)}
      />
      <MultiFilter
        label="Importance"
        selected={asArr(filters.importance)}
        options={meta?.importance}
        onChange={(v) => set("importance", v)}
      />
      <MultiFilter
        label="Status"
        selected={asArr(filters.status)}
        options={meta?.statuses}
        onChange={(v) => set("status", v)}
      />
      <MultiFilter
        label="Contest Type"
        selected={asArr(filters.contest_type)}
        options={meta?.contest_types}
        onChange={(v) => set("contest_type", v)}
      />

      <div className="space-y-1">
        <label className="filter-label">Rating</label>
        <div className="grid grid-cols-2 gap-2">
          <FilterInput
            type="number"
            placeholder="Min"
            value={filters.rating_min ?? ""}
            onChange={(v) =>
              set("rating_min", v === "" ? "" : Number(v))
            }
          />
          <FilterInput
            type="number"
            placeholder="Max"
            value={filters.rating_max ?? ""}
            onChange={(v) =>
              set("rating_max", v === "" ? "" : Number(v))
            }
          />
        </div>
      </div>

      <div className="space-y-1">
        <label className="filter-label">Sort</label>
        <div className="grid grid-cols-2 gap-2">
          <select
            className="filter-control"
            value={filters.sort ?? "date_added"}
            onChange={(e) => set("sort", e.target.value)}
          >
            {SORT_KEYS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
          <select
            className="filter-control"
            value={filters.order ?? "desc"}
            onChange={(e) => set("order", e.target.value as "asc" | "desc")}
          >
            <option value="desc">Desc</option>
            <option value="asc">Asc</option>
          </select>
        </div>
      </div>

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

function FilterInput({
  type,
  placeholder,
  value,
  onChange,
}: {
  type: "number" | "text"
  placeholder?: string
  value: string | number
  onChange: (v: string) => void
}) {
  return (
    <input
      type={type}
      placeholder={placeholder}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="filter-control"
    />
  )
}
