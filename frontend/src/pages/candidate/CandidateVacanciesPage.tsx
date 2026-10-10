import { useCallback, useEffect, useMemo, useState } from 'react'
import { ApiError } from '../../api/client'
import { createApplication, fetchMyApplications, fetchVacancies } from '../../api/platform'
import { fetchCandidateProfile } from '../../api/auth'
import type { Application, Vacancy } from '../../api/platform'
import { Modal } from '../../components/Modal'
import { Toast } from '../../components/Toast'
import { gradeLabel } from '../../lib/format'
import { statusPill } from '../../lib/statusPill'

const grades = ['', 'junior', 'middle', 'senior']
const gradeRank: Record<string, number> = { junior: 0, middle: 1, senior: 2 }
const specializations = ['', 'backend', 'frontend', 'data', 'devops', 'mobile', 'qa']

const specializationLabels: Record<string, string> = {
  backend: 'Backend',
  frontend: 'Frontend',
  data: 'Data',
  devops: 'DevOps',
  mobile: 'Mobile',
  qa: 'QA',
}

const applicationStatusConfig: Record<Application['status'], { label: string; pill: string; icon: string }> = {
  new: { label: 'Новый', pill: statusPill('info'), icon: 'schedule' },
  viewed: { label: 'Просмотрен', pill: statusPill('info'), icon: 'visibility' },
  accepted: { label: 'Принят', pill: statusPill('success'), icon: 'check_circle' },
  rejected: { label: 'Отклонён', pill: statusPill('neutral'), icon: 'cancel' },
}

function formatSalary(from: number, to: number): string {
  return `${from.toLocaleString('ru-RU')} – ${to.toLocaleString('ru-RU')} ₽`
}

