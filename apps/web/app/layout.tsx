import type { Metadata } from "next"
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
      <body>{children}</body>
    </html>
  )
}
