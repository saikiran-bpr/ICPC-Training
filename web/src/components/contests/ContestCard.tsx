import type { ReactNode } from "react"
import type { AssignedContest, ContestSummary } from "@/types/contest"
import { Pill } from "@/components/common/Pill"
import { Tag } from "@/components/common/Tag"
import { Stars } from "@/components/common/Stars"

type Props = {
  contest: ContestSummary | AssignedContest
  /** Extra slot under the header line (e.g. progress pills, AI summary). */
  extraSummary?: ReactNode
  /** Buttons rendered in the footer. */
  footer?: ReactNode
}

export function ContestCard({ contest, extraSummary, footer }: Props) {
  const meta = [contest.platform, contest.contest_type, contest.contest_year]
    .filter(Boolean)
    .join(" · ")

  return (
    <div className="card">
      <div className="flex items-start justify-between gap-3">
        <h3 className="card-title flex-1">
          {contest.url ? (
            <a
              href={contest.url}
              target="_blank"
              rel="noreferrer"
              className="hover:underline"
            >
              {contest.name}
            </a>
          ) : (
            contest.name
          )}
        </h3>
      </div>

      {meta && <div className="card-meta">{meta}</div>}

      {(contest.cf_stars != null || contest.ucup_stars != null) && (
        <div className="flex flex-wrap gap-2">
          <Stars label="CF" value={contest.cf_stars} color="#5ea1ff" />
          <Stars label="UCup" value={contest.ucup_stars} color="#d29922" />
        </div>
      )}

      {(contest.tutorial_pdf || contest.tutorial_translated) && (
        <div className="flex flex-wrap gap-3 text-[12px]">
          {contest.tutorial_pdf && (
            <a
              href={`/files/${contest.tutorial_pdf}`}
              target="_blank"
              rel="noreferrer"
              className="text-[color:var(--c-accent)] hover:underline"
            >
              📄 Tutorial
            </a>
          )}
          {contest.tutorial_translated && (
            <a
              href={`/files/${contest.tutorial_translated}`}
              target="_blank"
              rel="noreferrer"
              className="text-[color:var(--c-accent)] hover:underline"
            >
              📄 English translation
            </a>
          )}
        </div>
      )}

      {extraSummary}

      {(contest.assigned_users?.length > 0 || contest.assigned_teams?.length > 0) && (
        <div>
          <div className="card-section-h">Assigned to</div>
          <div className="flex flex-wrap gap-1">
            {contest.assigned_teams.map((t) => (
              <Tag key={`t-${t.id}`}>{t.name}</Tag>
            ))}
            {contest.assigned_users.map((u) => (
              <Pill key={`u-${u.id}`} value={u.role}>
                {u.name}
              </Pill>
            ))}
          </div>
        </div>
      )}

      {footer && <div className="card-footer">{footer}</div>}
    </div>
  )
}
