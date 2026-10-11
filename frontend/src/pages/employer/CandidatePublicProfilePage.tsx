import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ApiError } from '../../api/client'
import { anonymousCandidateId, fetchCandidatePublicProfile } from '../../api/platform'
import type { CandidatePublicProfile } from '../../api/platform'
import { formatExperience, formatIsoDate, gradeLabel, specializationLabel } from '../../lib/format'
import { StackProofBadges } from '../../components/StackProofBadges'
import { workFormatLabel } from '../../components/workFormat'

function matchReasons(profile: CandidatePublicProfile): string[] {
  const reasons: string[] = []
  const verified = profile.stack_proof.filter((item) => item.proof === 'verified')
  if (verified.length > 0) {
    reasons.push(
      `${verified.length} ${verified.length === 1 ? 'навык подтверждён' : 'навыка подтверждены'} тестом`,
    )
  }
  reasons.push(
    profile.is_verified
      ? 'Профиль подтверждён результатами тестирования'
      : 'Навыки заявлены кандидатом, тест ещё не пройден',
  )
  if (profile.pvn_achievements.length > 0) reasons.push('Есть достижения в ПВН')
  if (profile.city.trim() !== '' || workFormatLabel(profile.work_format) !== '') {
    reasons.push('Город и формат работы указаны в анкете')
  }
  return reasons
}

