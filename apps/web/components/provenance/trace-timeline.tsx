import type { TraceStep } from "@/lib/provenance"

export function TraceTimeline({ steps }: { steps: TraceStep[] }) {
  return (
    <ol className="trace-timeline" aria-label="Evidence path">
      {steps.map((step) => (
        <li key={step.id} className={`trace-step ${step.status}`}>
          <span aria-hidden="true" />
          <div>
            <strong>{step.label}</strong>
            <p>{step.detail}</p>
          </div>
        </li>
      ))}
    </ol>
  )
}
