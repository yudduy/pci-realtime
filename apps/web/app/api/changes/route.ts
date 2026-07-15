import {
  buildChanges,
  DELIVERY_LIMIT_DEFAULT_API,
  DELIVERY_LIMIT_MAX,
  deliveryError,
  logDeliveryHit,
  normalizeSince,
} from "@/lib/changes"
import { getDeliveryData } from "@/lib/data"
import { isVerticalId, VERTICAL_IDS } from "@/lib/verticals"

export const dynamic = "force-dynamic"
export const runtime = "nodejs"

const INVALID_SINCE =
  "Invalid since: use ISO 8601 (e.g. 2026-07-01 or 2026-07-01T00:00:00Z)"

export async function GET(request: Request) {
  const searchParams = new URL(request.url).searchParams
  const sinceValue = rawQueryParam(request.url, "since")
  const verticalValue = searchParams.get("vertical")
  const limitValue = searchParams.get("limit")
  const since = sinceValue === null ? null : normalizeSince(sinceValue)

  if (sinceValue !== null && since === null) {
    return jsonResponse({ error: INVALID_SINCE }, 400)
  }

  if (verticalValue !== null && !isVerticalId(verticalValue)) {
    return jsonResponse(
      {
        error: `Unknown vertical: ${verticalValue}. Valid ids: ${VERTICAL_IDS.join(", ")}`,
      },
      400,
    )
  }

  const limit = parseLimit(limitValue)
  if (limit === null) {
    return jsonResponse({ error: "Invalid limit: use an integer" }, 400)
  }

  const vertical = verticalValue ?? null
  const data = await getDeliveryData()
  const error = deliveryError(data)
  if (error) {
    return jsonResponse(
      { error: `Registry unavailable: ${error}` },
      503,
      "no-store",
    )
  }
  const changes = buildChanges(data, {
    since: since ?? undefined,
    vertical: vertical ?? undefined,
    limit,
  })

  logDeliveryHit("changes_api", vertical, {
    since_present: sinceValue !== null,
  })

  return jsonResponse(
    {
      contract_version: "1",
      generated_at: new Date().toISOString(),
      since,
      vertical,
      count: changes.length,
      changes,
    },
    200,
    "public, s-maxage=300, stale-while-revalidate=900",
  )
}

function parseLimit(value: string | null) {
  if (value === null) return DELIVERY_LIMIT_DEFAULT_API
  const trimmed = value.trim()
  if (!/^\d+$/.test(trimmed)) return null
  const parsed = Number(trimmed)
  return Math.min(DELIVERY_LIMIT_MAX, Math.max(1, parsed))
}

function rawQueryParam(requestUrl: string, key: string): string | null {
  const search = new URL(requestUrl).search
  if (!search) return null
  for (const pair of search.slice(1).split("&")) {
    const eq = pair.indexOf("=")
    const k = eq === -1 ? pair : pair.slice(0, eq)
    if (k !== key) continue
    return decodeURIComponent(eq === -1 ? "" : pair.slice(eq + 1))
  }
  return null
}

function jsonResponse(payload: unknown, status: number, cacheControl?: string) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      ...(cacheControl ? { "cache-control": cacheControl } : {}),
    },
  })
}
