import type { Metadata } from "next"
import "./globals.css"

export const metadata: Metadata = {
  title: "Energy Odds",
  description: "Simple energy policy odds backed by PCI and live market scans.",
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
