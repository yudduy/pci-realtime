import type { ChangeEvent } from "@/lib/changes"

export const SITE_URL = "https://pcindex.vercel.app"
// RFC 4151 tag URI — the year is the minting date, frozen forever; changing it re-delivers every entry as new.
export const TAG_URI_PREFIX = "tag:pcindex.vercel.app,2026"
const SUBTITLE =
  "Cited policy-change ledger for climate-tech verticals. Commitment credibility of IRA-era provisions, scored per the PNAS paper."

export function renderChangeFeed(
  changes: ChangeEvent[],
  options: { id: string; title: string; selfUrl: string },
) {
  const updated = changes[0]?.recorded_at ?? new Date().toISOString()
  const entries = changes.map(renderEntry).join("\n")

  return `<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <id>${escapeXml(options.id)}</id>
  <title>${escapeXml(options.title)}</title>
  <subtitle>${escapeXml(SUBTITLE)}</subtitle>
  <updated>${escapeXml(updated)}</updated>
  <link rel="self" href="${escapeXml(options.selfUrl)}" />
  <link rel="alternate" type="text/html" href="${SITE_URL}/" />
  <author><name>PCIndex</name></author>
${entries}
</feed>`
}

function renderEntry(change: ChangeEvent) {
  const sourceLabel = [change.source.name, change.source.title]
    .filter((value): value is string => Boolean(value))
    .join(" — ")
  const alternateUrl =
    change.source.url ?? `${SITE_URL}/#policy-${change.provision.code}`
  const sourceLink = change.source.url
    ? `<p><a href="${escapeXml(change.source.url)}">Official source</a></p>`
    : ""
  const content = [
    `<p>PCI Δ ${formatDelta(change.pci_delta)} · specificity ${formatDelta(change.dimension_deltas.specificity ?? 0)} · durability ${formatDelta(change.dimension_deltas.durability ?? 0)} · enforceability ${formatDelta(change.dimension_deltas.enforceability ?? 0)}</p>`,
    `<p>${escapeXml(change.rationale ?? "")}</p>`,
    `<blockquote>${escapeXml(change.source.quote ?? "")}<cite>${escapeXml(sourceLabel)}</cite></blockquote>`,
    `<p>Provision: ${escapeXml(change.provision.code)} — ${escapeXml(change.provision.name)} · Method: ${escapeXml(change.method_version ?? "")}</p>`,
    sourceLink,
  ].join("")

  return `  <entry>
    <id>${escapeXml(`${TAG_URI_PREFIX}:change:${change.id}`)}</id>
    <title>${escapeXml(change.headline ?? "")}</title>
    <updated>${escapeXml(change.recorded_at)}</updated>
    <link rel="alternate" href="${escapeXml(alternateUrl)}" />
    <content type="html">${escapeXml(content)}</content>
  </entry>`
}

function formatDelta(value: number) {
  if (value < 0) return `−${Math.abs(value)}`
  if (value > 0) return `+${value}`
  return "0"
}

function escapeXml(value: string) {
  return value
    .replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;")
}
