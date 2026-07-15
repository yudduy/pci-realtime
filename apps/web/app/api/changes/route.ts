import {
  ChangesQueryError,
  deliveryKey,
  getChanges,
  logDeliveryHit,
} from "@/lib/changes"

export const dynamic = "force-dynamic"

export async function GET(request: Request) {
  const searchParams = new URL(request.url).searchParams
  const vertical = searchParams.get("vertical")
  logDeliveryHit("api", deliveryKey(vertical))

  try {
    const payload = await getChanges({
      since: searchParams.get("since"),
      vertical,
      limit: parseLimit(searchParams.get("limit")),
    })
    return Response.json(payload, { headers: noStoreHeaders() })
  } catch (error) {
    if (error instanceof ChangesQueryError) {
      return Response.json(
        {
          error: error.message,
          ...(error.validVerticals
            ? { valid_verticals: error.validVerticals }
            : {}),
        },
        { status: 400, headers: noStoreHeaders() },
      )
    }
    throw error
  }
}

function parseLimit(value: string | null) {
  return value === null ? undefined : Number(value)
}

function noStoreHeaders() {
  return { "cache-control": "no-store" }
}
