import {
  renderChangeFeed,
  TAG_URI_PREFIX,
} from "@/lib/change-feed"
import {
  buildChanges,
  DELIVERY_LIMIT_DEFAULT_API,
  deliveryError,
  logDeliveryHit,
} from "@/lib/changes"
import { assertSnapshotUsable } from "@/lib/build-gate"
import { getDeliveryData } from "@/lib/data"
import { SITE_URL } from "@/lib/site"

export const dynamic = "force-static"

export async function GET() {
  const data = await getDeliveryData()
  assertSnapshotUsable("all-changes feed", data.connected, data.viewErrors)
  const changes = deliveryError(data)
    ? []
    : buildChanges(data, { limit: DELIVERY_LIMIT_DEFAULT_API })

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
      },
    },
  )
}
