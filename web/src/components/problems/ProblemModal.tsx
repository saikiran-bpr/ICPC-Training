import { useEffect, useState } from "react"
import { useForm } from "react-hook-form"
import { toast } from "sonner"
import { Modal } from "@/components/common/Modal"
import {
  AsyncMultiSelect,
  type AsyncMultiSelectItem,
} from "@/components/common/AsyncMultiSelect"
import { useFetch } from "@/hooks/useFetch"
import { metaService } from "@/services/meta"
import { searchContestants, searchAssignableTeams } from "@/services/assignmentSearch"
import { problemsService, type ProblemWrite } from "@/services/problems"
import { ApiError } from "@/lib/api"
import type { Problem } from "@/types/problem"

type Props = {
  open: boolean
  onClose: () => void
  /** Pass an existing problem to edit; omit to create. */
  initial?: Problem | null
  onSaved?: (p: Problem) => void
}

type FormShape = {
  url: string
  name: string
  platform: string
  contest_type: string
  rating: string
  difficulty: string
  importance: string
  topic: string
  sub_topic: string
  tags: string
  key_idea: string
  notes: string
}

function blank(initial?: Problem | null): FormShape {
  return {
    url: initial?.url ?? "",
    name: initial?.name ?? "",
    platform: initial?.platform ?? "",
    contest_type: initial?.contest_type ?? "",
    rating: initial?.rating != null ? String(initial.rating) : "",
    difficulty: initial?.difficulty ?? "",
    importance: initial?.importance ?? "",
    topic: initial?.topic ?? "",
    sub_topic: initial?.sub_topic ?? "",
    tags: initial?.tags?.join(", ") ?? "",
    key_idea: initial?.key_idea ?? "",
    notes: initial?.notes ?? "",
  }
}

function initialUsers(initial?: Problem | null): AsyncMultiSelectItem[] {
  return (
    initial?.assigned_users.map((u) => ({ id: u.id, label: u.name, meta: u.role })) ?? []
  )
}

function initialTeams(initial?: Problem | null): AsyncMultiSelectItem[] {
  return initial?.assigned_teams.map((t) => ({ id: t.id, label: t.name })) ?? []
}

