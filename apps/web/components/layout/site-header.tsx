import Link from "next/link"

const navItems = [
  { label: "Tracker", href: "/dashboard" },
  { label: "About", href: "/about" },
  { label: "Code", href: "https://github.com/yudduy/pci-realtime" },
  {
    label: "Paper",
    href: "https://github.com/yudduy/pci-realtime/blob/main/Research_report.pdf",
  },
]

export function SiteHeader() {
  return (
    <header className="site-header">
      <div className="site-header-inner">
        <Link href="/" className="site-brand" aria-label="PCIndex home">
          <span className="site-mark">PCI</span>
          <span>PCIndex</span>
        </Link>
        <nav className="site-nav" aria-label="Primary navigation">
          {navItems.map((item) => {
            if (item.href.startsWith("http")) {
              return (
                <a key={item.label} href={item.href}>
                  {item.label}
                </a>
              )
            }

            return (
              <Link key={item.label} href={item.href}>
                {item.label}
              </Link>
            )
          })}
        </nav>
      </div>
    </header>
  )
}