export function CandidateVacanciesPage() {
  const [gradeFilter, setGradeFilter] = useState('')
  const [specializationFilter, setSpecializationFilter] = useState('')
  const [vacancies, setVacancies] = useState<Vacancy[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedVacancy, setSelectedVacancy] = useState<Vacancy | null>(null)
  const [message, setMessage] = useState('')
  const [isApplying, setIsApplying] = useState(false)
  const [applyError, setApplyError] = useState<string | null>(null)
  const [visibleCount, setVisibleCount] = useState(9)
  const [applySuccess, setApplySuccess] = useState<string | null>(null)
  const [applications, setApplications] = useState<Application[]>([])
  const [isApplicationsLoading, setIsApplicationsLoading] = useState(true)
  const [candidateGrade, setCandidateGrade] = useState<string | null>(null)
  const [candidateSpecialization, setCandidateSpecialization] = useState<string | null>(null)

  useEffect(() => {
    fetchCandidateProfile()
      .then((profile) => {
        setCandidateGrade(profile.grade ?? null)
        setCandidateSpecialization(profile.specialization ?? null)
      })
      .catch(() => {
        setCandidateGrade(null)
        setCandidateSpecialization(null)
      })
  }, [])

  const loadVacancies = useCallback(async (grade: string, specialization: string) => {
    setIsLoading(true)
    setError(null)
    try {
      const list = await fetchVacancies({
        grade: grade === '' ? undefined : grade,
        specialization: specialization === '' ? undefined : specialization,
      })
      setVacancies(list)
    } catch (exception) {
      if (exception instanceof ApiError) setError(exception.detail)
      else setError('Не удалось связаться с сервером')
    } finally {
      setIsLoading(false)
    }
  }, [])

  const loadApplications = useCallback(async () => {
    setIsApplicationsLoading(true)
    try {
      const list = await fetchMyApplications()
      setApplications(list)
    } catch {
      setApplications([])
    } finally {
      setIsApplicationsLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadVacancies(gradeFilter, specializationFilter)
  }, [gradeFilter, specializationFilter, loadVacancies])

  useEffect(() => {
    void loadApplications()
  }, [loadApplications])

  const submitApplication = async () => {
    if (selectedVacancy === null) return
    setApplyError(null)
    setIsApplying(true)
    try {
      const created = await createApplication(selectedVacancy.id, message)
      setSelectedVacancy(null)
      setMessage('')
      setApplySuccess(`Отклик на «${selectedVacancy.title}» отправлен`)
      setApplications((previous) => [created, ...previous.filter((item) => item.id !== created.id)])
      void loadApplications()
    } catch (exception) {
      if (exception instanceof ApiError) setApplyError(exception.detail)
      else setApplyError('Не удалось связаться с сервером')
    } finally {
      setIsApplying(false)
    }
  }

  const vacancyTitleById = new Map(vacancies.map((vacancy) => [vacancy.id, vacancy.title]))
  const appliedVacancyIds = useMemo(
    () => new Set(applications.map((application) => application.vacancy_id)),
    [applications],
  )
  const rankOf = (value: string | null) => (value === null ? -1 : (gradeRank[value] ?? -1))
  const sortedVacancies = useMemo(() => {
    const withScore = vacancies.map((vacancy) => {
      const specMatch = candidateSpecialization !== null && vacancy.specialization === candidateSpecialization ? 1 : 0
      const gradeDistance = candidateGrade !== null && vacancy.grade !== null ? Math.abs(rankOf(vacancy.grade) - rankOf(candidateGrade)) : 9
      const applied = appliedVacancyIds.has(vacancy.id) ? 1 : 0
      return { vacancy, specMatch, gradeDistance, applied }
    })
    withScore.sort((a, b) => {
      if (a.applied !== b.applied) return a.applied - b.applied
      if (a.specMatch !== b.specMatch) return b.specMatch - a.specMatch
      if (a.gradeDistance !== b.gradeDistance) return a.gradeDistance - b.gradeDistance
      return b.vacancy.id - a.vacancy.id
    })
    return withScore.map((item) => item.vacancy)
  }, [vacancies, candidateSpecialization, candidateGrade, appliedVacancyIds])

  const visibleVacancies = sortedVacancies.slice(0, visibleCount)
  return (
    <div className="mx-auto flex w-full max-w-[1280px] flex-col gap-6 px-4 py-8 sm:px-6">
      <div className="flex flex-col gap-1">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="font-mono text-display font-extrabold tracking-tight text-ink">Вакансии спецтрека</h1>
        </div>
        <p className="max-w-3xl font-sans text-body text-ink-secondary">
          Отклик анонимный: контакты откроются, когда вас пригласят.
        </p>
      </div>

      <div className="flex flex-col gap-4 rounded-panel bg-raised p-5 shadow-raised-sm sm:flex-row sm:items-end">
        <div className="flex flex-1 flex-col gap-1.5">
          <label className="label-cap" htmlFor="vacancy-grade">Грейд</label>
          <select className="field cursor-pointer py-2.5" id="vacancy-grade" onChange={(event) => setGradeFilter(event.target.value)} value={gradeFilter}>
            {grades.map((item) => (<option key={item} value={item}>{item === '' ? 'Все грейды' : gradeLabel(item)}</option>))}
          </select>
        </div>
        <div className="flex flex-1 flex-col gap-1.5">
          <label className="label-cap" htmlFor="vacancy-specialization">Специализация</label>
          <select className="field cursor-pointer py-2.5" id="vacancy-specialization" onChange={(event) => setSpecializationFilter(event.target.value)} value={specializationFilter}>
            {specializations.map((item) => (
              <option key={item} value={item}>{item === '' ? 'Все специализации' : specializationLabels[item]}</option>
            ))}
          </select>
        </div>
      </div>

      {error !== null ? (
        <div className="flex items-start gap-3 rounded-panel bg-pvn-red/10 px-5 py-4 font-sans text-caption text-pvn-red-ink shadow-raised-sm">
          <span className="material-symbols-outlined shrink-0 text-[18px]">error</span>
          <span>{error}</span>
        </div>
      ) : null}

      <Toast actionLabel="Мои отклики" message={applySuccess} onAction={() => document.getElementById('my-applications')?.scrollIntoView({ behavior: 'smooth' })} onClose={() => setApplySuccess(null)} />

      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
          {[0, 1, 2, 3, 4, 5].map((index) => (
            <div className="flex animate-pulse flex-col gap-3 rounded-panel bg-raised p-6 shadow-raised" key={index}>
              <div className="h-6 w-2/3 rounded-lg bg-inset" />
              <div className="h-4 w-full rounded-lg bg-inset" />
              <div className="h-8 w-1/2 rounded-lg bg-inset" />
            </div>
          ))}
        </div>
      ) : vacancies.length === 0 ? (
        <div className="flex flex-col items-center gap-3 rounded-panel bg-raised p-12 text-center text-ink-secondary shadow-raised">
          <span className="material-symbols-outlined text-[48px] text-ink-muted">search_off</span>
          <span className="font-mono text-h2 font-semibold text-ink">Вакансий не найдено</span>
          <span className="max-w-md font-sans text-body">Попробуйте изменить фильтры по грейду и специализации.</span>
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
            {visibleVacancies.map((vacancy) => {
            const applied = appliedVacancyIds.has(vacancy.id)
            return (
              <div className="flex flex-col gap-4 rounded-panel bg-raised p-6 shadow-raised" key={vacancy.id}>
                <div className="flex items-start justify-between gap-4">
                  <div className="flex min-w-0 items-center gap-3">
                    <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-pvn-blue/10">
                      <span className="material-symbols-outlined text-[22px] text-pvn-blue">work</span>
                    </span>
                    <div className="flex min-w-0 flex-col gap-1.5">
                      <span className="font-mono text-h3 font-semibold text-ink">{vacancy.title}</span>
                      <div className="flex items-center gap-1.5">
                        {vacancy.specialization !== null ? (
                          <span className="chip-blue">{specializationLabels[vacancy.specialization] ?? vacancy.specialization}</span>
                        ) : null}
                        {vacancy.grade !== null ? (<span className="chip">{gradeLabel(vacancy.grade)}</span>) : null}
                      </div>
                    </div>
                  </div>
                  {!vacancy.is_open ? (
                    <span className="stat-pill shrink-0 bg-sunken text-ink-secondary">Закрыта</span>
                  ) : null}
                </div>

                {vacancy.description !== null ? (
                  <p className="font-sans text-caption leading-relaxed text-ink-secondary line-clamp-3">{vacancy.description}</p>
                ) : null}

                <div className="flex flex-wrap gap-1.5">
                  {vacancy.stack.map((item) => (<span className="chip" key={item}>{item}</span>))}
                </div>

                <div className="flex items-baseline justify-between rounded-xl bg-inset p-4 shadow-inset-sm">
                  <span className="font-mono text-[16px] font-extrabold text-pvn-blue">
                    {formatSalary(vacancy.salary_from, vacancy.salary_to)}
                  </span>
                  <span className="material-symbols-outlined text-[20px] text-ink-muted">payments</span>
                </div>

                <button
                  className="btn-blue mt-auto w-full py-3 text-[14px]"
                  disabled={!vacancy.is_open || applied || isApplying}
                  onClick={() => {
                    setSelectedVacancy(vacancy)
                    setMessage('')
                    setApplyError(null)
                  }}
                  type="button"
                >
                  <span className="material-symbols-outlined text-[18px]">{applied ? 'check' : 'send'}</span>
                  {applied ? 'Отклик отправлен' : !vacancy.is_open ? 'Вакансия закрыта' : 'Откликнуться'}
                </button>
              </div>
            )
          })}
          </div>
          {visibleCount < vacancies.length ? (
            <button
              className="btn-ghost mx-auto"
              onClick={() => setVisibleCount((previous) => previous + 9)}
              type="button"
            >
              <span className="material-symbols-outlined text-[18px]">expand_more</span>
              Показать ещё {Math.min(9, vacancies.length - visibleCount)}
            </button>
          ) : null}
        </div>
      )}

      <section className="flex flex-col gap-4" id="my-applications">
        <h2 className="font-mono text-h2 font-semibold text-ink">Мои отклики</h2>
        {isApplicationsLoading ? (
          <div className="flex animate-pulse flex-col gap-3 rounded-panel bg-raised p-6 shadow-raised">
            {[0, 1, 2].map((index) => (<div className="h-10 rounded-xl bg-inset" key={index} />))}
          </div>
        ) : applications.length === 0 ? (
          <div className="flex flex-col items-center gap-3 rounded-panel bg-raised py-10 text-center text-ink-secondary shadow-raised">
            <span className="material-symbols-outlined text-[36px] text-ink-muted">inbox</span>
            <span className="font-sans text-body">Откликов пока нет</span>
          </div>
        ) : (
          <div className="flex flex-col divide-y divide-ink/10 rounded-panel bg-raised p-6 shadow-raised">
            {applications.map((application) => {
              const statusConfig = applicationStatusConfig[application.status]
              const vacancyTitle = vacancyTitleById.get(application.vacancy_id) ?? `Вакансия #${application.vacancy_id}`
              return (
                <div className="flex flex-col gap-3 py-3 first:pt-0 last:pb-0" key={application.id}>
                  <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
                    <div className="flex min-w-0 items-center gap-3">
                      <span className="material-symbols-outlined shrink-0 text-[20px] text-pvn-blue">work_outline</span>
                      <div className="flex min-w-0 flex-col">
                        <span className="truncate font-mono text-[13px] font-semibold text-ink">{vacancyTitle}</span>
                        {application.message !== null ? (
                          <span className="truncate font-sans text-caption text-ink-secondary">{application.message}</span>
                        ) : null}
                      </div>
                    </div>
                    <span className={`stat-pill shrink-0 self-start sm:self-center ${statusConfig.pill}`}>
                      <span className="material-symbols-outlined text-[13px]">{statusConfig.icon}</span>
                      {statusConfig.label}
                    </span>
                  </div>
                  {application.interview_at ? (
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-xl bg-good/10 px-3 py-2 font-sans text-caption text-ink-secondary">
                      <span className="flex items-center gap-1 font-mono text-[12px] font-bold text-good-ink">
                        <span className="material-symbols-outlined text-[16px]">event_available</span>
                        Интервью
                      </span>
                      <span>{new Date(application.interview_at).toLocaleString('ru-RU', { dateStyle: 'long', timeStyle: 'short' })}</span>
                      {application.interview_link ? <span className="break-all font-mono text-[12px]">{application.interview_link}</span> : null}
                      {application.interview_address ? <span>{application.interview_address}</span> : null}
                    </div>
                  ) : null}
                </div>
              )
            })}
          </div>
        )}
      </section>

      {selectedVacancy !== null ? (
        <Modal labelledBy="apply-modal-title" onClose={() => setSelectedVacancy(null)} open panelClassName="relative w-full max-w-md overflow-y-auto rounded-panel bg-raised p-6 shadow-raised-lg">
          <div className="flex flex-col gap-4">
            <div className="flex items-start justify-between gap-4">
              <div className="flex flex-col gap-1">
                <span className="label-cap">Отклик на вакансию</span>
                <span className="font-mono text-h3 font-semibold text-ink" id="apply-modal-title">{selectedVacancy.title}</span>
                <span className="font-mono text-[14px] font-bold text-pvn-blue">
                  {formatSalary(selectedVacancy.salary_from, selectedVacancy.salary_to)}
                </span>
              </div>
              <button className="shrink-0 text-ink-muted transition-colors hover:text-ink" onClick={() => setSelectedVacancy(null)} type="button">
                <span className="material-symbols-outlined text-[20px]">close</span>
              </button>
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="label-cap" htmlFor="application-message">Сопроводительное сообщение</label>
              <textarea
                className="field min-h-24 resize-y"
                id="application-message"
                onChange={(event) => setMessage(event.target.value)}
                placeholder="Кратко о релевантном опыте и мотивации"
                value={message}
              />
            </div>
            {applyError !== null ? (
              <div className="flex items-start gap-2 rounded-xl bg-pvn-red/10 p-3 font-sans text-caption text-pvn-red-ink">
                <span className="material-symbols-outlined shrink-0 text-[16px]">error</span>
                <span>{applyError}</span>
              </div>
            ) : null}
            <div className="flex items-center gap-3">
              <button className="btn-primary flex-1 py-3 text-[14px]" disabled={isApplying || message.trim() === ''} onClick={() => void submitApplication()} type="button">
                {isApplying ? 'Отправка…' : 'Отправить отклик'}
              </button>
              <button className="btn-ghost" onClick={() => setSelectedVacancy(null)} type="button">Отмена</button>
            </div>
          </div>
        </Modal>
      ) : null}
    </div>
  )
}
