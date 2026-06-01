import type { Meta } from "@/types/meta"
import type { ProblemFilters } from "@/types/problem"

type Props = {
  meta: Meta | null
  filters: ProblemFilters
  onChange: (next: ProblemFilters) => void
  onClear: () => void
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
}: Props) {
  function set<K extends keyof ProblemFilters>(
    key: K,
    value: ProblemFilters[K] | "",
  ) {
    const next = { ...filters }
    if (value === "" || value === undefined || value === null) {
      delete next[key]
    } else {
      next[key] = value as ProblemFilters[K]
    }
    onChange(next)
  }

  return (
    <aside
      className="w-[280px] shrink-0 overflow-y-auto border-r p-4 space-y-4"
      style={{ background: "var(--c-panel)", borderColor: "var(--c-border)" }}
    >
      <h2 className="filter-heading">Filters</h2>

      <FilterSelect
        label="Platform"
        value={filters.platform}
        options={meta?.platforms}
        onChange={(v) => set("platform", v)}
      />
      <FilterSelect
        label="Topic"
        value={filters.topic}
        options={meta?.topics}
        onChange={(v) => set("topic", v)}
      />
      <FilterSelect
        label="Difficulty"
        value={filters.difficulty}
        options={meta?.difficulties}
        onChange={(v) => set("difficulty", v)}
      />
      <FilterSelect
        label="Importance"
        value={filters.importance}
        options={meta?.importance}
        onChange={(v) => set("importance", v)}
      />
      <FilterSelect
        label="Status"
        value={filters.status}
        options={meta?.statuses}
        onChange={(v) => set("status", v)}
      />
      <FilterSelect
        label="Contest Type"
        value={filters.contest_type}
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

function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: string | undefined
  options: string[] | undefined
  onChange: (v: string) => void
}) {
  return (
    <div className="space-y-1">
      <label className="filter-label">{label}</label>
      <select
        className="filter-control"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">All</option>
        {options?.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </div>
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
