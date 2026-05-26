import { formatDateTime } from "@/components/market/format"
import type { MarketDiscoveryCandidate, RegistryData } from "@/lib/data"
import {
  buildMarketCoverage,
  candidatesForProvision,
  rejectionLabel,
} from "@/lib/market-coverage"

export function MarketCoveragePanel({
  data,
  selectedProvision,
  compact = false,
}: {
  data: RegistryData
  selectedProvision?: string
  compact?: boolean
}) {
  const coverage = buildMarketCoverage(data)
  if (!coverage.scanned && !coverage.candidates) return null

  const scopedCandidates = candidatesForProvision(
    data.marketDiscoveryCandidates,
    selectedProvision,
  )
  const shownCandidates = (
    selectedProvision && scopedCandidates.length ? scopedCandidates : data.marketDiscoveryCandidates
  ).slice(0, compact ? 3 : 5)
  const topBlocker = coverage.rejectionCounts[0]?.label ?? "No blockers recorded"
  const fallbackNotice = Boolean(selectedProvision && !scopedCandidates.length)

  return (
    <section className={compact ? "market-coverage-panel compact" : "market-coverage-panel"}>
      <div className="coverage-head">
        <div>
          <p>Market Discovery Audit</p>
          <h2>
            {coverage.matched
              ? `${coverage.matched} eligible public ${coverage.matched === 1 ? "market" : "markets"}`
              : "No eligible public market found"}
          </h2>
        </div>
        <span>{formatDateTime(coverage.latestAt)}</span>
      </div>

      <div className="coverage-metrics">
        <CoverageMetric label="Scanned" value={formatCount(coverage.scanned)} />
        <CoverageMetric label="Near-misses" value={formatCount(coverage.candidates)} />
        <CoverageMetric label="Eligible" value={formatCount(coverage.matched)} />
        <CoverageMetric label="Top blocker" value={topBlocker} />
      </div>

      <div className="coverage-body">
        <div className="coverage-venues">
          {coverage.venues.map((venue) => (
            <div key={venue.source} className="coverage-venue">
              <strong>{venue.name}</strong>
              <span>
                {formatCount(venue.scanned)} scanned / {formatCount(venue.published)} eligible
              </span>
              <small>{venue.rateLimited ? `${venue.rateLimited} rate limits` : "No rate limits"}</small>
            </div>
          ))}
        </div>

        <div className="coverage-candidates">
          <div className="coverage-subhead">
            <strong>{selectedProvision ? `${selectedProvision} near-misses` : "Closest near-misses"}</strong>
            {fallbackNotice && <span>No direct candidate mentioned this provision.</span>}
          </div>
          {shownCandidates.length ? (
            <div className="coverage-candidate-list">
              {shownCandidates.map((candidate) => (
                <CandidateRow key={candidate.candidate_id} candidate={candidate} />
              ))}
            </div>
          ) : (
            <p className="coverage-empty">No stored near-miss rows for this scan.</p>
          )}
        </div>
      </div>
    </section>
  )
}

function CoverageMetric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function CandidateRow({ candidate }: { candidate: MarketDiscoveryCandidate }) {
  const title = candidate.title || candidate.ticker
  const body = (
    <>
      <div>
        <strong>{title}</strong>
        <span>
          {candidate.venue.toUpperCase()} / {candidate.ticker}
        </span>
      </div>
      <div className="coverage-reasons">
        {(candidate.rejection_reasons.length ? candidate.rejection_reasons : ["eligible_snapshot"]).map(
          (reason) => (
            <small key={reason}>{reason === "eligible_snapshot" ? "Eligible snapshot" : rejectionLabel(reason)}</small>
          ),
        )}
      </div>
    </>
  )

  if (candidate.market_url) {
    return (
      <a href={candidate.market_url} className="coverage-candidate">
        {body}
      </a>
    )
  }

  return <div className="coverage-candidate">{body}</div>
}

function formatCount(value: number) {
  return value.toLocaleString("en-US")
}
