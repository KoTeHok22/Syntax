import type { Invitation } from '../api/platform'

interface Step {
  key: string
  label: string
  at: string | null
  icon: string
  tone: 'done' | 'current' | 'pending' | 'stopped'
}

function formatMoment(value: string | null): string {
  if (value === null) return ''
  return new Date(value).toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}

function buildSteps(invitation: Invitation): Step[] {
  const sent: Step = { key: 'sent', label: 'Отправлено', at: invitation.created_at, icon: 'send', tone: 'done' }
  const viewed: Step = {
    key: 'viewed',
    label: 'Просмотрено',
    at: invitation.viewed_at,
    icon: 'visibility',
    tone: invitation.viewed_at !== null ? 'done' : invitation.status === 'sent' ? 'current' : 'pending',
  }
  if (invitation.status === 'withdrawn') {
    return [sent, { key: 'viewed', label: 'Просмотрено', at: invitation.viewed_at, icon: 'visibility', tone: invitation.viewed_at ? 'done' : 'pending' }, {
      key: 'withdrawn', label: 'Отозвано', at: invitation.responded_at, icon: 'undo', tone: 'stopped',
    }]
  }
  const finalLabel = invitation.status === 'rejected' ? 'Отклонено' : 'Принято'
  const finalIcon = invitation.status === 'rejected' ? 'cancel' : 'check_circle'
  const final: Step = {
    key: 'final',
    label: finalLabel,
    at: invitation.responded_at,
    icon: finalIcon,
    tone: invitation.responded_at !== null ? (invitation.status === 'rejected' ? 'stopped' : 'done') : invitation.status === 'viewed' ? 'current' : 'pending',
  }
  return [sent, viewed, final]
}

const TONE_CLASS: Record<Step['tone'], string> = {
  done: 'bg-pvn-blue text-white',
  current: 'bg-pvn-blue/20 text-pvn-blue',
  pending: 'bg-sunken text-ink-muted',
  stopped: 'bg-pvn-red/15 text-pvn-red-ink',
}

const LABEL_CLASS: Record<Step['tone'], string> = {
  done: 'text-ink font-semibold',
  current: 'text-ink font-semibold',
  pending: 'text-ink-muted',
  stopped: 'text-pvn-red-ink font-semibold',
}

export function InvitationTimeline({ invitation }: { invitation: Invitation }) {
  const steps = buildSteps(invitation)
  return (
    <ol className="flex flex-wrap items-center gap-x-2 gap-y-2">
      {steps.map((step, index) => (
        <li className="flex items-center gap-2" key={step.key}>
          <span className="flex items-center gap-1.5">
            <span className={`flex h-6 w-6 items-center justify-center rounded-full ${TONE_CLASS[step.tone]}`}>
              <span className="material-symbols-outlined text-[14px] leading-none">{step.icon}</span>
            </span>
            <span className="flex flex-col leading-tight">
              <span className={`font-mono text-[11px] ${LABEL_CLASS[step.tone]}`}>{step.label}</span>
              {step.at !== null ? (
                <span className="font-mono text-[10px] text-ink-muted">{formatMoment(step.at)}</span>
              ) : null}
            </span>
          </span>
          {index < steps.length - 1 ? (
            <span className={`h-px w-6 ${step.tone === 'pending' ? 'bg-sunken' : 'bg-pvn-blue/40'}`} aria-hidden="true" />
          ) : null}
        </li>
      ))}
    </ol>
  )
}
