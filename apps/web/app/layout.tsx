import type { Metadata } from "next"
import "./globals.css"

export const metadata: Metadata = {
  metadataBase: new URL("https://pcindex.vercel.app"),
  title: "Policy Intelligence Desk",
  description:
    "Policy intelligence for reviewed briefs, verified evidence, tracked theses, and a derived credibility signal.",
  openGraph: {
    title: "Policy Intelligence Desk",
    description:
      "Policy intelligence for reviewed briefs, verified evidence, tracked theses, and a derived credibility signal.",
    url: "https://pcindex.vercel.app",
    siteName: "Policy Intelligence Desk",
    type: "website",
  },
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
