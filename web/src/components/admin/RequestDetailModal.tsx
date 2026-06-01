import { Modal } from "@/components/common/Modal"
import type { User } from "@/types/user"

type Props = {
  request: User | null
  onClose: () => void
  onApprove: (u: User) => void
  onReject: (u: User) => void
  busy: boolean
}

export function RequestDetailModal({
  request,
  onClose,
  onApprove,
  onReject,
  busy,
}: Props) {
  if (!request) return null

  return (
    <Modal
      open={request !== null}
      onClose={onClose}
      title={`Signup request — ${request.name}`}
      size="sm"
      footer={
        <>
          <button type="button" className="btn" onClick={onClose} disabled={busy}>
            Close
          </button>
          <button
            type="button"
            className="btn btn-danger"
            onClick={() => onReject(request)}
            disabled={busy}
          >
            Reject
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => onApprove(request)}
            disabled={busy}
          >
            Approve as Contestant
          </button>
        </>
      }
    >
      <div className="space-y-3">
        <Section title="Account">
          <Row label="Full name" value={request.name} />
          <Row label="Email" value={request.email} mono />
        </Section>

        <Section title="Profile">
          <Row label="Codeforces handle" value={request.handle ?? "—"} mono />
          <Row label="Institution" value={request.institution ?? "—"} />
          <Row
            label="Year of study"
            value={
              request.year_of_study != null ? String(request.year_of_study) : "—"
            }
          />
        </Section>

        <Section title="Request">
          <Row label="Requested role" value="Contestant" />
          <Row
            label="Submitted"
            value={
              request.date_joined
                ? new Date(request.date_joined).toLocaleString()
                : "—"
            }
          />
          <Row label="Status" value={request.status} />
          <Row label="Request ID" value={`#${request.id}`} mono />
        </Section>
      </div>
    </Modal>
  )
}

function Section({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}) {
  return (
    <div>
      <div
        className="text-[11px] uppercase tracking-wide mb-1"
        style={{ color: "var(--c-muted)" }}
      >
        {title}
      </div>
      <div
        className="rounded-md border divide-y"
        style={{
          background: "var(--c-panel-2)",
          borderColor: "var(--c-border)",
        }}
      >
        {children}
      </div>
    </div>
  )
}

function Row({
  label,
  value,
  mono,
}: {
  label: string
  value: string
  mono?: boolean
}) {
  return (
    <div
      className="flex items-center justify-between px-3 py-2 text-[13px]"
      style={{ borderColor: "var(--c-border)" }}
    >
      <span style={{ color: "var(--c-muted)" }}>{label}</span>
      <span
        className={mono ? "font-mono" : ""}
        style={{ color: "var(--c-text)" }}
      >
        {value}
      </span>
    </div>
  )
}
