import { useEffect } from 'react'

let busyCount = 0

export function isGenerationBusy(): boolean {
  return busyCount > 0
}

export function useGenerationGuard(busy: boolean): void {
  useEffect(() => {
    if (!busy) return
    busyCount += 1
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', onBeforeUnload)
    return () => {
      busyCount = Math.max(0, busyCount - 1)
      window.removeEventListener('beforeunload', onBeforeUnload)
    }
  }, [busy])
}
