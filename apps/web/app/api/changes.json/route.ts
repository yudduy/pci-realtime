import { assertSnapshotUsable } from "@/lib/build-gate"
import {
  buildChanges,
  DELIVERY_LIMIT_MAX,
  deliveryError,
  logDeliveryHit,
} from "@/lib/changes"
import { getDeliveryData } from "@/lib/data"

export const dynamic = "force-static"

export async function GET() {
  const data = await getDeliveryData()
  assertSnapshotUsable("changes snapshot", data.connected, data.viewErrors)
  const changes = deliveryError(data)
    ? []
    : buildChanges(data, { limit: DELIVERY_LIMIT_MAX })

  logDeliveryHit("changes_api", null)

  return Response.json({
    contract_version: "1",
    generated_at: new Date().toISOString(),
    since: null,
    vertical: null,
    count: changes.length,
    changes,
  })
}
