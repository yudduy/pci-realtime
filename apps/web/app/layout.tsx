import type { Metadata } from "next"
import "./globals.css"

export const metadata: Metadata = {
  metadataBase: new URL("https://pcindex.vercel.app"),
  title: "PCIndex",
  description: "Track IRA climate policy updates, public market coverage, and model estimates.",
  openGraph: {
    title: "PCIndex",
    description: "Track IRA climate policy updates, public market coverage, and model estimates.",
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
