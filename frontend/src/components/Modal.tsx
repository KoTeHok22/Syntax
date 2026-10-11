import { useEffect, useRef } from 'react'
import type { ReactNode } from 'react'

interface ModalProps {
  open: boolean
  onClose: () => void
  labelledBy?: string
  children: ReactNode
  panelClassName?: string
}

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

export const modalPanelClass = 'relative w-full max-w-2xl overflow-hidden rounded-panel bg-raised shadow-raised-lg'
export const modalColumnClass = 'flex min-h-0 flex-1 flex-col overflow-hidden'
export const modalBodyClass = 'flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto overscroll-contain p-6'
export const modalFooterClass = 'flex shrink-0 flex-col items-stretch gap-3 border-t border-ink/10 bg-raised px-6 pb-4 pt-4 sm:flex-row sm:items-center sm:justify-end'

export function Modal({ open, onClose, labelledBy, children, panelClassName }: ModalProps) {
  const panelRef = useRef<HTMLDivElement>(null)
  const previouslyFocused = useRef<HTMLElement | null>(null)

  useEffect(() => {
    if (!open) return
    previouslyFocused.current = document.activeElement as HTMLElement | null
    const panel = panelRef.current
    const first = panel?.querySelector<HTMLElement>(FOCUSABLE)
    first?.focus()

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        onClose()
        return
      }
      if (event.key !== 'Tab' || panel === null) return
      const focusable = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE)).filter((node) => node.offsetParent !== null)
      if (focusable.length === 0) return
      const firstEl = focusable[0]
      const lastEl = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === firstEl) {
        event.preventDefault()
        lastEl.focus()
      } else if (!event.shiftKey && document.activeElement === lastEl) {
        event.preventDefault()
        firstEl.focus()
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      previouslyFocused.current?.focus()
    }
  }, [open, onClose])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-pvn-dark/50 p-4 backdrop-blur-sm"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div
        aria-labelledby={labelledBy}
        aria-modal="true"
        className={`my-auto flex max-h-[calc(100dvh-2rem)] min-h-0 flex-col ${panelClassName ?? modalPanelClass}`}
        ref={panelRef}
        role="dialog"
      >
        {children}
      </div>
    </div>
  )
}
