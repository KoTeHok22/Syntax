import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ApiError } from '../../api/client'
import { fetchEmployerProfile, fetchIncomingApplications, scheduleInterview, updateApplicationStatus, anonymousCandidateId } from '../../api/platform'
import type { Application, CompanyOffice } from '../../api/platform'
import { Modal } from '../../components/Modal'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { retryATSDelivery } from '../../api/ats'
import type { ATSDeliveryResult, ATSDeliveryStatus } from '../../api/ats'
import { statusPill } from '../../lib/statusPill'

type ApplicationStatus = Application['status']
type StatusTab = 'all' | ApplicationStatus

interface InterviewFormState {
  date: string
  time: string
  duration: string
  format: 'video' | 'onsite' | 'phone'
  link: string
  officeId: string
  address: string
}

const emptyInterviewForm: InterviewFormState = {
  date: '',
  time: '',
  duration: '60',
  format: 'video',
  link: '',
  officeId: '',
  address: '',
}

function defaultOffice(offices: CompanyOffice[]): CompanyOffice | undefined {
  return offices.find((office) => office.is_default) ?? offices[0]
}

const STATUS_PILLS: Record<ApplicationStatus, { label: string; className: string }> = {
  new: { label: 'Новый', className: statusPill('info') },
  viewed: { label: 'Просмотрен', className: statusPill('neutral') },
  accepted: { label: 'Принят', className: statusPill('success') },
  rejected: { label: 'Отклонён', className: statusPill('neutral') },
}

interface ApplicationDelivery {
  status: ATSDeliveryStatus
  attempts: number
  error: string | null
  deliveredAt: string | null
}

function deliveryFromApplication(application: Application): ApplicationDelivery {
  const candidate = application as Application & {
    ats_delivery_status?: ATSDeliveryStatus
    ats_delivery_attempts?: number
    ats_delivery_error?: string | null
    ats_delivered_at?: string | null
  }
  return {
    status: candidate.ats_delivery_status ?? 'pending',
    attempts: candidate.ats_delivery_attempts ?? 0,
    error: candidate.ats_delivery_error ?? null,
    deliveredAt: candidate.ats_delivered_at ?? null,
  }
}

function deliveryLabel(status: ATSDeliveryStatus): string {
  if (status === 'delivered') return 'Доставлено в ATS'
  if (status === 'failed') return 'ATS не подтвердил доставку'
  if (status === 'not_configured') return 'ATS не подключён'
  return 'Ожидает отправки в ATS'
}

function todayIsoDate(): string {
  const now = new Date()
  const offsetMs = now.getTimezoneOffset() * 60_000
  return new Date(now.getTime() - offsetMs).toISOString().slice(0, 10)
}

function formatInterviewDate(form: InterviewFormState): string {
  const date = form.date.length > 0 ? form.date.split('-').reverse().join('.') : 'дата не указана'
  return `${date}${form.time.length > 0 ? `, ${form.time}` : ''}`
}

function SkeletonApplication() {
  return (
    <div className="flex animate-pulse flex-col gap-4 rounded-panel bg-raised p-6 shadow-raised">
      <div className="h-5 w-44 rounded-lg bg-inset" />
      <div className="h-16 rounded-xl bg-inset" />
      <div className="h-9 w-72 rounded-xl bg-inset" />
    </div>
  )
}

