import type { Metadata } from "next"
import "./globals.css"

export const metadata: Metadata = {
  title: "PCIndex",
  description: "Live policy-market tracker for IRA credibility and public market forecasts.",
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
