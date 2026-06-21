import Link from "next/link"

const navItems = [
  { label: "About", href: "/about" },
  { label: "Connect", href: "/connect" },
  { label: "Code", href: "https://github.com/yudduy/pci-realtime" },
]

export function SiteHeader() {
  return (
    <header className="site-header">
      <div className="site-header-inner">
        <Link href="/" className="site-brand" aria-label="PCIndex home">
          <svg
            className="site-mark"
            viewBox="0 0 28 28"
            width="26"
            height="26"
            aria-hidden="true"
          >
            <rect width="28" height="28" rx="7" fill="#1652f0" />
            <path
              d="M6.5 18.5 L12 12.5 L16 15.5 L21.5 8.5"
              fill="none"
              stroke="#ffffff"
              strokeWidth="2.3"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <circle cx="21.5" cy="8.5" r="2" fill="#ffffff" />
          </svg>
          <span className="site-wordmark">
            PC<span>Index</span>
          </span>
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
