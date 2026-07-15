import type { Metadata } from "next"
import { baselineVerticals } from "@/lib/verticals"
import "./globals.css"

export const metadata: Metadata = {
  metadataBase: new URL("https://pcindex.vercel.app"),
  title: "PCIndex",
  description:
    "Climate-tech vertical credibility with provision-level official evidence and score attribution.",
  openGraph: {
    title: "PCIndex",
    description:
      "Climate-tech vertical credibility with provision-level official evidence and score attribution.",
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
      <head>
        <link
          rel="alternate"
          type="application/atom+xml"
          title="PCIndex policy changes"
          href="/feed.xml"
        />
        {baselineVerticals().map((vertical) => (
          <link
            key={vertical.id}
            rel="alternate"
            type="application/atom+xml"
            title={`${vertical.name} policy changes`}
            href={`/verticals/${vertical.id}/feed.xml`}
          />
        ))}
      </head>
      <body>{children}</body>
    </html>
  )
}
