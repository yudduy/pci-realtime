import type { Metadata } from "next"
import "./globals.css"

export const metadata: Metadata = {
  metadataBase: new URL("https://pcindex.vercel.app"),
  title: "PCIndex",
  description: "Live policy-market tracker for IRA credibility and public market forecasts.",
  openGraph: {
    title: "PCIndex",
    description: "Live policy-market tracker for IRA credibility and public market forecasts.",
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
