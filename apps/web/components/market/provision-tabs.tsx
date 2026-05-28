"use client"

import { useRef, useState, type KeyboardEvent, type ReactNode } from "react"

export type ProvisionTab = {
  id: string
  label: string
  count?: number
  content: ReactNode
}

export function ProvisionTabs({
  tabs,
  initialId,
}: {
  tabs: ProvisionTab[]
  initialId?: string
}) {
  const [activeId, setActiveId] = useState(initialId ?? tabs[0]?.id ?? "")
  const tabRefs = useRef<Record<string, HTMLButtonElement | null>>({})

  const focusTab = (id: string) => {
    setActiveId(id)
    requestAnimationFrame(() => tabRefs.current[id]?.focus())
  }

  const onKey = (event: KeyboardEvent<HTMLButtonElement>) => {
    const idx = tabs.findIndex((tab) => tab.id === activeId)
    if (idx < 0) return
    if (event.key === "ArrowRight") {
      event.preventDefault()
      focusTab(tabs[(idx + 1) % tabs.length].id)
    } else if (event.key === "ArrowLeft") {
      event.preventDefault()
      focusTab(tabs[(idx - 1 + tabs.length) % tabs.length].id)
    } else if (event.key === "Home") {
      event.preventDefault()
      focusTab(tabs[0].id)
    } else if (event.key === "End") {
      event.preventDefault()
      focusTab(tabs[tabs.length - 1].id)
    }
  }

  return (
    <div className="provision-tabs">
      <div role="tablist" aria-label="Provision detail tabs" className="provision-tab-strip">
        {tabs.map((tab) => {
          const active = tab.id === activeId
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              id={`tab-${tab.id}`}
              ref={(node) => {
                tabRefs.current[tab.id] = node
              }}
              aria-selected={active}
              aria-controls={`panel-${tab.id}`}
              tabIndex={active ? 0 : -1}
              className={active ? "provision-tab active" : "provision-tab"}
              onClick={() => setActiveId(tab.id)}
              onKeyDown={onKey}
            >
              {tab.label}
              {typeof tab.count === "number" && <span>{tab.count}</span>}
            </button>
          )
        })}
      </div>

      {tabs.map((tab) => {
        const active = tab.id === activeId
        return (
          <section
            key={tab.id}
            role="tabpanel"
            id={`panel-${tab.id}`}
            aria-labelledby={`tab-${tab.id}`}
            hidden={!active}
            className="provision-tab-panel"
          >
            {tab.content}
          </section>
        )
      })}
    </div>
  )
}
