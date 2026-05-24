import type { Metadata } from "next"
import "./globals.css"

export const metadata: Metadata = {
  title: "PCI Markets",
  description: "Policy credibility forecasts and gated market proposals.",
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
