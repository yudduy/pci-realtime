import type { ChangeRecord, ChangesResponse } from "@/lib/changes"
import { baselineVertical } from "@/lib/verticals"

const BASE_URL = "https://pcindex.vercel.app"
const TAG_PREFIX = "tag:pcindex.vercel.app,2026:change/"

type AtomFeedOptions = {
  title: string
  path: string
  payload: ChangesResponse
}

export function atomFeed({ title, path, payload }: AtomFeedOptions) {
  const updated = latestUpdate(payload)
  const entries = payload.changes.map(atomEntry).join("\n")
  const selfUrl = `${BASE_URL}${path}`

  return `<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <id>${escapeXml(selfUrl)}</id>
  <title>${escapeXml(title)}</title>
  <updated>${escapeXml(updated)}</updated>
  <link rel="self" type="application/atom+xml" href="${escapeXml(selfUrl)}" />
  <link rel="alternate" type="text/html" href="${BASE_URL}/" />
  <author><name>PCIndex</name></author>
${entries}
</feed>
`
}

function atomEntry(change: ChangeRecord) {
  const verticalName = change.verticals[0]
    ? baselineVertical(change.verticals[0]).name
    : "PCIndex"
  const timestamp = atomTimestamp(change.date)
  const sourceLink = change.citation.url
    ? `\n    <link rel="alternate" href="${escapeXml(change.citation.url)}" />`
    : ""

  return `  <entry>
    <id>${TAG_PREFIX}${encodeURIComponent(change.id)}</id>
    <title>${escapeXml(`${verticalName}: ${change.title}`)}</title>
    <updated>${timestamp}</updated>
    <published>${timestamp}</published>${sourceLink}
    <content type="html">${escapeXml(entryHtml(change))}</content>
  </entry>`
}

function entryHtml(change: ChangeRecord) {
  const blocks = [`<p>${escapeXml(change.summary)}</p>`]
  if (change.citation.quote) {
    blocks.push(`<blockquote>${escapeXml(change.citation.quote)}</blockquote>`)
  }
  if (change.citation.url) {
    blocks.push(
      `<p><a href="${escapeXml(change.citation.url)}">Official source</a></p>`,
    )
  }
  return blocks.join("")
}

function latestUpdate(payload: ChangesResponse) {
  const latestDate = payload.changes.reduce<string | null>(
    (latest, change) => (!latest || change.date > latest ? change.date : latest),
    null,
  )
  return latestDate ? atomTimestamp(latestDate) : payload.as_of
}

function atomTimestamp(date: string) {
  return `${date}T00:00:00.000Z`
}

function escapeXml(value: string) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;")
}
