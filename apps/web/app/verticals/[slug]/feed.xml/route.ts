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
import {
  baselineVertical,
  isVerticalId,
  VERTICAL_IDS,
} from "@/lib/verticals"

export const dynamic = "force-static"
export const dynamicParams = false

export function generateStaticParams() {
  return VERTICAL_IDS.map((slug) => ({ slug }))
}

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ slug: string }> },
) {
  const { slug } = await params

  if (!isVerticalId(slug)) {
    return new Response(
      `Unknown vertical: ${slug}. Valid ids: ${VERTICAL_IDS.join(", ")}`,
      {
        status: 404,
        headers: { "content-type": "text/plain; charset=utf-8" },
      },
    )
  }

  const data = await getDeliveryData()
  assertSnapshotUsable(`vertical feed (${slug})`, data.connected, data.viewErrors)
  const changes = deliveryError(data)
    ? []
    : buildChanges(data, {
        vertical: slug,
        limit: DELIVERY_LIMIT_DEFAULT_API,
      })
  const vertical = baselineVertical(slug)

  logDeliveryHit("feed_vertical", slug)

  return new Response(
    renderChangeFeed(changes, {
      id: `${TAG_URI_PREFIX}:changes:${slug}`,
      title: `PCIndex — ${vertical.name} changes`,
      selfUrl: `${SITE_URL}/verticals/${slug}/feed.xml`,
    }),
    {
      headers: {
        "content-type": "application/atom+xml; charset=utf-8",
      },
    },
  )
}
