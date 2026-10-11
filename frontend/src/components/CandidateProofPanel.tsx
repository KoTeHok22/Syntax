import type { CandidateCard as CandidateCardData } from '../api/platform'

function stackReason(card: CandidateCardData): string | null {
  const overlap = card.match_breakdown?.overlap
  if (!overlap || overlap.required_total === 0) return null
  if (overlap.matched_total === 0) return 'Совпадений по заявленному стеку нет'
  if (overlap.matched_total === overlap.required_total) {
    return `Стек полностью совпадает с требованиями (${overlap.matched_total} из ${overlap.required_total})`
  }
  return `Совпадает часть стека: ${overlap.matched_total} из ${overlap.required_total}`
}

function semanticReason(card: CandidateCardData): string | null {
  const match = card.match_breakdown
  if (!match || match.mode !== 'semantic' || match.semantic === null) return null
  const score = match.semantic
  if (score >= 0.75) return 'Опыт по смыслу очень близок к задачам вакансии'
  if (score >= 0.5) return 'Опыт по смыслу заметно близок к задачам вакансии'
  return 'Опыт по смыслу частично пересекается с задачами вакансии'
}

function testReason(card: CandidateCardData): string | null {
  const test = card.score_breakdown?.test_score
  if (!test) return null
  if (test.value >= 75) return 'Сильный результат подтверждающего теста'
  if (test.value >= 50) return 'Средний результат подтверждающего теста'
  return 'Слабый результат подтверждающего теста'
}

function completenessReason(card: CandidateCardData): string | null {
  const completeness = card.score_breakdown?.profile_completeness
  if (!completeness) return null
  if (completeness.value >= 75) return 'Профиль заполнен подробно'
  if (completeness.value >= 50) return 'Профиль заполнен частично'
  return 'Профиль заполнен слабо'
}

function buildReasons(card: CandidateCardData): string[] {
  const reasons = [
    stackReason(card),
    semanticReason(card),
    testReason(card),
    completenessReason(card),
  ].filter((reason): reason is string => reason !== null)
  return reasons.slice(0, 4)
}

interface CandidateProofPanelProps {
  card: CandidateCardData
}

export function CandidateProofPanel({ card }: CandidateProofPanelProps) {
  const verified = card.is_verified || card.proof_tier === 'verified'
  const reasons = buildReasons(card)
  return (
    <div className="flex flex-col gap-3 rounded-panel border border-ink/5 bg-raised p-5 shadow-raised">
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 font-sans text-[12px] font-semibold ${
            verified ? 'bg-good/15 text-good-ink' : 'bg-warn/15 text-warn-ink'
          }`}
        >
          <span className="material-symbols-outlined text-[15px] leading-none">
            {verified ? 'verified_user' : 'help'}
          </span>
          {verified ? 'Подтверждён тестом' : 'Не подтверждён тестом'}
        </span>
        <span className="font-sans text-[12px] text-ink-secondary">
          {verified
            ? 'Пройден подтверждающий тест под наблюдением'
            : 'Навыки указаны самим кандидатом, тест ещё не пройден'}
        </span>
      </div>

      {reasons.length > 0 ? (
        <div className="flex flex-col gap-1.5">
          <span className="font-mono text-[11px] uppercase tracking-wider text-ink-secondary">
            Почему в выдаче
          </span>
          <ul className="flex flex-col gap-1">
            {reasons.map((reason) => (
              <li className="flex items-start gap-2 font-sans text-[13px] text-ink" key={reason}>
                <span className="material-symbols-outlined mt-0.5 text-[15px] leading-none text-pvn-blue">
                  check_circle
                </span>
                <span>{reason}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  )
}
