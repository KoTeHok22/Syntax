import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { fetchMyApplications } from '../api/platform'
import type { Application } from '../api/platform'

interface VacancyOption {
  vacancyId: number
  title: string
}

const statusLabels: Record<string, string> = {
  new: 'Отклик отправлен',
  viewed: 'Отклик просмотрен',
  accepted: 'Отклик принят',
  rejected: 'Отклик отклонён',
}

export function CandidateVacancyPicker({ activeVacancyId }: { activeVacancyId: number | null }) {
  const navigate = useNavigate()
  const [applications, setApplications] = useState<Application[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      setApplications(await fetchMyApplications())
    } catch {
      setError('Не удалось загрузить список вакансий')
      setApplications([])
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  if (isLoading) {
    return <div className="h-24 animate-pulse rounded-panel bg-inset" />
  }

  if (error !== null) {
    return (
      <div className="flex items-start gap-3 rounded-panel bg-pvn-red/10 px-5 py-4 font-sans text-caption text-pvn-red-ink shadow-raised-sm">
        <span className="material-symbols-outlined shrink-0 text-[18px]">error</span>
        <span>{error}</span>
      </div>
    )
  }

  if (applications.length === 0) {
    return (
      <div className="flex flex-col items-center gap-3 rounded-panel bg-raised p-12 text-center text-ink-secondary shadow-raised">
        <span className="material-symbols-outlined text-[48px] text-ink-muted">work_outline</span>
        <span className="font-mono text-h2 font-semibold text-ink">Заданий пока нет</span>
        <span className="max-w-md font-sans text-body">
          Откликнитесь на вакансию, чтобы получить задания от работодателя.
        </span>
        <div className="flex flex-wrap items-center justify-center gap-3">
          <Link className="btn-primary" to="/candidate/vacancies">Найти вакансию</Link>
          <Link className="btn-ghost" to="/candidate/applications">Мои отклики</Link>
        </div>
      </div>
    )
  }

  const options: VacancyOption[] = applications.map((application) => ({
    vacancyId: application.vacancy_id,
    title: application.vacancy_title ?? `Вакансия ${application.id}`,
  }))
  const statusByVacancy = new Map(applications.map((application) => [application.vacancy_id, application.status]))

  return (
    <div className="flex flex-col gap-3 rounded-panel bg-raised p-5 shadow-raised">
      <label className="label-cap" htmlFor="candidate-vacancy-picker">Вакансия</label>
      <select
        className="field cursor-pointer py-2.5"
        id="candidate-vacancy-picker"
        onChange={(event) => navigate(`/candidate/regular-tasks?vacancy=${event.target.value}`)}
        value={activeVacancyId ?? ''}
      >
        <option disabled value="">Выберите вакансию</option>
        {options.map((option) => (
          <option key={option.vacancyId} value={option.vacancyId}>{option.title}</option>
        ))}
      </select>
      <p className="font-sans text-caption text-ink-secondary">
        Задания доступны по вакансиям, на которые вы откликнулись.
      </p>
      {activeVacancyId !== null && statusByVacancy.has(activeVacancyId) ? (
        <span className="stat-pill w-fit bg-inset text-ink-secondary">
          {statusLabels[statusByVacancy.get(activeVacancyId) ?? ''] ?? 'Отклик отправлен'}
        </span>
      ) : null}
    </div>
  )
}
