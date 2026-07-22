import { createServer } from "node:http"
import { createReadStream } from "node:fs"
import { realpathSync } from "node:fs"
import { realpath, stat } from "node:fs/promises"
import { extname, resolve, sep } from "node:path"
import { fileURLToPath } from "node:url"

const CONTENT_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".xml": "application/xml; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".txt": "text/plain; charset=utf-8",
  ".svg": "image/svg+xml",
  ".pdf": "application/pdf",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".ico": "image/x-icon",
  ".woff2": "font/woff2",
}

export function createExportServer({ root }) {
  const exportRoot = realpathSync(resolve(root))

  return createServer(async (request, response) => {
    if (request.method !== "GET" && request.method !== "HEAD") {
      response.writeHead(405, { allow: "GET, HEAD" })
      response.end()
      return
    }

    try {
      const pathname = decodeURIComponent(
        new URL(request.url ?? "/", "http://localhost").pathname,
      )
      if (pathname.includes("\0") || pathname.includes("\\")) {
        throw new Error("invalid path")
      }

      const requested = resolve(exportRoot, `.${pathname}`)
      const candidates = [requested, resolve(requested, "index.html"), `${requested}.html`]
      const file = await firstFile(exportRoot, candidates)
      if (file) {
        sendFile(request, response, file.path, file.size, 200)
        return
      }
    } catch {
      // Malformed and out-of-root paths use the same Pages-style 404.
    }

    const fallback = await firstFile(exportRoot, [resolve(exportRoot, "404.html")])
    if (fallback) {
      sendFile(request, response, fallback.path, fallback.size, 404)
      return
    }
    response.writeHead(404, { "content-type": "text/plain; charset=utf-8" })
    response.end(request.method === "HEAD" ? undefined : "Not found")
  })
}

async function firstFile(root, candidates) {
  for (const candidate of candidates) {
    if (candidate !== root && !candidate.startsWith(`${root}${sep}`)) continue
    try {
      const [info, canonical] = await Promise.all([stat(candidate), realpath(candidate)])
      if (info.isFile() && canonical === candidate) {
        return { path: candidate, size: info.size }
      }
    } catch {
      // Try the next static-host resolution candidate.
    }
  }
  return null
}

function sendFile(request, response, path, size, status) {
  response.writeHead(status, {
    "content-type": CONTENT_TYPES[extname(path)] ?? "application/octet-stream",
    "content-length": size,
  })
  if (request.method === "HEAD") response.end()
  else createReadStream(path).pipe(response)
}

function cliOptions(argv) {
  const options = { root: "out", port: 3000, host: "0.0.0.0" }
  for (let index = 0; index < argv.length; index += 2) {
    const flag = argv[index]
    const value = argv[index + 1]
    if (!value || !["--root", "--port", "--host"].includes(flag)) {
      throw new Error(`Usage: serve-export.mjs --root <dir> --port <port> --host <host>`)
    }
    if (flag === "--root") options.root = value
    if (flag === "--port") options.port = Number(value)
    if (flag === "--host") options.host = value
  }
  if (!Number.isInteger(options.port) || options.port < 1) {
    throw new Error(`Invalid port: ${options.port}`)
  }
  return options
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const options = cliOptions(process.argv.slice(2))
    createExportServer(options).listen(options.port, options.host, () => {
      console.log(`Serving ${resolve(options.root)} at http://${options.host}:${options.port}`)
    })
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error))
    process.exitCode = 1
  }
}
