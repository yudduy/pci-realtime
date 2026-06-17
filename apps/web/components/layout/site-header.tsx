import Image from "next/image"
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
          <Image
            className="site-logo"
            src="/pcindex-logo.svg"
            alt=""
            width={58}
            height={32}
            priority
            aria-hidden="true"
          />
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
