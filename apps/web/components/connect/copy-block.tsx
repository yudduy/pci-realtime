"use client"

import { Check, Copy } from "lucide-react"
import { useState } from "react"

export function CopyBlock({
  label,
  value,
  language = "bash",
}: {
  label: string
  value: string
  language?: string
}) {
  const [copied, setCopied] = useState(false)

  async function copy() {
    await navigator.clipboard.writeText(value)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1800)
  }

  return (
    <div className="connect-code-block">
      <div className="connect-code-head">
        <span>{label}</span>
        <button type="button" onClick={copy} aria-label={`Copy ${label}`}>
          {copied ? <Check size={15} aria-hidden="true" /> : <Copy size={15} aria-hidden="true" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre>
        <code className={`language-${language}`}>{value}</code>
      </pre>
    </div>
  )
}
