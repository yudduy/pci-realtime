/** @type {import('next').NextConfig} */
const nextConfig = {
  async redirects() {
    return [
      // The terminal lives at "/". Keep a clean edge-level permanent redirect for
      // the deprecated duplicate route so crawlers and old links resolve to one
      // canonical URL (no rendered duplicate page).
      { source: "/dashboard", destination: "/", permanent: true },
    ]
  },
}

export default nextConfig
