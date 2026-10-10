import { useEffect } from 'react'

interface ToastProps {
  message: string | null
  onClose: () => void
  duration?: number
  actionLabel?: string
  onAction?: () => void
}

export function Toast({ message, onClose, duration = 5000, actionLabel, onAction }: ToastProps) {
  useEffect(() => {
    if (message === null) return
    const timer = window.setTimeout(onClose, duration)
    return () => window.clearTimeout(timer)
  }, [message, duration, onClose])

  if (message === null) return null

  return (
    <div className="fixed inset-x-4 bottom-6 z-[60] flex items-start gap-3 rounded-panel bg-pvn-dark px-5 py-4 shadow-raised-lg sm:inset-x-auto sm:bottom-auto sm:right-6 sm:top-24 sm:max-w-sm">
      <span className="material-symbols-outlined shrink-0 text-[20px] text-good">check_circle</span>
      <span className="font-sans text-caption text-white">{message}</span>
      {actionLabel !== undefined && onAction !== undefined ? (
        <button className="shrink-0 font-mono text-[12px] font-bold text-white underline hover:text-white/80" onClick={onAction} type="button">
          {actionLabel}
        </button>
      ) : null}
      <button className="ml-auto flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-white/70 hover:bg-white/10" onClick={onClose} title="Закрыть" type="button">
        <span className="material-symbols-outlined text-[16px]">close</span>
      </button>
    </div>
  )
}
