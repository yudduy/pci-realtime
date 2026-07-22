import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { expect, test } from "@playwright/test"

const EVENT_ID = "2026-W21:federal_register:45v-guidance:45V"
const CHANGE_EVENT_KEYS = JSON.parse(
  readFileSync(
    resolve(__dirname, "../../../../contracts/change-event-keys.json"),
    "utf8",
  ),
) as Record<"change" | "provision" | "source", string[]>

test("serves the all-changes Atom feed", async ({ request }) => {
  const response = await request.get("/feed.xml")
  const body = await response.text()

  expect(response.status()).toBe(200)
  expect(response.headers()["content-type"]).toContain("application/atom+xml")
  expect(body).toContain('<feed xmlns="http://www.w3.org/2005/Atom">')
  expect(body).toContain(
    `tag:pcindex.vercel.app,2026:change:${EVENT_ID}`,
  )
  expect(body).toContain(
    "Clean Hydrogen: Clean hydrogen production credit guidance",
  )
  expect(body).toContain(
    "https://www.federalregister.gov/documents/example#:~:text=",
  )
  expect(body).toContain("Treasury guidance narrows eligibility")
  expect(body).not.toMatch(/&(?!amp;|lt;|gt;|quot;|#39;|apos;)/)
})

test("serves vertical Atom feeds and rejects unknown verticals", async ({
  request,
}) => {
  const hydrogenResponse = await request.get(
    "/verticals/clean-hydrogen/feed.xml",
  )
  const hydrogenBody = await hydrogenResponse.text()
  expect(hydrogenResponse.status()).toBe(200)
  expect(hydrogenBody).toContain(
    `tag:pcindex.vercel.app,2026:change:${EVENT_ID}`,
  )

  const manufacturingResponse = await request.get(
    "/verticals/advanced-manufacturing/feed.xml",
  )
  expect(manufacturingResponse.status()).toBe(200)
  expect(await manufacturingResponse.text()).not.toContain("<entry>")

  const unknownResponse = await request.get("/verticals/geothermal/feed.xml")
  expect(unknownResponse.status()).toBe(404)
})

test("serves the canonical changes API contract", async ({ request }) => {
  const response = await request.get("/api/changes.json")
  const payload = await response.json()

  expect(response.status()).toBe(200)
  expect(payload.contract_version).toBe("1")
  expect(payload.count).toBe(1)
  expect(Object.keys(payload.changes[0]).sort()).toEqual(CHANGE_EVENT_KEYS.change)
  expect(payload.changes[0].verticals).toEqual(["clean-hydrogen"])
  expect(Object.keys(payload.changes[0].provision).sort()).toEqual(
    CHANGE_EVENT_KEYS.provision,
  )
  expect(payload.changes[0].provision).toEqual({
    code: "45V",
    name: "Clean Hydrogen Production Credit",
  })
  expect(Object.keys(payload.changes[0].source).sort()).toEqual(
    CHANGE_EVENT_KEYS.source,
  )
  expect(payload.changes[0].pci_delta).toBe(-0.33)
  expect(payload.changes[0].method_version).toBe("test")
  expect(payload.changes[0].source.url).toContain("#:~:text=")
})

test("serves per-vertical snapshots and retires the query API", async ({ request }) => {
  const hydrogen = await request.get("/api/changes/clean-hydrogen.json")
  expect(hydrogen.status()).toBe(200)
  expect((await hydrogen.json()).vertical).toBe("clean-hydrogen")

  const bogus = await request.get("/api/changes/bogus.json")
  expect(bogus.status()).toBe(404)

  const legacy = await request.get("/api/changes")
  expect(legacy.status()).toBe(404)
})
