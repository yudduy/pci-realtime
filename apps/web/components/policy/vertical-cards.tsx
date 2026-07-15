"use client"

import type { VerticalPci } from "@/lib/data"
import { deltaToneClass, formatDelta, formatScore } from "@/lib/format"

export const VERTICAL_STATUS_LABEL =
  "Commitment credibility vs IRA-enactment baseline"

export type VerticalTone = "green" | "amber" | "red" | "neutral"

export function verticalTone(vertical: VerticalPci): VerticalTone {
  const score = vertical.vertical_pci
  const baseline = vertical.baseline_pci
  if (score === null || !Number.isFinite(score) || !Number.isFinite(baseline)) {
    return "neutral"
  }
  if (score >= baseline - 0.15) return "green"
  if (score >= baseline - 1) return "amber"
  return "red"
}

export function VerticalCards({
  verticals,
  onSelect,
}: {
  verticals: VerticalPci[]
  onSelect: (verticalId: string) => void
}) {
  return (
    <section className="vertical-overview" aria-labelledby="vertical-overview-title">
      <div className="vertical-overview-head">
        <div>
          <p>Scored climate-tech verticals</p>
          <h2 id="vertical-overview-title">Commitment credibility by vertical</h2>
        </div>
        <p className="vertical-status-label">{VERTICAL_STATUS_LABEL}</p>
      </div>

      <div className="vertical-card-grid">
        {verticals.map((vertical) => {
          const tone = verticalTone(vertical)
          const hasWeeklyDelta =
            typeof vertical.weekly_delta === "number" &&
            Number.isFinite(vertical.weekly_delta) &&
            vertical.weekly_delta !== 0
          return (
            <a
              key={vertical.id}
              href={`#vertical-${vertical.id}`}
              className={`vertical-card vertical-tone-${tone}`}
              data-testid="vertical-card"
              data-tone={tone}
              onClick={() => onSelect(vertical.id)}
              aria-label={`Open ${vertical.name} evidence detail`}
            >
              <div className="vertical-card-head">
                <h3>{vertical.name}</h3>
                <span
                  className="vertical-card-status"
                  aria-label={`${VERTICAL_STATUS_LABEL}: ${formatScore(vertical.vertical_pci)}`}
                >
                  <span>Status</span>
                  <strong>{formatScore(vertical.vertical_pci)}</strong>
                </span>
              </div>

              <div className="vertical-card-change">
                {hasWeeklyDelta && (
                  <span className={`vertical-delta-chip ${deltaToneClass(vertical.weekly_delta)}`}>
                    Weekly {formatDelta(vertical.weekly_delta)}
                  </span>
                )}
                <p>
                  {vertical.last_change_week_start ? (
                    <>
                      Last change:{" "}
                      <time dateTime={vertical.last_change_week_start}>
                        {formatVerticalDate(vertical.last_change_week_start)}
                      </time>
                    </>
                  ) : (
                    "No scored changes yet"
                  )}
                </p>
              </div>

              <p className="vertical-coverage-note">{vertical.coverage_note}</p>
              <div className="vertical-provision-chips" aria-label="Underlying provisions">
                {vertical.provisions.map((code) => (
                  <span key={code} className="vertical-provision-chip">
                    {code}
                  </span>
                ))}
              </div>
            </a>
          )
        })}
      </div>
    </section>
  )
}

function formatVerticalDate(value: string) {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(value))
}
