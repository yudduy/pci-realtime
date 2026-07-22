import type { MetadataRoute } from "next"
import { POLICIES } from "@/lib/policy-copy"
import { SITE_URL } from "@/lib/site"

const baseUrl = SITE_URL

export const dynamic = "force-static"

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    {
      url: baseUrl,
      changeFrequency: "hourly",
      priority: 1,
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
    {
      url: `${baseUrl}/paper.pdf`,
      changeFrequency: "yearly",
      priority: 0.5,
    },
    {
      url: `${baseUrl}/si-appendix.pdf`,
      changeFrequency: "yearly",
      priority: 0.4,
    },
    ...POLICIES.map((policy) => ({
      url: `${baseUrl}/policies/${policy.code}`,
      changeFrequency: "hourly" as const,
      priority: 0.8,
    })),
  ]
}
