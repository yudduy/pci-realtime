"use client"

import { useRouter } from "next/navigation"
import { useCallback, useEffect, useRef, type ReactNode } from "react"

export function BottomSheet({
  title,
  eyebrow,
  children,
  onClose,
}: {
  title: string
  eyebrow?: string
  children: ReactNode
  onClose?: () => void
}) {
  const router = useRouter()
  const dialogRef = useRef<HTMLDivElement>(null)
  const previouslyFocused = useRef<Element | null>(null)

  const close = useCallback(() => {
    if (onClose) onClose()
    else router.back()
  }, [onClose, router])

  useEffect(() => {
    previouslyFocused.current = document.activeElement
    const node = dialogRef.current
    node?.focus()
    const original = document.body.style.overflow
    document.body.style.overflow = "hidden"

    const focusableSelector =
      'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])'

    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault()
        close()
        return
      }
      if (event.key !== "Tab" || !node) return
      const focusables = node.querySelectorAll<HTMLElement>(focusableSelector)
      if (focusables.length === 0) {
        event.preventDefault()
        node.focus()
        return
      }
      const first = focusables[0]
      const last = focusables[focusables.length - 1]
      const active = document.activeElement as HTMLElement | null
      if (event.shiftKey && (active === first || active === node)) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && active === last) {
        event.preventDefault()
        first.focus()
      }
    }
    window.addEventListener("keydown", onKey)
    return () => {
      window.removeEventListener("keydown", onKey)
      document.body.style.overflow = original
      if (previouslyFocused.current instanceof HTMLElement) {
        previouslyFocused.current.focus()
      }
    }
  }, [close])

  return (
    <div
      className="bottom-sheet-backdrop"
      role="presentation"
      onClick={(event) => {
        if (event.target === event.currentTarget) close()
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        className="bottom-sheet"
      >
        <button
          type="button"
          className="bottom-sheet-handle"
          aria-label="Close panel"
          onClick={close}
        />
        <header className="bottom-sheet-head">
          <div>
            {eyebrow && <p>{eyebrow}</p>}
            <h2>{title}</h2>
          </div>
          <button type="button" onClick={close} className="bottom-sheet-close" aria-label="Close">
            ×
          </button>
        </header>
        <div className="bottom-sheet-body">{children}</div>
      </div>
    </div>
  )
}
