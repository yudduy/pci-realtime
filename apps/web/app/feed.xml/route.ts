import {
  renderChangeFeed,
  SITE_URL,
  TAG_URI_PREFIX,
} from "@/lib/change-feed"
import {
  buildChanges,
  DELIVERY_LIMIT_DEFAULT_API,
  deliveryError,
  logDeliveryHit,
} from "@/lib/changes"
import { getDeliveryData } from "@/lib/data"

export const dynamic = "force-dynamic"
export const runtime = "nodejs"

export async function GET() {
  const data = await getDeliveryData()
  const error = deliveryError(data)
  if (error) {
    return new Response(`Registry unavailable: ${error}`, {
      status: 503,
      headers: {
        "content-type": "text/plain; charset=utf-8",
        "cache-control": "no-store",
      },
    })
  }
  const changes = buildChanges(data, { limit: DELIVERY_LIMIT_DEFAULT_API })

  logDeliveryHit("feed", null)

  return new Response(
    renderChangeFeed(changes, {
      id: `${TAG_URI_PREFIX}:changes`,
      title: "PCIndex — cited policy changes",
      selfUrl: `${SITE_URL}/feed.xml`,
    }),
    {
      headers: {
        "content-type": "application/atom+xml; charset=utf-8",
        "cache-control": "public, s-maxage=600, stale-while-revalidate=1800",
      },
    },
  )
}
