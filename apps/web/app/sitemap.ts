import type { MetadataRoute } from "next"

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
  ]
}

