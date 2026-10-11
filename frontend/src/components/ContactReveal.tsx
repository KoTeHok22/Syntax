import { useState } from 'react'

const CONTACT_META: Record<string, { label: string; icon: string; href?: (value: string) => string }> = {
  telegram: { label: 'Telegram', icon: 'send', href: (value) => `https://t.me/${value.replace(/^@/, '')}` },
  email: { label: 'Email', icon: 'mail', href: (value) => `mailto:${value}` },
  phone: { label: 'Телефон', icon: 'call', href: (value) => `tel:${value.replace(/[^+\d]/g, '')}` },
}

function displayValue(key: string, value: string): string {
  if (key === 'telegram' && !value.startsWith('@')) return `@${value}`
  return value
}

export function ContactReveal({ contacts, companyName }: { contacts: Record<string, string>; companyName: string | null }) {
  const [copiedKey, setCopiedKey] = useState<string | null>(null)
  const entries = Object.entries(contacts).filter(([, value]) => typeof value === 'string' && value.trim() !== '')

  const copy = async (key: string, value: string) => {
    const done = () => {
      setCopiedKey(key)
      window.setTimeout(() => setCopiedKey((current) => (current === key ? null : current)), 2000)
    }
    try {
      if (navigator.clipboard !== undefined && window.isSecureContext) {
        await navigator.clipboard.writeText(value)
        done()
        return
      }
    } catch {
      /* fall through to legacy copy */
    }
    try {
      const helper = document.createElement('textarea')
      helper.value = value
      helper.setAttribute('readonly', '')
      helper.style.position = 'absolute'
      helper.style.left = '-9999px'
      document.body.appendChild(helper)
      helper.select()
      document.execCommand('copy')
      document.body.removeChild(helper)
      done()
    } catch {
      setCopiedKey(null)
    }
  }

  if (entries.length === 0) {
    return (
      <div className="flex flex-col gap-3 rounded-xl bg-good/10 p-4">
        <span className="font-mono text-[11px] font-bold uppercase tracking-wider text-good-ink">Контакты открыты</span>
        <span className="font-sans text-caption text-ink-secondary">Кандидат подтвердил согласие, но ещё не заполнил контакты в профиле.</span>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3 rounded-xl bg-good/10 p-4">
      <div className="flex items-center gap-2">
        <span className="material-symbols-outlined text-[18px] text-good-ink">lock_open</span>
        <span className="font-mono text-[11px] font-bold uppercase tracking-wider text-good-ink">Контакты открыты</span>
      </div>
      <div className="flex flex-col gap-3">
        {entries.map(([key, value]) => {
          const meta = CONTACT_META[key] ?? { label: key, icon: 'alternate_email' }
          const shown = displayValue(key, value)
          return (
            <div className="flex flex-wrap items-center gap-3" key={key}>
              <span className="material-symbols-outlined text-[20px] text-good-ink">{meta.icon}</span>
              <div className="flex min-w-0 flex-col">
                <span className="font-mono text-[10px] uppercase tracking-wider text-ink-muted">{meta.label}</span>
                {meta.href !== undefined ? (
                  <a className="truncate font-mono text-[14px] font-semibold text-ink hover:text-pvn-blue hover:underline" href={meta.href(value)} rel="noreferrer" target="_blank">
                    {shown}
                  </a>
                ) : (
                  <span className="truncate font-mono text-[14px] font-semibold text-ink">{shown}</span>
                )}
              </div>
              <button
                className="btn-ghost ml-auto shrink-0 py-1.5 text-[12px]"
                onClick={() => void copy(key, shown)}
                type="button"
              >
                <span className="material-symbols-outlined text-[16px]">{copiedKey === key ? 'check' : 'content_copy'}</span>
                {copiedKey === key ? 'Скопировано' : 'Копировать'}
              </button>
            </div>
          )
        })}
      </div>
      {companyName !== null ? (
        <span className="font-sans text-caption text-ink-secondary">Напишите первым — это ваше приглашение от «{companyName}».</span>
      ) : null}
    </div>
  )
}
