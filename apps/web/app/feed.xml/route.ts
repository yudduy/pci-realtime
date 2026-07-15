import { atomFeed } from "@/lib/atom"
import { getChanges, logDeliveryHit } from "@/lib/changes"

export const dynamic = "force-dynamic"

export async function GET() {
  logDeliveryHit("feed", "all")
  const payload = await getChanges()
  return atomResponse(
    atomFeed({
      title: "PCIndex Policy Changes",
      path: "/feed.xml",
      payload,
    }),
  )
}

function atomResponse(body: string) {
  return new Response(body, {
    headers: {
      "cache-control": "no-store",
      "content-type": "application/atom+xml; charset=utf-8",
    },
  })
}
