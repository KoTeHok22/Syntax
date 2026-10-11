import { useId, useState } from 'react'
import type { ScoreComponent } from '../api/platform'

interface ScoreBreakdownProps {
  breakdown: Record<string, ScoreComponent>
}

export function ScoreBreakdown({ breakdown }: ScoreBreakdownProps) {
  const [isOpen, setIsOpen] = useState(false)
  const panelId = useId()
  const entries = Object.entries(breakdown)
  if (entries.length === 0) return null
  return (
    <div className="flex flex-col gap-2">
      <button
        aria-controls={panelId}
        aria-expanded={isOpen}
        className="flex w-full cursor-pointer items-center gap-2 rounded-xl bg-inset px-3 py-2.5 text-left font-mono text-[12px] font-bold uppercase tracking-wider text-ink shadow-inset-sm transition-colors hover:text-pvn-blue"
        onClick={() => setIsOpen((value) => !value)}
        type="button"
      >
        <span
          className="material-symbols-outlined text-[18px] text-pvn-blue transition-transform duration-300 ease-out"
          style={{ transform: isOpen ? 'rotate(90deg)' : 'rotate(0deg)' }}
        >
          chevron_right
        </span>
        Что влияет на балл
      </button>
      <div
        className={`grid transition-[grid-template-rows,opacity] duration-200 ease-out ${
          isOpen ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'
        }`}
        id={panelId}
        role="region"
        aria-hidden={!isOpen}
      >
        <div className="overflow-hidden">
          <div className="flex flex-col gap-2.5 rounded-xl border border-ink/10 bg-inset p-3">
            {entries.map(([key, component]) => (
              <div className="flex flex-col gap-1" key={key}>
                <div className="flex items-baseline justify-between font-mono text-[11px]">
                  <span className="text-ink-secondary">{component.label}</span>
                  <span className="font-bold text-pvn-blue">{Math.round(component.value)}/100</span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-sunken shadow-inset-sm">
                  <div
                    className="bar-fill h-full rounded-full bg-pvn-blue"
                    style={{ width: `${Math.max(0, Math.min(component.value, 100))}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
