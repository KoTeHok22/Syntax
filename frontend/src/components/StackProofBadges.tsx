import type { StackProofItem } from '../api/platform'

interface StackProofBadgesProps {
  items: StackProofItem[]
}

export function StackProofBadges({ items }: StackProofBadgesProps) {
  if (items.length === 0) {
    return <span className="font-sans text-caption text-ink-secondary">Стек не указан</span>
  }
  return (
    <ul className="flex flex-wrap gap-2">
      {items.map((item) => {
        const verified = item.proof === 'verified'
        return (
          <li
            className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 font-sans text-[12px] font-semibold ${
              verified ? 'bg-good/15 text-good-ink' : 'bg-inset text-ink-secondary'
            }`}
            key={item.stack}
          >
            <span>{item.stack}</span>
            <span aria-hidden="true" className="text-ink-muted">
              ·
            </span>
            <span className="inline-flex items-center gap-1">
              <span aria-hidden="true" className="material-symbols-outlined text-[14px] leading-none">
                {verified ? 'verified' : 'help'}
              </span>
              {verified ? 'Проверен тестом' : 'Заявлен'}
            </span>
          </li>
        )
      })}
    </ul>
  )
}
