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
import {
  baselineVertical,
  isVerticalId,
  VERTICAL_IDS,
} from "@/lib/verticals"

export const dynamic = "force-dynamic"
export const runtime = "nodejs"

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
  const changes = buildChanges(data, {
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
        "cache-control": "public, s-maxage=600, stale-while-revalidate=1800",
      },
    },
  )
}
