import { atomFeed } from "@/lib/atom"
import {
  deliveryKey,
  getChanges,
  logDeliveryHit,
} from "@/lib/changes"
import { baselineVertical, isVerticalId } from "@/lib/verticals"

export const dynamic = "force-dynamic"

type VerticalFeedProps = {
  params: Promise<{ slug: string }>
}

export async function GET(_request: Request, { params }: VerticalFeedProps) {
  const { slug } = await params
  const vertical = slug.trim().toLowerCase()
  logDeliveryHit("feed", deliveryKey(vertical))
  if (!isVerticalId(vertical)) {
    return new Response("Unknown vertical.", {
      status: 404,
      headers: { "cache-control": "no-store" },
    })
  }

  const payload = await getChanges({ vertical })
  const name = baselineVertical(vertical).name
  return new Response(
    atomFeed({
      title: `${name} Policy Changes`,
      path: `/verticals/${vertical}/feed.xml`,
      payload,
    }),
    {
      headers: {
        "cache-control": "no-store",
        "content-type": "application/atom+xml; charset=utf-8",
      },
    },
  )
}
