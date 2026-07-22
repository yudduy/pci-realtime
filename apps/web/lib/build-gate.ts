export function snapshotGateEnabled() {
  return process.env.PCI_REQUIRE_LIVE_SNAPSHOT === "1"
}

export function assertSnapshotUsable(
  context: string,
  connected: boolean,
  viewErrors: string[],
) {
  if (!snapshotGateEnabled() || (connected && viewErrors.length === 0)) return

  const failures = [
    ...(!connected ? ["registry is disconnected"] : []),
    ...(viewErrors.length ? [`failing views: ${viewErrors.join(", ")}`] : []),
  ]
  throw new Error(`[snapshot-gate] ${context}: ${failures.join("; ")}`)
}
