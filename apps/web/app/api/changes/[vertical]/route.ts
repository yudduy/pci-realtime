import { assertSnapshotUsable } from "@/lib/build-gate"
import {
  buildChanges,
  DELIVERY_LIMIT_MAX,
  deliveryError,
  logDeliveryHit,
} from "@/lib/changes"
import { getDeliveryData } from "@/lib/data"
import { VERTICAL_IDS } from "@/lib/verticals"

export const dynamic = "force-static"
export const dynamicParams = false

export function generateStaticParams() {
  return VERTICAL_IDS.map((vertical) => ({ vertical: `${vertical}.json` }))
}

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ vertical: string }> },
) {
  const vertical = (await params).vertical.replace(/\.json$/, "")
  const data = await getDeliveryData()
  assertSnapshotUsable(
    `changes snapshot (${vertical})`,
    data.connected,
    data.viewErrors,
  )
  const changes = deliveryError(data)
    ? []
    : buildChanges(data, { vertical, limit: DELIVERY_LIMIT_MAX })

  logDeliveryHit("changes_api", vertical)

  return Response.json({
    contract_version: "1",
    generated_at: new Date().toISOString(),
    since: null,
    vertical,
    count: changes.length,
    changes,
  })
}
