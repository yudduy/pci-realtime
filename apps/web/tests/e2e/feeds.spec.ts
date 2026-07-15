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
  const response = await request.get("/api/changes")
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

test("filters and validates changes API queries", async ({ request }) => {
  const manufacturing = await request.get(
    "/api/changes?vertical=advanced-manufacturing",
  )
  expect((await manufacturing.json()).count).toBe(0)

  const badVertical = await request.get("/api/changes?vertical=bogus")
  expect(badVertical.status()).toBe(400)
  expect((await badVertical.json()).error).toContain(
    "advanced-manufacturing, clean-hydrogen, carbon-capture, electric-vehicles, clean-energy-finance",
  )

  const badSince = await request.get("/api/changes?since=bogus")
  expect(badSince.status()).toBe(400)

  const badSinceGrammar = await request.get("/api/changes?since=07/01/2026")
  expect(badSinceGrammar.status()).toBe(400)

  const future = await request.get("/api/changes?since=2030-01-01")
  expect((await future.json()).count).toBe(0)

  const past = await request.get("/api/changes?since=2020-01-01")
  expect((await past.json()).count).toBe(1)

  const encodedPlus = await request.get(
    "/api/changes?since=2020-01-01T00:00:00%2B00:00",
  )
  expect(encodedPlus.status()).toBe(200)
  expect((await encodedPlus.json()).count).toBe(1)

  const literalPlus = await request.get(
    "/api/changes?since=2030-01-01T00:00:00+00:00",
  )
  expect(literalPlus.status()).toBe(200)
  expect((await literalPlus.json()).count).toBe(0)

  const badLimit = await request.get("/api/changes?limit=abc")
  expect(badLimit.status()).toBe(400)

  const exponentLimit = await request.get("/api/changes?limit=1e2")
  expect(exponentLimit.status()).toBe(400)
})
