import { expect, test, type Page } from "@playwright/test"

test("serves a valid global Atom feed from the change fixture", async ({
  page,
  request,
}) => {
  const response = await request.get("/feed.xml")

  expect(response.status()).toBe(200)
  expect(response.headers()["content-type"]).toContain("application/atom+xml")
  expect(response.headers()["cache-control"]).toContain("no-store")
  const feed = await parseAtom(page, await response.text())

  expect(feed.parserError).toBeNull()
  expect(feed.updated).toBe("2026-05-18T00:00:00.000Z")
  expect(feed.entries).toHaveLength(2)
  expect(feed.entries.map((entry) => entry.title)).toEqual([
    "Clean Hydrogen: Clean hydrogen production credit guidance",
    "Electric Vehicles: Clean vehicle credit transition & eligibility guidance",
  ])
  expect(feed.entries[0]).toMatchObject({
    id: expect.stringContaining(
      encodeURIComponent("2026-W21:federal_register:45v-guidance:45V"),
    ),
    content: expect.stringContaining("<blockquote>"),
    href: expect.stringContaining("https://www.federalregister.gov/documents/example"),
  })
  expect(feed.entries[1].content).toContain("manufacturers &amp; buyers")
  expect(feed.entries[1].content).toContain("Official source")
})

test("filters a vertical Atom feed and returns 404 for an unknown slug", async ({
  page,
  request,
}) => {
  const response = await request.get("/verticals/clean-hydrogen/feed.xml")
  expect(response.status()).toBe(200)

  const feed = await parseAtom(page, await response.text())
  expect(feed.parserError).toBeNull()
  expect(feed.entries).toHaveLength(1)
  expect(feed.entries[0].title).toBe(
    "Clean Hydrogen: Clean hydrogen production credit guidance",
  )

  const unknown = await request.get("/verticals/geothermal/feed.xml")
  expect(unknown.status()).toBe(404)
})

test("filters the JSON change contract and validates verticals", async ({ request }) => {
  const previous = await request.get(
    "/api/changes?since=2025-01-01&vertical=electric-vehicles&limit=10",
  )
  expect(previous.status()).toBe(200)
  expect((await previous.json()).count).toBe(1)

  const excluded = await request.get(
    "/api/changes?since=2026-01-01&vertical=electric-vehicles&limit=10",
  )
  expect(excluded.status()).toBe(200)
  expect((await excluded.json()).changes).toEqual([])

  const response = await request.get(
    "/api/changes?since=2026-01-01&vertical=clean-hydrogen&limit=10",
  )
  expect(response.status()).toBe(200)
  expect(response.headers()["cache-control"]).toContain("no-store")
  const payload = await response.json()
  expect(payload.as_of).toMatch(/^\d{4}-\d{2}-\d{2}T/)
  expect(payload.count).toBe(1)
  expect(Object.keys(payload.changes[0]).sort()).toEqual(
    [
      "citation",
      "date",
      "dimensions",
      "id",
      "method",
      "pci_delta",
      "provisions",
      "summary",
      "title",
      "verticals",
    ].sort(),
  )
  expect(payload.changes[0]).toMatchObject({
    id: "2026-W21:federal_register:45v-guidance:45V",
    date: "2026-05-18",
    verticals: ["clean-hydrogen"],
    provisions: ["45V"],
    title: "Clean hydrogen production credit guidance",
    summary: "Treasury guidance narrows eligibility for the clean hydrogen credit.",
    pci_delta: -0.33,
    dimensions: { specificity: -1, durability: 0, enforceability: 0 },
    citation: {
      quote: "Treasury guidance narrows eligibility for the clean hydrogen credit.",
      source_name: "Federal Register",
      published_at: "2026-05-20T14:00:00.000Z",
    },
    method: {
      schema_version: "schema-b-v1.0.0",
      method_version: "pci-delta-v1",
      prompt_version: "test",
    },
  })
  expect(Object.keys(payload.changes[0].citation).sort()).toEqual(
    ["published_at", "quote", "source_name", "url"].sort(),
  )

  const unknown = await request.get("/api/changes?vertical=geothermal")
  expect(unknown.status()).toBe(400)
  expect(await unknown.json()).toMatchObject({
    error: expect.stringContaining("Unknown vertical"),
    valid_verticals: [
      "advanced-manufacturing",
      "clean-hydrogen",
      "carbon-capture",
      "electric-vehicles",
      "clean-energy-finance",
    ],
  })
})

async function parseAtom(page: Page, source: string) {
  return page.evaluate((xml) => {
    const document = new DOMParser().parseFromString(xml, "application/xml")
    const entries = Array.from(document.getElementsByTagName("entry")).map(
      (entry) => ({
        id: entry.getElementsByTagName("id")[0]?.textContent ?? "",
        title: entry.getElementsByTagName("title")[0]?.textContent ?? "",
        content: entry.getElementsByTagName("content")[0]?.textContent ?? "",
        href: entry.getElementsByTagName("link")[0]?.getAttribute("href") ?? "",
      }),
    )
    return {
      parserError:
        document.getElementsByTagName("parsererror")[0]?.textContent ?? null,
      updated: document.getElementsByTagName("feed")[0]
        ?.getElementsByTagName("updated")[0]?.textContent,
      entries,
    }
  }, source)
}
