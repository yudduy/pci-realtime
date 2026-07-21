import { spawn } from "node:child_process"
import { cp, mkdir, rm, symlink } from "node:fs/promises"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

const webRoot = join(dirname(fileURLToPath(import.meta.url)), "../..")
const sandbox = join(webRoot, ".next/e2e-fixture")
const entries = [
  "app",
  "components",
  "lib",
  "public",
  "next-env.d.ts",
  "next.config.mjs",
  "package.json",
  "postcss.config.mjs",
  "tsconfig.json",
]

await rm(sandbox, { force: true, recursive: true })
await mkdir(sandbox, { recursive: true })
for (const entry of entries) {
  await cp(join(webRoot, entry), join(sandbox, entry), { recursive: true })
}
await symlink(join(webRoot, "node_modules"), join(sandbox, "node_modules"), "dir")

const child = spawn(
  process.execPath,
  [
    join(webRoot, "node_modules/next/dist/bin/next"),
    "dev",
    "--hostname",
    "127.0.0.1",
    "--port",
    "8513",
    "--webpack",
  ],
  { cwd: sandbox, env: process.env, stdio: "inherit" },
)

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.once(signal, () => child.kill(signal))
}

child.once("exit", async (code) => {
  await rm(sandbox, { force: true, recursive: true })
  process.exit(code ?? 0)
})
