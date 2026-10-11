import { useCallback, useEffect, useState } from 'react'
import { fetchMyApplications } from '../../api/platform'
import type { Application } from '../../api/platform'
import { statusPill } from '../../lib/statusPill'

const applicationStatusConfig: Record<Application['status'], { label: string; pill: string; icon: string }> = {
  new: { label: 'Новый', pill: statusPill('info'), icon: 'schedule' },
  viewed: { label: 'Просмотрен', pill: statusPill('info'), icon: 'visibility' },
  accepted: { label: 'Принят', pill: statusPill('success'), icon: 'check_circle' },
  rejected: { label: 'Отклонён', pill: statusPill('neutral'), icon: 'cancel' },
}

const formatLabels: Record<string, string> = {
  video: 'Видеозвонок',
  onsite: 'Офис',
  phone: 'Телефон',
}

const formatIcons: Record<string, string> = {
  video: 'videocam',
  onsite: 'location_on',
  phone: 'call',
}

export function CandidateApplicationsPage() {
  const [applications, setApplications] = useState<Application[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadApplications = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      setApplications(await fetchMyApplications())
    } catch {
      setError('Не удалось загрузить отклики')
      setApplications([])
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadApplications()
  }, [loadApplications])

  return (
    <div className="mx-auto flex w-full max-w-[1280px] flex-col gap-6 px-4 py-8 sm:px-6">
      <div className="flex flex-col gap-1">
        <h1 className="font-mono text-display font-extrabold tracking-tight text-ink">Мои отклики</h1>
        <p className="max-w-3xl font-sans text-body text-ink-secondary">
          Вакансии, на которые вы откликнулись. Контакты откроются, когда работодатель пригласит вас.
        </p>
      </div>

      {error !== null ? (
        <div className="flex items-start gap-3 rounded-panel bg-pvn-red/10 px-5 py-4 font-sans text-caption text-pvn-red-ink shadow-raised-sm">
          <span className="material-symbols-outlined shrink-0 text-[18px]">error</span>
          <span>{error}</span>
        </div>
      ) : null}

      {isLoading ? (
        <div className="flex flex-col gap-3 rounded-panel bg-raised p-6 shadow-raised">
          {[0, 1, 2].map((index) => (<div className="h-14 animate-pulse rounded-xl bg-inset" key={index} />))}
        </div>
      ) : applications.length === 0 ? (
        <div className="flex flex-col items-center gap-3 rounded-panel bg-raised p-12 text-center text-ink-secondary shadow-raised">
          <span className="material-symbols-outlined text-[48px] text-ink-muted">inbox</span>
          <span className="font-mono text-h2 font-semibold text-ink">Откликов пока нет</span>
          <span className="max-w-md font-sans text-body">Откликнитесь на вакансию на странице «Вакансии» — здесь появится статус.</span>
        </div>
      ) : (
        <div className="flex flex-col divide-y divide-ink/10 rounded-panel bg-raised p-6 shadow-raised">
          {applications.map((application) => {
            const statusConfig = applicationStatusConfig[application.status]
            const vacancyTitle = application.vacancy_title ?? `Вакансия #${application.vacancy_id}`
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
                  <div className="flex flex-col gap-2 rounded-xl bg-good/10 p-4">
                    <div className="flex items-center gap-2">
                      <span className="material-symbols-outlined text-[18px] text-good-ink">event_available</span>
                      <span className="font-mono text-[11px] font-bold uppercase tracking-wider text-good-ink">Приглашение на интервью</span>
                    </div>
                    <span className="font-mono text-[15px] font-semibold text-ink">
                      {new Date(application.interview_at).toLocaleString('ru-RU', { dateStyle: 'long', timeStyle: 'short' })}
                      {application.interview_duration ? ` · ${application.interview_duration} мин` : ''}
                    </span>
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 font-sans text-caption text-ink-secondary">
                      {formatLabels[application.interview_format ?? ''] ? (
                        <span className="flex items-center gap-1">
                          <span className="material-symbols-outlined text-[15px] text-ink-muted">{formatIcons[application.interview_format ?? ''] ?? 'videocam'}</span>
                          {formatLabels[application.interview_format ?? '']}
                        </span>
                      ) : null}
                      {application.interview_address ? <span>{application.interview_address}</span> : null}
                    </div>
                    {application.interview_link ? (
                      <a
                        className="btn-primary w-fit py-2 text-[13px]"
                        href={application.interview_link}
                        rel="noreferrer"
                        target="_blank"
                      >
                        <span className="material-symbols-outlined text-[18px]">link</span>
                        Перейти по ссылке
                      </a>
                    ) : null}
                  </div>
                ) : null}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
