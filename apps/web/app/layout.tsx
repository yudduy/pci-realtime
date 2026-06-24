import type { Metadata } from "next"
import { IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google"
import "./globals.css"

// IBM Plex is the intended institutional voice; Mono carries the numeric/terminal
// data layer. Self-hosted by next/font (no external <link>), swap to avoid FOIT.
const plexSans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-plex-sans",
  display: "swap",
})

const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-plex-mono",
  display: "swap",
})

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
    <html lang="en" className={`${plexSans.variable} ${plexMono.variable}`}>
      <body>{children}</body>
    </html>
  )
}