export function ProblemModal({ open, onClose, initial, onSaved }: Props) {
  const meta = useFetch((s) => metaService.get({ signal: s }), [])

  const [selUsers, setSelUsers] = useState<AsyncMultiSelectItem[]>(() =>
    initialUsers(initial),
  )
  const [selTeams, setSelTeams] = useState<AsyncMultiSelectItem[]>(() =>
    initialTeams(initial),
  )
  const [lookingUp, setLookingUp] = useState(false)
  const [saving, setSaving] = useState(false)

  const { register, handleSubmit, reset, setValue, watch, formState } =
    useForm<FormShape>({ defaultValues: blank(initial) })

  // Reset whenever the modal opens with a different problem.
  useEffect(() => {
    if (!open) return
    reset(blank(initial))
    setSelUsers(initialUsers(initial))
    setSelTeams(initialTeams(initial))
  }, [open, initial, reset])

  async function doLookup() {
    const u = watch("url").trim()
    if (!u) {
      toast.error("Enter a URL first")
      return
    }
    setLookingUp(true)
    try {
      const r = await problemsService.lookup(u)
      const setIfPresent = (k: keyof FormShape, v: string | undefined | null) => {
        if (v !== undefined && v !== null && v !== "") setValue(k, v)
      }
      if (r.name) setIfPresent("name", r.name)
      if (r.rating != null) setIfPresent("rating", String(r.rating))
      if (r.difficulty) setIfPresent("difficulty", r.difficulty)
      if (r.topic) setIfPresent("topic", r.topic)
      if (r.platform) setIfPresent("platform", r.platform)
      if (r.contest_type) setIfPresent("contest_type", r.contest_type)
      if (r.sub_topic) setIfPresent("sub_topic", r.sub_topic)
      if (r.tags?.length) setIfPresent("tags", r.tags.join(", "))
      toast.success("Fetched metadata")
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Lookup failed")
    } finally {
      setLookingUp(false)
    }
  }

  async function onSubmit(values: FormShape) {
    setSaving(true)
    try {
      const payload: ProblemWrite = {
        url: values.url.trim(),
        name: values.name.trim() || undefined,
        platform: values.platform || undefined,
        contest_type: values.contest_type || undefined,
        rating: values.rating ? Number(values.rating) : null,
        difficulty: values.difficulty || undefined,
        importance: values.importance || undefined,
        topic: values.topic || undefined,
        sub_topic: values.sub_topic.trim() || null,
        tags: values.tags
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean),
        key_idea: values.key_idea.trim() || null,
        notes: values.notes.trim() || null,
        assigned_user_ids: selUsers.map((u) => u.id),
        assigned_team_ids: selTeams.map((t) => t.id),
      }
      const saved = initial
        ? await problemsService.update(initial.id, payload)
        : await problemsService.create(payload)
      toast.success(initial ? "Problem updated" : "Problem created")
      onSaved?.(saved)
      onClose()
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Save failed")
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={initial ? "Edit problem" : "New problem"}
      footer={
        <>
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
          <button
            type="submit"
            form="problem-form"
            className="btn btn-primary"
            disabled={saving}
          >
            {saving ? "Saving…" : "Save"}
          </button>
        </>
      }
    >
      <form id="problem-form" onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div className="form-grid">
          <div className="full">
            <label className="form-label">URL</label>
            <div className="flex gap-2">
              <input
                className="form-control flex-1"
                placeholder="https://codeforces.com/problemset/problem/..."
                {...register("url", { required: true })}
              />
              <button
                type="button"
                className="btn"
                onClick={doLookup}
                disabled={lookingUp}
              >
                {lookingUp ? "Fetching…" : "Fetch details"}
              </button>
            </div>
            <p className="form-hint">
              For Codeforces URLs we'll auto-fill name, rating, tags, difficulty.
            </p>
          </div>

          <div className="full">
            <label className="form-label">Name</label>
            <input
              className="form-control"
              placeholder="(optional — auto-fetched if blank)"
              {...register("name")}
            />
          </div>

          <Select
            label="Platform"
            options={meta.data?.platforms ?? []}
            {...register("platform")}
          />
          <Select
            label="Contest Type"
            options={meta.data?.contest_types ?? []}
            {...register("contest_type")}
          />
          <div>
            <label className="form-label">Rating</label>
            <input
              type="number"
              className="form-control"
              {...register("rating")}
            />
          </div>
          <Select
            label="Difficulty"
            options={meta.data?.difficulties ?? []}
            {...register("difficulty")}
          />
          <Select
            label="Importance"
            options={meta.data?.importance ?? []}
            {...register("importance")}
          />
          <Select
            label="Topic"
            options={meta.data?.topics ?? []}
            {...register("topic")}
          />
          <div>
            <label className="form-label">Sub-topic</label>
            <input className="form-control" {...register("sub_topic")} />
          </div>
          <div className="full">
            <label className="form-label">Tags</label>
            <input
              className="form-control"
              placeholder="comma-separated"
              {...register("tags")}
            />
          </div>

          <div className="full">
            <label className="form-label">Assign to contestants</label>
            <AsyncMultiSelect
              selected={selUsers}
              onChange={setSelUsers}
              search={searchContestants}
              placeholder="Search contestants by name or handle…"
              emptyMessage="No contestants found"
            />
            <p className="form-hint">
              Only contestants can be assigned problems.
            </p>
          </div>
          <div className="full">
            <label className="form-label">Assign to teams</label>
            <AsyncMultiSelect
              selected={selTeams}
              onChange={setSelTeams}
              search={searchAssignableTeams}
              placeholder="Search teams…"
              emptyMessage="No teams found"
            />
            <p className="form-hint">
              Assigning to a team makes the problem visible to all members. You
              can only assign to teams you coach.
            </p>
          </div>
          <div className="full">
            <label className="form-label">Key idea / trick</label>
            <textarea className="form-control" {...register("key_idea")} />
          </div>
          <div className="full">
            <label className="form-label">Notes</label>
            <textarea className="form-control" {...register("notes")} />
          </div>
        </div>
        {formState.errors.url && (
          <p className="form-error">URL is required</p>
        )}
      </form>
    </Modal>
  )
}

type SelectProps = React.SelectHTMLAttributes<HTMLSelectElement> & {
  label: string
  options: string[]
}
const Select = ({ label, options, ...rest }: SelectProps) => (
  <div>
    <label className="form-label">{label}</label>
    <select className="form-control" {...rest}>
      <option value="">—</option>
      {options.map((o) => (
        <option key={o} value={o}>
          {o}
        </option>
      ))}
    </select>
  </div>
)
