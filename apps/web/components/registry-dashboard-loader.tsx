"use client"

import { useEffect, useState } from "react"
import {
  emptyRegistryData,
  getRegistryData,
  type RegistryData,
} from "@/lib/data"
import { RegistryDashboard } from "@/components/registry-dashboard"

export function RegistryDashboardLoader() {
  const [data, setData] = useState<RegistryData>(() => emptyRegistryData())

  useEffect(() => {
    let cancelled = false

    getRegistryData()
      .then((registryData) => {
        if (!cancelled) setData(registryData)
      })
      .catch((error: unknown) => {
        if (cancelled) return
        const message = error instanceof Error ? error.message : String(error)
        setData(emptyRegistryData([`dashboard: ${message}`]))
      })

    return () => {
      cancelled = true
    }
  }, [])

  return <RegistryDashboard data={data} />
}
