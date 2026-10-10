export type StatusTone = 'info' | 'success' | 'warn' | 'danger' | 'neutral'

const TONE_CLASS: Record<StatusTone, string> = {
  info: 'bg-pvn-blue/10 text-pvn-blue',
  success: 'bg-good/15 text-good-ink',
  warn: 'bg-warn/15 text-warn-ink',
  danger: 'bg-pvn-red/10 text-pvn-red-ink',
  neutral: 'bg-sunken text-ink-secondary',
}

export function statusPill(tone: StatusTone): string {
  return TONE_CLASS[tone]
}
