import type { Metadata } from "next"
import { SITE_URL } from "@/lib/site"
import "./globals.css"

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: "PCIndex",
  description:
    "Climate-tech vertical credibility with provision-level official evidence and score attribution.",
  alternates: {
    types: {
      "application/atom+xml": [
        { url: `${SITE_URL}/feed.xml`, title: "PCIndex policy changes" },
      ],
    },
  },
  openGraph: {
    title: "PCIndex",
    description:
      "Climate-tech vertical credibility with provision-level official evidence and score attribution.",
    url: SITE_URL,
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