export function EmployerApplicationsPage() {
  const [applications, setApplications] = useState<Application[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [listError, setListError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [tab, setTab] = useState<StatusTab>('all')
  const [interviewApplication, setInterviewApplication] = useState<Application | null>(null)
  const [interviewForm, setInterviewForm] = useState<InterviewFormState>(emptyInterviewForm)
  const [interviewError, setInterviewError] = useState<string | null>(null)
  const [isSubmittingInterview, setIsSubmittingInterview] = useState(false)
  const [toast, setToast] = useState<string | null>(null)
  const [busyApplicationId, setBusyApplicationId] = useState<number | null>(null)
  const [rejecting, setRejecting] = useState<Application | null>(null)
  const [offices, setOffices] = useState<CompanyOffice[]>([])
  const [deliveryByApplication, setDeliveryByApplication] = useState<Record<number, ApplicationDelivery>>({})
  const [deliveryBusyId, setDeliveryBusyId] = useState<number | null>(null)
  const viewedRef = useRef<Set<number>>(new Set())

  useEffect(() => {
    fetchEmployerProfile().then((profile) => setOffices(profile.offices)).catch(() => setOffices([]))
  }, [])

  const loadApplications = useCallback(async () => {
    setIsLoading(true)
    setListError(null)
    try {
      const loaded = await fetchIncomingApplications()
      setApplications(loaded)
      setDeliveryByApplication(Object.fromEntries(loaded.map((item) => [item.id, deliveryFromApplication(item)])))
    } catch (exception) {
      if (exception instanceof ApiError) setListError(exception.detail)
      else setListError('Не удалось загрузить отклики')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadApplications()
  }, [loadApplications])

  useEffect(() => {
    if (toast === null) return
    const timer = window.setTimeout(() => setToast(null), 5000)
    return () => window.clearTimeout(timer)
  }, [toast])

  const autoMarkViewed = useCallback(
    (application: Application, node: HTMLElement | null) => {
      if (node === null || application.status !== 'new' || viewedRef.current.has(application.id)) return
      const observer = new IntersectionObserver(
        (entries) => {
          for (const entry of entries) {
            if (!entry.isIntersecting || viewedRef.current.has(application.id)) continue
            viewedRef.current.add(application.id)
            observer.disconnect()
            void updateApplicationStatus(application.id, 'viewed')
              .then((updated) => {
                setApplications((previous) => previous.map((item) => (item.id === updated.id ? updated : item)))
              })
              .catch(() => {
                viewedRef.current.delete(application.id)
              })
          }
        },
        { threshold: 0.4 },
      )
      observer.observe(node)
    },
    [],
  )

  const statusCount = useCallback(
    (status: ApplicationStatus) => applications.filter((application) => application.status === status).length,
    [applications],
  )

  const visibleApplications = useMemo(() => {
    if (tab === 'all') return applications
    return applications.filter((application) => application.status === tab)
  }, [applications, tab])

  const changeStatus = async (application: Application, status: ApplicationStatus) => {
    setBusyApplicationId(application.id)
    setActionError(null)
    try {
      const updated = await updateApplicationStatus(application.id, status)
      setApplications((previous) => previous.map((item) => (item.id === updated.id ? updated : item)))
      setDeliveryByApplication((previous) => ({ ...previous, [updated.id]: deliveryFromApplication(updated) }))
    } catch (exception) {
      if (exception instanceof ApiError) setActionError(exception.detail)
      else setActionError('Не удалось обновить статус отклика')
    } finally {
      setBusyApplicationId(null)
    }
  }

  const confirmReject = async () => {
    if (rejecting === null) return
    await changeStatus(rejecting, 'rejected')
    setRejecting(null)
  }

  const retryDelivery = async (application: Application) => {
    setDeliveryBusyId(application.id)
    setActionError(null)
    try {
      const result: ATSDeliveryResult = await retryATSDelivery(application.id)
      setDeliveryByApplication((previous) => ({
        ...previous,
        [application.id]: {
          status: result.status,
          attempts: result.attempts,
          error: result.error,
          deliveredAt: result.delivered_at ?? previous[application.id]?.deliveredAt ?? null,
        },
      }))
    } catch (exception) {
      if (exception instanceof ApiError) setActionError(exception.detail)
      else setActionError('Не удалось выполнить повторную отправку в ATS')
    } finally {
      setDeliveryBusyId(null)
    }
  }

  const openInterviewModal = (application: Application) => {
    const office = defaultOffice(offices)
    if (application.interview_at) {
      const scheduled = new Date(application.interview_at)
      const offsetMs = scheduled.getTimezoneOffset() * 60_000
      const local = new Date(scheduled.getTime() - offsetMs)
      setInterviewForm({
        date: local.toISOString().slice(0, 10),
        time: local.toISOString().slice(11, 16),
        duration: String(application.interview_duration ?? 60),
        format: application.interview_format ?? 'video',
        link: application.interview_link ?? '',
        officeId: office ? String(office.id) : '',
        address: application.interview_address ?? (office ? office.address : ''),
      })
    } else {
      setInterviewForm({
        ...emptyInterviewForm,
        officeId: office ? String(office.id) : '',
        address: office ? office.address : '',
      })
    }
    setInterviewApplication(application)
    setInterviewError(null)
  }

  const selectOffice = (officeId: string) => {
    const office = offices.find((item) => String(item.id) === officeId)
    setInterviewForm({ ...interviewForm, officeId, address: office ? office.address : interviewForm.address })
  }

  const closeInterviewModal = () => {
    setInterviewApplication(null)
    setInterviewForm(emptyInterviewForm)
    setInterviewError(null)
  }

  const confirmInterview = async (event: React.FormEvent) => {
    event.preventDefault()
    if (interviewApplication === null) return
    setInterviewError(null)
    if (interviewForm.date.length === 0 || interviewForm.time.length === 0) {
      setInterviewError('Укажите дату и время технического интервью')
      return
    }
    if (interviewForm.date < todayIsoDate()) {
      setInterviewError('Дата интервью не может быть в прошлом')
      return
    }
    if (interviewForm.format === 'video' && interviewForm.link.trim().length === 0) {
      setInterviewError('Укажите ссылку на видеозвонок')
      return
    }
    if (interviewForm.format === 'onsite' && interviewForm.address.trim().length === 0) {
      setInterviewError('Укажите адрес офиса для очной встречи')
      return
    }
    const scheduledAt = new Date(`${interviewForm.date}T${interviewForm.time}:00`)
    if (Number.isNaN(scheduledAt.getTime())) {
      setInterviewError('Проверьте дату и время интервью')
      return
    }
    setIsSubmittingInterview(true)
    try {
      const updated = await scheduleInterview(interviewApplication.id, {
        scheduled_at: scheduledAt.toISOString(),
        duration_minutes: Number(interviewForm.duration),
        format: interviewForm.format,
        link: interviewForm.format === 'video' ? interviewForm.link.trim() : null,
        address: interviewForm.format === 'onsite' ? interviewForm.address.trim() : null,
      })
      setApplications((previous) => previous.map((item) => (item.id === updated.id ? updated : item)))
      setToast(
        `Техническое интервью назначено: кандидат ${anonymousCandidateId(interviewApplication.candidate_profile_id)}, ${formatInterviewDate(interviewForm)}`,
      )
      closeInterviewModal()
    } catch (exception) {
      if (exception instanceof ApiError) setInterviewError(exception.detail)
      else setInterviewError('Не удалось сохранить интервью')
    } finally {
      setIsSubmittingInterview(false)
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-[1280px] flex-col gap-6 px-4 py-8 sm:px-6">
      <div className="flex flex-col gap-1">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="font-mono text-display font-extrabold tracking-tight text-ink">Входящие отклики</h1>
          {!isLoading ? <span className="stat-pill bg-pvn-blue/10 text-pvn-blue">{applications.length}</span> : null}
        </div>
        <p className="max-w-3xl font-sans text-body text-ink-secondary">
          Контакты соискателя открываются после назначения интервью.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-1 rounded-panel bg-raised p-2 shadow-raised-sm">
        {(
          [
            { value: 'all', label: 'Все', count: applications.length },
            { value: 'new', label: 'Новые', count: statusCount('new') },
            { value: 'viewed', label: 'Просмотренные', count: statusCount('viewed') },
            { value: 'accepted', label: 'Принятые', count: statusCount('accepted') },
            { value: 'rejected', label: 'Отклонённые', count: statusCount('rejected') },
          ] as { value: StatusTab; label: string; count: number }[]
        ).map((item) => (
          <button
            className={
              tab === item.value
                ? 'flex items-center gap-2 rounded-xl bg-pvn-blue px-4 py-2 font-mono text-[12px] font-bold text-white shadow-blue transition-all'
                : 'flex items-center gap-2 rounded-xl px-4 py-2 font-mono text-[12px] font-medium text-ink-secondary transition-all hover:bg-inset hover:text-ink'
            }
            key={item.value}
            onClick={() => setTab(item.value)}
            type="button"
          >
            {item.label}
            <span
              className={
                tab === item.value
                  ? 'rounded-full bg-white/25 px-1.5 font-mono text-[10px] font-bold text-white'
                  : 'rounded-full bg-inset px-1.5 font-mono text-[10px] font-bold text-ink-secondary'
              }
            >
              {item.count}
            </span>
          </button>
        ))}
      </div>

      {listError !== null ? (
        <div className="flex items-center gap-3 rounded-panel bg-pvn-red/10 px-5 py-4 font-sans text-caption text-pvn-red-ink shadow-raised-sm">
          <span className="material-symbols-outlined text-[18px]">error</span>
          <span>{listError}</span>
          <button className="ml-auto font-mono font-semibold underline" onClick={() => void loadApplications()} type="button">Повторить</button>
        </div>
      ) : null}
      {actionError !== null ? (
        <div className="flex items-center gap-3 rounded-panel bg-pvn-red/10 px-5 py-4 font-sans text-caption text-pvn-red-ink shadow-raised-sm">
          <span className="material-symbols-outlined text-[18px]">error</span>
          <span>{actionError}</span>
          <button className="ml-auto font-mono font-semibold underline" onClick={() => setActionError(null)} type="button">Скрыть</button>
        </div>
      ) : null}

      {isLoading ? (
        <div className="flex flex-col gap-4">
          <SkeletonApplication />
          <SkeletonApplication />
          <SkeletonApplication />
        </div>
      ) : visibleApplications.length === 0 ? (
        <div className="flex flex-col items-center gap-3 rounded-panel bg-raised p-12 text-center shadow-raised">
          <span className="material-symbols-outlined text-[40px] text-ink-muted">mark_email_unread</span>
          <span className="font-mono text-h2 font-bold text-ink">Ничего не найдено</span>
          <span className="max-w-md font-sans text-caption text-ink-secondary">
            {applications.length === 0 ? 'На ваши вакансии пока нет откликов' : 'В этом статусе нет ни одного отклика'}
          </span>
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {visibleApplications.map((application) => (
            <article
              className={`relative flex flex-col gap-4 overflow-hidden rounded-panel bg-raised p-6 shadow-raised ${application.status === 'new' ? 'ring-1 ring-warn/30' : ''}`}
              key={application.id}
              ref={(node) => autoMarkViewed(application, node)}
            >
              <div className="absolute left-0 top-0 h-full w-1.5 bg-pvn-blue" />
              <div className="flex flex-col justify-between gap-4 pl-2 md:flex-row md:items-start">
                <div className="flex min-w-0 flex-col gap-2">
                  <h2 className="font-mono text-h3 font-bold text-ink">
                    Кандидат {anonymousCandidateId(application.candidate_profile_id)}
                  </h2>
                  <span className="chip w-fit max-w-full truncate">
                    {application.vacancy_title ? `Вакансия: ${application.vacancy_title}` : 'Отклик на вакансию'}
                  </span>
                  <span className={`stat-pill w-fit ${STATUS_PILLS[application.status].className}`}>
                    {application.status === 'new' ? (
                      <span className="h-1.5 w-1.5 rounded-full bg-warn" />
                    ) : null}
                    {STATUS_PILLS[application.status].label}
                  </span>
                </div>
                <div className="flex shrink-0 flex-wrap items-center gap-2">
                  {application.status !== 'accepted' ? (
                    <button
                      className="btn-blue py-2 text-[13px]"
                      disabled={busyApplicationId === application.id}
                      onClick={() => void changeStatus(application, 'accepted')}
                      type="button"
                    >
                      <span className="material-symbols-outlined text-[18px]">check</span>
                      Принять
                    </button>
                  ) : null}
                  {application.status !== 'rejected' && application.status !== 'accepted' ? (
                    <button
                      className="btn-ghost py-2 text-[13px]"
                      disabled={busyApplicationId === application.id}
                      onClick={() => setRejecting(application)}
                      type="button"
                    >
                      <span className="material-symbols-outlined text-[18px]">close</span>
                      Отклонить
                    </button>
                  ) : null}
                </div>
              </div>
              {application.message !== null && application.message.length > 0 ? (
                <div className="flex items-start gap-3 rounded-xl bg-inset p-4 text-ink shadow-inset-sm">
                  <span className="material-symbols-outlined mt-0.5 shrink-0 text-[20px] text-pvn-blue">chat</span>
                  <div className="font-sans text-body">
                    «{application.message}»
                  </div>
                </div>
              ) : null}
              {application.status === 'accepted' ? (() => {
                const delivery = deliveryByApplication[application.id] ?? deliveryFromApplication(application)
                return (
                  <div className="flex flex-col gap-3 rounded-xl bg-inset p-4 shadow-inset-sm">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="flex items-center gap-2">
                        <span className={`h-2 w-2 rounded-full ${delivery.status === 'delivered' ? 'bg-good' : delivery.status === 'failed' ? 'bg-pvn-red' : 'bg-warn'}`} />
                        <span className="font-mono text-[13px] font-bold text-ink">{deliveryLabel(delivery.status)}</span>
                      </div>
                      {delivery.status !== 'delivered' ? (
                        <button className="btn-ghost py-2 text-[13px]" disabled={deliveryBusyId === application.id} onClick={() => void retryDelivery(application)} type="button">
                          <span className="material-symbols-outlined text-[18px]">refresh</span>
                          {deliveryBusyId === application.id ? 'Отправка…' : 'Повторить отправку'}
                        </button>
                      ) : null}
                    </div>
                    <div className="flex flex-wrap gap-x-4 gap-y-1 font-sans text-caption text-ink-secondary">
                      <span>Попыток: {delivery.attempts}</span>
                      {delivery.deliveredAt !== null ? <span>Подтверждено: {new Date(delivery.deliveredAt).toLocaleString('ru-RU')}</span> : null}
                    </div>
                    {delivery.error !== null ? <span className="font-sans text-caption text-pvn-red-ink">{delivery.error}</span> : null}
                  </div>
                )
              })() : null}
              {application.interview_at ? (
                <div className="flex flex-col gap-2 rounded-xl bg-good/10 p-4 shadow-inset-sm">
                  <div className="flex items-center gap-2 font-mono text-[13px] font-bold text-good-ink">
                    <span className="material-symbols-outlined text-[18px]">event_available</span>
                    Интервью назначено
                  </div>
                  <div className="flex flex-wrap gap-x-4 gap-y-1 font-sans text-caption text-ink-secondary">
                    <span>{new Date(application.interview_at).toLocaleString('ru-RU', { dateStyle: 'long', timeStyle: 'short' })}</span>
                    {application.interview_duration ? <span>{application.interview_duration} мин</span> : null}
                    {application.interview_format === 'video' ? <span>Видеозвонок</span> : application.interview_format === 'onsite' ? <span>Очно</span> : application.interview_format === 'phone' ? <span>Телефон</span> : null}
                  </div>
                  {application.interview_link ? <span className="break-all font-mono text-[12px] text-ink-secondary">{application.interview_link}</span> : null}
                  {application.interview_address ? <span className="font-sans text-caption text-ink-secondary">{application.interview_address}</span> : null}
                </div>
              ) : null}
              <div className="flex flex-col justify-between gap-3 rounded-xl bg-inset p-4 shadow-inset-sm md:flex-row md:items-center">
                <span className="font-sans text-caption text-ink-secondary">
                  {application.status === 'accepted'
                    ? application.interview_at
                      ? 'Интервью назначено — кандидат видит детали'
                      : 'Отклик принят — назначьте техническое интервью'
                    : 'Сначала примите отклик'}
                </span>
                <button
                  className="btn-ghost py-2 text-[13px]"
                  disabled={application.status !== 'accepted'}
                  onClick={() => openInterviewModal(application)}
                  title={application.status === 'accepted' ? undefined : 'Сначала примите отклик'}
                  type="button"
                >
                  <span className="material-symbols-outlined text-[18px]">event_available</span>
                  {application.interview_at ? 'Переназначить интервью' : 'Назначить интервью'}
                </button>
              </div>
            </article>
          ))}
        </div>
      )}

      {interviewApplication !== null ? (
        <Modal labelledBy="interview-modal-title" onClose={closeInterviewModal} open panelClassName="relative my-auto w-full max-w-2xl overflow-hidden rounded-panel bg-raised shadow-raised-lg">
          <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
            <div className="flex items-start justify-between gap-4 bg-inset px-6 py-4 shadow-inset-sm">
              <div className="flex flex-col gap-1">
                <h2 className="font-mono text-h2 font-extrabold tracking-tight text-ink" id="interview-modal-title">Техническое интервью</h2>
                <span className="font-mono text-[12px] text-ink-secondary">
                  Кандидат {anonymousCandidateId(interviewApplication.candidate_profile_id)}
                </span>
              </div>
              <button
                className="flex h-9 w-9 items-center justify-center rounded-xl text-ink-muted transition-all hover:bg-raised hover:text-ink"
                onClick={closeInterviewModal}
                title="Закрыть"
                type="button"
              >
                <span className="material-symbols-outlined text-[20px]">close</span>
              </button>
            </div>
            <form className="flex flex-col gap-5 overflow-y-auto p-6" onSubmit={confirmInterview}>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <div className="flex flex-col gap-1.5">
                  <label className="label-cap" htmlFor="interview-date">Дата *</label>
                  <input className="field cursor-pointer py-2.5" id="interview-date" min={todayIsoDate()} onChange={(event) => setInterviewForm({ ...interviewForm, date: event.target.value })} required type="date" value={interviewForm.date} />
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className="label-cap" htmlFor="interview-time">Время *</label>
                  <input className="field cursor-pointer py-2.5" id="interview-time" onChange={(event) => setInterviewForm({ ...interviewForm, time: event.target.value })} required type="time" value={interviewForm.time} />
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className="label-cap" htmlFor="interview-duration">Длительность</label>
                  <select className="field cursor-pointer py-2.5" id="interview-duration" onChange={(event) => setInterviewForm({ ...interviewForm, duration: event.target.value })} value={interviewForm.duration}>
                    <option value="30">30 минут</option>
                    <option value="60">60 минут</option>
                    <option value="90">90 минут</option>
                    <option value="120">2 часа</option>
                  </select>
                </div>
              </div>
              <div className="flex flex-col gap-2">
                <span className="label-cap">Формат *</span>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                  {(
                    [
                      { value: 'video', title: 'Видеозвонок', hint: 'Платформенная ссылка', icon: 'video_call' },
                      { value: 'onsite', title: 'Очно', hint: 'Офис компании', icon: 'apartment' },
                      { value: 'phone', title: 'Телефон', hint: 'Голосовой звонок', icon: 'call' },
                    ] as { value: InterviewFormState['format']; title: string; hint: string; icon: string }[]
                  ).map((option) => (
                    <label
                      className={`flex cursor-pointer items-center gap-3 rounded-xl p-3 transition-all ${
                        interviewForm.format === option.value ? 'bg-raised shadow-raised-sm ring-2 ring-pvn-blue/40' : 'bg-inset shadow-inset-sm'
                      }`}
                      key={option.value}
                    >
                      <input
                        checked={interviewForm.format === option.value}
                        className="h-4 w-4 accent-pvn-blue"
                        name="interview-format"
                        onChange={() => setInterviewForm({ ...interviewForm, format: option.value })}
                        type="radio"
                        value={option.value}
                      />
                      <div className="flex flex-col">
                        <span className="flex items-center gap-1 font-mono text-[12px] font-semibold text-ink">
                          <span className="material-symbols-outlined text-[16px] text-ink-muted">{option.icon}</span>
                          {option.title}
                        </span>
                        <span className="font-sans text-[11px] text-ink-secondary">{option.hint}</span>
                      </div>
                    </label>
                  ))}
                </div>
              </div>
              {interviewForm.format === 'onsite' ? (
                <div className="flex flex-col gap-3">
                  {offices.length > 0 ? (
                    <div className="flex flex-col gap-1.5">
                      <label className="label-cap" htmlFor="interview-office">Офис</label>
                      <select
                        className="field cursor-pointer py-2.5"
                        id="interview-office"
                        onChange={(event) => selectOffice(event.target.value)}
                        value={interviewForm.officeId}
                      >
                        {offices.map((office) => (
                          <option key={office.id} value={String(office.id)}>
                            {office.title.length > 0 ? `${office.title} · ${office.city}` : office.city}
                          </option>
                        ))}
                      </select>
                    </div>
                  ) : null}
                  <div className="flex flex-col gap-1.5">
                    <label className="label-cap" htmlFor="interview-address">Адрес *</label>
                    <input
                      className="field font-sans text-body"
                      id="interview-address"
                      onChange={(event) => setInterviewForm({ ...interviewForm, address: event.target.value })}
                      required
                      type="text"
                      value={interviewForm.address}
                    />
                  </div>
                </div>
              ) : null}
              {interviewForm.format === 'video' ? (
                <div className="flex flex-col gap-1.5">
                  <label className="label-cap" htmlFor="interview-link">Ссылка на звонок *</label>
                  <input
                    className="field font-mono text-[14px]"
                    id="interview-link"
                    onChange={(event) => setInterviewForm({ ...interviewForm, link: event.target.value })}
                    placeholder="Ссылка: https://meet.example.com/room"
                    required
                    type="text"
                    value={interviewForm.link}
                  />
                </div>
              ) : null}
              <p className="font-sans text-caption text-ink-secondary">
                {interviewForm.format === 'video'
                  ? 'Кандидат получит ссылку на видеозвонок и детали сессии после сохранения расписания.'
                  : interviewForm.format === 'onsite'
                    ? 'Кандидат получит адрес офиса и детали сессии после сохранения расписания.'
                    : 'Кандидат получит номер телефона и детали сессии после сохранения расписания.'}
              </p>
              {interviewError !== null ? (
                <div className="flex items-center gap-2 rounded-xl bg-pvn-red/10 px-4 py-3 font-sans text-caption text-pvn-red-ink">
                  <span className="material-symbols-outlined text-[18px]">error</span>
                  <span>{interviewError}</span>
                </div>
              ) : null}
              <div className="sticky bottom-0 -mx-6 mt-1 flex items-center justify-end gap-3 border-t border-ink/10 bg-raised px-6 pb-1 pt-4">
                <button className="btn-ghost" onClick={closeInterviewModal} type="button">Отмена</button>
                <button className="btn-primary" disabled={isSubmittingInterview} type="submit">
                  <span className="material-symbols-outlined text-[18px]">check</span>
                  {isSubmittingInterview ? 'Сохранение…' : 'Подтвердить'}
                </button>
              </div>
            </form>
          </div>
        </Modal>
      ) : null}

      <ConfirmDialog
        confirmLabel="Отклонить"
        busy={rejecting !== null && busyApplicationId === rejecting.id}
        description="Кандидат получит отказ, действие необратимо."
        onCancel={() => setRejecting(null)}
        onConfirm={() => void confirmReject()}
        open={rejecting !== null}
        title="Отклонить отклик?"
        tone="danger"
      />

      {toast !== null ? (
        <div className="fixed bottom-6 right-6 z-[60] flex max-w-sm items-start gap-3 rounded-panel bg-pvn-dark px-5 py-4 shadow-raised-lg">
          <span className="material-symbols-outlined shrink-0 text-[20px] text-good-ink">check_circle</span>
          <span className="font-sans text-caption text-white">{toast}</span>
          <button className="ml-auto flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-white/70 hover:bg-white/10" onClick={() => setToast(null)} type="button">
            <span className="material-symbols-outlined text-[16px]">close</span>
          </button>
        </div>
      ) : null}
    </div>
  )
}