export function CandidatePublicProfilePage() {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const [searchParams] = useSearchParams()
  const [profile, setProfile] = useState<CandidatePublicProfile | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const vacancyParam = searchParams.get('vacancy_id')
  const vacancyId = vacancyParam !== null && Number.isFinite(Number(vacancyParam)) ? Number(vacancyParam) : undefined

  const load = useCallback(async (signal?: AbortSignal) => {
    const candidateId = Number(id)
    if (!Number.isFinite(candidateId) || candidateId <= 0) {
      setError('Кандидат не найден')
      setIsLoading(false)
      return
    }
    setIsLoading(true)
    setError(null)
    try {
      const loaded = await fetchCandidatePublicProfile(candidateId, vacancyId, signal)
      if (signal?.aborted) return
      setProfile(loaded)
    } catch (exception) {
      if (signal?.aborted) return
      if (exception instanceof ApiError && exception.status === 404) setError('Профиль недоступен: кандидат скрыт или не найден')
      else if (exception instanceof ApiError) setError(exception.detail)
      else setError('Не удалось загрузить профиль')
    } finally {
      if (!signal?.aborted) setIsLoading(false)
    }
  }, [id, vacancyId])

  useEffect(() => {
    const controller = new AbortController()
    void load(controller.signal)
    return () => controller.abort()
  }, [load])

  if (isLoading) {
    return (
      <div className="mx-auto flex w-full max-w-[1000px] flex-col gap-6 px-4 py-8 sm:px-6">
        <div className="h-9 w-1/3 animate-pulse rounded-lg bg-inset" />
        <div className="h-96 animate-pulse rounded-panel bg-raised shadow-raised" />
      </div>
    )
  }

  if (profile === null) {
    return (
      <div className="mx-auto flex w-full max-w-[1000px] flex-col gap-4 px-4 py-8 sm:px-6">
        <button className="btn-ghost self-start py-2 text-[13px]" onClick={() => navigate(-1)} type="button">
          <span className="material-symbols-outlined text-[18px]">arrow_back</span>
          Назад к поиску
        </button>
        <div className="flex items-center gap-3 rounded-panel bg-pvn-red/10 px-5 py-4 font-sans text-caption text-pvn-red-ink shadow-raised-sm" role="alert">
          <span aria-hidden="true" className="material-symbols-outlined text-[18px]">error</span>
          <span>{error ?? 'Профиль недоступен'}</span>
          <button className="ml-auto font-mono font-semibold underline" onClick={() => void load()} type="button">
            Повторить
          </button>
        </div>
      </div>
    )
  }

  const location = [profile.city.trim(), workFormatLabel(profile.work_format)].filter((part) => part.length > 0).join(' · ')
  const reasons = matchReasons(profile)

  return (
    <div className="mx-auto flex w-full max-w-[1000px] flex-col gap-6 px-4 py-8 sm:px-6">
      <button className="btn-ghost self-start py-2 text-[13px]" onClick={() => navigate(-1)} type="button">
        <span className="material-symbols-outlined text-[18px]">arrow_back</span>
        Назад к поиску
      </button>

      <div className="flex flex-wrap items-center gap-3">
        <h1 className="font-mono text-display font-extrabold tracking-tight text-ink">
          Кандидат {anonymousCandidateId(profile.candidate_profile_id)}
        </h1>
        <span className={`stat-pill ${profile.is_verified ? 'bg-good/15 text-good-ink' : 'bg-warn/15 text-warn-ink'}`}>
          {profile.is_verified ? 'Подтверждён тестом' : 'Не подтверждён тестом'}
        </span>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <section className="flex flex-col gap-5 lg:col-span-2">
          <div className="flex flex-col gap-3 rounded-panel bg-raised p-6 shadow-raised">
            <span className="label-cap">Основное</span>
            <div className="grid grid-cols-1 gap-x-8 gap-y-2 sm:grid-cols-2">
              <div className="flex items-center justify-between gap-3 border-b border-ink/10 py-2.5">
                <span className="label-cap">Специализация</span>
                <span className="font-mono text-[13px] font-semibold text-ink">{specializationLabel(profile.specialization) || '—'}</span>
              </div>
              <div className="flex items-center justify-between gap-3 border-b border-ink/10 py-2.5">
                <span className="label-cap">Грейд</span>
                <span className="font-mono text-[13px] font-semibold text-ink">{gradeLabel(profile.grade) || '—'}</span>
              </div>
              <div className="flex items-center justify-between gap-3 border-b border-ink/10 py-2.5">
                <span className="label-cap">Опыт</span>
                <span className="font-mono text-[13px] font-semibold text-ink">{formatExperience(profile.years_of_experience)}</span>
              </div>
              <div className="flex items-center justify-between gap-3 border-b border-ink/10 py-2.5">
                <span className="label-cap">Город и формат</span>
                <span className="font-mono text-[13px] font-semibold text-ink">{location === '' ? '—' : location}</span>
              </div>
            </div>
          </div>

          <div className="flex flex-col gap-3 rounded-panel bg-raised p-6 shadow-raised">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <span className="label-cap">Стек и проверка навыков</span>
              <span className="font-sans text-caption text-ink-secondary">Проверен тестом — навык подтверждён результатами ПВН</span>
            </div>
            <StackProofBadges items={profile.stack_proof} />
          </div>

          {profile.soft_skills.length > 0 ? (
            <div className="flex flex-col gap-3 rounded-panel bg-raised p-6 shadow-raised">
              <span className="label-cap">Soft skills</span>
              <div className="flex flex-wrap gap-2">
                {profile.soft_skills.map((skill) => (
                  <span className="chip" key={skill}>{skill}</span>
                ))}
              </div>
            </div>
          ) : null}

          {profile.pvn_achievements.length > 0 ? (
            <div className="flex flex-col gap-3 rounded-panel bg-raised p-6 shadow-raised">
              <span className="label-cap">Достижения ФСП</span>
              <ul className="flex flex-col divide-y divide-ink/10">
                {profile.pvn_achievements.map((achievement, index) => (
                  <li className="flex items-center justify-between gap-4 py-2.5 first:pt-0 last:pb-0" key={`${achievement.type}-${achievement.level}-${index}`}>
                    <span className="flex items-center gap-2 font-sans text-[13px] text-ink">
                      <span aria-hidden="true" className="material-symbols-outlined text-[16px] leading-none text-warn-ink">workspace_premium</span>
                      {achievement.type}
                    </span>
                    <span className="font-mono text-[12px] text-ink-secondary">
                      {achievement.date !== undefined ? `${achievement.level} · ${formatIsoDate(achievement.date)}` : achievement.level}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </section>

        <aside className="flex flex-col gap-5 lg:col-span-1">
          <div className="flex flex-col gap-3 rounded-panel bg-raised p-6 shadow-raised">
            <span className="label-cap">Почему в выдаче</span>
            <ul className="flex flex-col gap-2">
              {reasons.map((reason) => (
                <li className="flex items-start gap-2 font-sans text-caption text-ink" key={reason}>
                  <span aria-hidden="true" className="material-symbols-outlined mt-0.5 text-[15px] leading-none text-pvn-blue">check_circle</span>
                  <span>{reason}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="flex items-start gap-2 rounded-panel bg-inset p-5 shadow-inset-sm">
            <span aria-hidden="true" className="material-symbols-outlined text-[18px] text-ink-secondary">visibility_off</span>
            <span className="font-sans text-caption text-ink-secondary">
              Анкета анонимна: имя, контакты и фото скрыты. Они раскроются, если кандидат примет ваше приглашение.
            </span>
          </div>
        </aside>
      </div>
    </div>
  )
}
