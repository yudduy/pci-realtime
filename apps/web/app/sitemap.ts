import type { MetadataRoute } from "next"
import { POLICIES } from "@/lib/policy-copy"

const baseUrl = "https://pcindex.vercel.app"

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    {
      url: baseUrl,
      changeFrequency: "hourly",
      priority: 1,
    },
    {
      url: `${baseUrl}/dashboard`,
      changeFrequency: "hourly",
      priority: 0.9,
    },
    {
      url: `${baseUrl}/about`,
      changeFrequency: "monthly",
      priority: 0.7,
    },
    {
      url: `${baseUrl}/connect`,
      changeFrequency: "monthly",
      priority: 0.6,
    },
    ...POLICIES.map((policy) => ({
      url: `${baseUrl}/policies/${policy.code}`,
      changeFrequency: "hourly" as const,
      priority: 0.8,
    })),
  ]
}
