import { redirect } from "next/navigation"

// The terminal lives at "/"; "/dashboard" is kept only as a stable redirect
// so previously shared links and sitemap entries do not break.
export default function DashboardPage() {
  redirect("/")
}
