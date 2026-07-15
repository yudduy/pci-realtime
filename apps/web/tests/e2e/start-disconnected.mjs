import { spawn } from "node:child_process"
import { cp, mkdir, rm, symlink } from "node:fs/promises"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

const webRoot = join(dirname(fileURLToPath(import.meta.url)), "../..")
const sandbox = join(webRoot, ".next/e2e-disconnected")
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

const env = { ...process.env }
for (const name of [
  "NEXT_PUBLIC_SUPABASE_URL",
  "SUPABASE_URL",
  "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY",
  "NEXT_PUBLIC_SUPABASE_ANON_KEY",
  "SUPABASE_ANON_KEY",
  "SUPABASE_PUBLISHABLE_KEY",
]) {
  delete env[name]
}

const child = spawn(
  process.execPath,
  [
    join(webRoot, "node_modules/next/dist/bin/next"),
    "dev",
    "--hostname",
    "127.0.0.1",
    "--port",
    "8512",
    "--webpack",
  ],
  { cwd: sandbox, env, stdio: "inherit" },
)

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.once(signal, () => child.kill(signal))
}

child.once("exit", async (code) => {
  await rm(sandbox, { force: true, recursive: true })
  process.exit(code ?? 0)
})
