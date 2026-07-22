import assert from "node:assert/strict"
import { stat, readFile } from "node:fs/promises"
import { dirname, join, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import { createExportServer } from "../../scripts/serve-export.mjs"

const webRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../..")
const repoRoot = resolve(webRoot, "../..")
const outRoot = join(webRoot, "out")
const expectedSiteUrl =
  process.env.NEXT_PUBLIC_SITE_URL ?? "https://pcindex.github.io"

async function verify() {
  const server = createExportServer({ root: outRoot })
  await new Promise((resolveListen, reject) => {
    server.once("error", reject)
    server.listen(0, "127.0.0.1", resolveListen)
  })

  try {
    const address = server.address()
    assert(address && typeof address === "object", "server did not bind a port")
    const baseUrl = `http://127.0.0.1:${address.port}`

    const home = await fetchText(baseUrl, "/", 200)
    assert(home.includes('data-mode="live"'), "/ must contain data-mode=live")
    assert(!home.includes("DISCONNECTED"), "/ must not bake disconnected state")

    const feed = await fetchText(baseUrl, "/feed.xml", 200)
    assert(feed.includes('<feed xmlns="http://www.w3.org/2005/Atom">'))
    assert(feed.includes("tag:pcindex.vercel.app,2026"))
    await fetchText(baseUrl, "/verticals/clean-hydrogen/feed.xml", 200)

    const contract = JSON.parse(
      await readFile(join(repoRoot, "contracts/change-event-keys.json"), "utf8"),
    )
    const allChanges = await fetchJson(baseUrl, "/api/changes.json", 200)
    assert.equal(allChanges.contract_version, "1")
    assert.equal(allChanges.count, allChanges.changes.length)
    assert(allChanges.count >= 1, "changes snapshot must contain fixture data")
    for (const change of allChanges.changes) {
      assert.deepEqual(Object.keys(change).sort(), [...contract.change].sort())
    }

    const verticalChanges = await fetchJson(
      baseUrl,
      "/api/changes/clean-hydrogen.json",
      200,
    )
    assert.equal(verticalChanges.vertical, "clean-hydrogen")
    await fetchText(baseUrl, "/api/changes/bogus.json", 404)

    assert((await fetchText(baseUrl, "/policies/45V", 200)).includes("#policy-45V"))
    assert((await fetchText(baseUrl, "/dashboard", 200)).includes("url=/"))
    await fetchText(baseUrl, "/robots.txt", 200)
    const sitemap = await fetchText(baseUrl, "/sitemap.xml", 200)
    assert(sitemap.includes(expectedSiteUrl), "sitemap must use the build site URL")
    await fetchText(baseUrl, "/llms.txt", 200)
    await fetchText(baseUrl, "/nope", 404)

    await assertPath(join(outRoot, ".nojekyll"), "file")
    await assertPath(join(outRoot, "404.html"), "file")
    await assertPath(join(outRoot, "_next"), "directory")
  } finally {
    await new Promise((resolveClose) => server.close(resolveClose))
  }
}

async function fetchText(baseUrl, path, status) {
  const response = await fetch(`${baseUrl}${path}`)
  assert.equal(response.status, status, `${path} returned ${response.status}`)
  return response.text()
}

async function fetchJson(baseUrl, path, status) {
  return JSON.parse(await fetchText(baseUrl, path, status))
}

async function assertPath(path, kind) {
  const info = await stat(path)
  assert(kind === "file" ? info.isFile() : info.isDirectory(), `${path} is not a ${kind}`)
}

try {
  await verify()
  console.log("[verify-export] PASS")
} catch (error) {
  console.error(`[verify-export] FAILED: ${error instanceof Error ? error.message : String(error)}`)
  process.exitCode = 1
}
