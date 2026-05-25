const repository = process.env.GITHUB_REPOSITORY?.split("/")[1]
const githubPages = process.env.GITHUB_PAGES === "true"
const githubPagesBasePath =
  githubPages && repository && !repository.endsWith(".github.io")
    ? `/${repository}`
    : undefined

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export",
  trailingSlash: true,
  basePath: githubPagesBasePath,
  assetPrefix: githubPagesBasePath ? `${githubPagesBasePath}/` : undefined,
  images: {
    unoptimized: true,
  },
}

export default nextConfig
