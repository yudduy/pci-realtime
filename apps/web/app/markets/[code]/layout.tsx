import type { ReactNode } from "react"

export default function ProvisionLayout({
  children,
  drawer,
}: {
  children: ReactNode
  drawer: ReactNode
}) {
  return (
    <>
      {children}
      {drawer}
    </>
  )
}
