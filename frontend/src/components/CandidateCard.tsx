import { anonymousCandidateId } from '../api/platform'
import type { CandidateCard as CandidateCardData } from '../api/platform'
import { ScoreBreakdown } from './ScoreBreakdown'
import { gradeLabel, specializationLabel, formatIsoDate } from '../lib/format'

interface CandidateCardProps {
  card: CandidateCardData
  onInvite: (card: CandidateCardData) => void
  relevanceLabel?: string
}

export function CandidateCard({ card, onInvite, relevanceLabel = 'Совпадение' }: CandidateCardProps) {
  const achievements = card.pvn_achievements.slice(0, 2)
  const stack = card.stack.slice(0, 8)
  const match = card.match_breakdown
  const relevancePercent = Math.round(Math.max(0, Math.min(card.match_relevance, 1)) * 100)
  return (
    <article className="card-enter group relative flex h-full flex-col gap-4 rounded-panel border border-ink/5 bg-raised p-6 shadow-raised transition-[box-shadow,transform] duration-300 ease-out hover:-translate-y-0.5 hover:shadow-raised-lg">
      <header className="flex items-start justify-between gap-4">
        <div className="flex min-w-0 flex-col gap-1">
          <h3 className="truncate font-mono text-[20px] font-extrabold tracking-tight text-ink">
            Кандидат {anonymousCandidateId(card.candidate_profile_id)}
          </h3>
          <span className="font-mono text-[13px] font-semibold text-pvn-blue">
            {specializationLabel(card.specialization)} · {gradeLabel(card.grade)}
          </span>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          <div className="flex items-baseline gap-1 rounded-xl bg-pvn-blue/10 px-3 py-1.5">
            <span className="font-mono text-[22px] font-extrabold leading-none text-pvn-blue">{Math.round(card.score)}</span>
            <span className="font-mono text-[12px] font-semibold text-ink-secondary">/ 100</span>
          </div>
            <span className="font-mono text-[10px] uppercase tracking-wider text-ink-secondary">Оценка</span>
        </div>
      </header>

      <div className="flex min-h-[28px] flex-wrap content-start gap-1.5">
        {stack.map((technology) => (
          <span className="chip" key={technology}>
            {technology}
          </span>
        ))}
      </div>

      <div className="min-h-[44px]">
        {achievements.length > 0 ? (
          <div className="flex items-start gap-2 rounded-xl bg-inset px-3 py-2 shadow-inset-sm">
            <span className="material-symbols-outlined text-[16px] leading-none text-warn-ink">workspace_premium</span>
            <div className="flex flex-col">
              {achievements.map((achievement) => (
                <span className="font-mono text-[11px] font-semibold leading-tight text-warn-ink" key={`${achievement.type}-${achievement.date}`}>
                  ПВН: {achievement.level} ({formatIsoDate(achievement.date)})
                </span>
              ))}
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-2 rounded-xl bg-inset px-3 py-2 font-mono text-[11px] text-ink-secondary shadow-inset-sm">
            <span className="material-symbols-outlined text-[15px] text-ink-muted">info</span>
            Нет подтверждений ПВН
          </div>
        )}
      </div>

      <div className="mt-auto flex flex-col gap-4">
        <ScoreBreakdown breakdown={card.score_breakdown} />

        <div className="flex flex-col gap-2">
          <div className="flex items-baseline justify-between font-mono text-[11px] uppercase tracking-wider text-ink-secondary">
            <span>{relevanceLabel}</span>
            <span className="font-bold text-ink">{relevancePercent}%</span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-sunken shadow-inset-sm">
            <div
              className="bar-fill h-full rounded-full bg-pvn-blue"
              style={{ width: `${relevancePercent}%` }}
            />
          </div>
          <details className="font-sans text-caption text-ink-secondary">
            <summary className="cursor-pointer font-semibold text-ink focus-visible:outline-pvn-blue">Как рассчитано совпадение</summary>
            <div className="mt-2 flex flex-col gap-2">
              {match?.mode === 'semantic' || match?.mode === 'lexical' ? (
                <>
                  <dl className="flex flex-col gap-1">
                    <div className="flex flex-wrap justify-between gap-x-3">
                      <dt>Совпадение технологий</dt>
                      <dd>{Math.round(match.stack * 100)}% (вклад {Math.round(match.stack_weight * 100)}%)</dd>
                    </div>
                    {match.mode === 'semantic' && match.semantic !== null ? (
                      <div className="flex flex-wrap justify-between gap-x-3">
                        <dt>Близость опыта к задачам</dt>
                        <dd>{Math.round(match.semantic * 100)}% (вклад {Math.round(match.semantic_weight * 100)}%)</dd>
                      </div>
                    ) : null}
                  </dl>
                  <p>
                    {match.mode === 'semantic' && match.semantic !== null
                      ? 'Сравниваем технологии и смысл описания опыта с задачами вакансии. Это не вероятность успешного найма.'
                      : 'Совпадение по технологиям вакансии.'}
                  </p>
                </>
              ) : (
                <p>Совпадение по технологиям вакансии.</p>
              )}
            </div>
          </details>
        </div>

        <button className="btn-blue mt-auto w-full py-3 text-[14px]" onClick={() => onInvite(card)} type="button">
          Отправить приглашение
        </button>
      </div>
    </article>
  )
}
