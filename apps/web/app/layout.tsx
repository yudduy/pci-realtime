import type { Metadata } from "next"
import "./globals.css"

export const metadata: Metadata = {
  metadataBase: new URL("https://pcindex.vercel.app"),
  title: "PCIndex",
  description:
    "Climate policy intelligence for official evidence, score trends, and source attribution.",
  openGraph: {
    title: "PCIndex",
    description:
      "Climate policy intelligence for official evidence, score trends, and source attribution.",
    url: "https://pcindex.vercel.app",
    siteName: "PCIndex",
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
