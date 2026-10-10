import { useCallback, useEffect, useMemo, useState } from 'react'
import { ApiError } from '../../api/client'
import { closeVacancy, createVacancy, fetchMyVacancies, updateVacancy } from '../../api/platform'
import type { Vacancy } from '../../api/platform'
import { Modal } from '../../components/Modal'
import { Toast } from '../../components/Toast'
import { gradeLabel, specializationLabel } from '../../lib/format'

const PAGE_LIMIT = 20

const SPECIALIZATIONS = [
  { value: 'backend', label: 'Backend разработка' },
  { value: 'frontend', label: 'Frontend разработка' },
  { value: 'data', label: 'Data Engineering / MLOps' },
  { value: 'devops', label: 'DevOps / SRE / Cloud' },
  { value: 'mobile', label: 'Mobile (iOS / Android)' },
  { value: 'qa', label: 'QA / SDET' },
]

const GRADES = [
  { value: 'junior', label: 'Junior' },
  { value: 'middle', label: 'Middle' },
  { value: 'senior', label: 'Senior / Lead' },
]

type TabFilter = 'all' | 'open' | 'closed'
type ModalMode = 'closed' | 'create' | 'edit'

interface VacancyFormState {
  title: string
  description: string
  stack: string
  specialization: string
  grade: string
  salaryFrom: string
  salaryTo: string
}

const emptyVacancyForm: VacancyFormState = {
  title: '',
  description: '',
  stack: '',
  specialization: 'backend',
  grade: 'middle',
  salaryFrom: '',
  salaryTo: '',
}

function formatSalary(from: number, to: number): string {
  return `${from.toLocaleString('ru-RU')} – ${to.toLocaleString('ru-RU')} ₽`
}

function SkeletonVacancy() {
  return (
    <div className="flex w-full animate-pulse flex-col gap-3 rounded-panel bg-raised p-6 shadow-raised">
      <div className="h-4 w-40 rounded-lg bg-inset" />
      <div className="h-5 w-72 rounded-lg bg-inset" />
      <div className="flex gap-2">
        <div className="h-5 w-20 rounded-full bg-inset" />
        <div className="h-5 w-16 rounded-full bg-inset" />
      </div>
    </div>
  )
}

export function EmployerVacanciesPage() {
  const [vacancies, setVacancies] = useState<Vacancy[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const [hasMore, setHasMore] = useState(false)
  const [listError, setListError] = useState<string | null>(null)
  const [tab, setTab] = useState<TabFilter>('all')
  const [search, setSearch] = useState('')
  const [modalMode, setModalMode] = useState<ModalMode>('closed')
  const [editingVacancy, setEditingVacancy] = useState<Vacancy | null>(null)
  const [vacancyForm, setVacancyForm] = useState<VacancyFormState>(emptyVacancyForm)
  const [formError, setFormError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [confirmingCloseId, setConfirmingCloseId] = useState<number | null>(null)
  const [isClosing, setIsClosing] = useState(false)
  const [previewVacancy, setPreviewVacancy] = useState<Vacancy | null>(null)
  const [successNotice, setSuccessNotice] = useState<string | null>(null)

  const loadVacancies = useCallback(async (skip: number) => {
    if (skip === 0) setIsLoading(true)
    else setIsLoadingMore(true)
    setListError(null)
    try {
      const loaded = await fetchMyVacancies({ skip, limit: PAGE_LIMIT })
      setVacancies((previous) => (skip === 0 ? loaded : [...previous, ...loaded]))
      setHasMore(loaded.length === PAGE_LIMIT)
    } catch (exception) {
      if (exception instanceof ApiError) setListError(exception.detail)
      else setListError('Не удалось загрузить вакансии')
    } finally {
      setIsLoading(false)
      setIsLoadingMore(false)
    }
  }, [])

  useEffect(() => {
    void loadVacancies(0)
  }, [loadVacancies])

  const openCount = vacancies.filter((vacancy) => vacancy.is_open).length
  const closedCount = vacancies.length - openCount

  const visibleVacancies = useMemo(() => {
    const query = search.trim().toLowerCase()
    return vacancies.filter((vacancy) => {
      if (tab === 'open' && !vacancy.is_open) return false
      if (tab === 'closed' && vacancy.is_open) return false
      if (query.length === 0) return true
      const haystack = [vacancy.title, ...vacancy.stack].join(' ').toLowerCase()
      return haystack.includes(query)
    })
  }, [vacancies, tab, search])

  const openModal = () => {
    setVacancyForm(emptyVacancyForm)
    setEditingVacancy(null)
    setFormError(null)
    setModalMode('create')
  }

  const openEditModal = (vacancy: Vacancy) => {
    setVacancyForm({
      title: vacancy.title,
      description: vacancy.description ?? '',
      stack: vacancy.stack.join(', '),
      specialization: vacancy.specialization ?? 'backend',
      grade: vacancy.grade ?? 'middle',
      salaryFrom: String(vacancy.salary_from),
      salaryTo: String(vacancy.salary_to),
    })
    setEditingVacancy(vacancy)
    setFormError(null)
    setModalMode('edit')
  }

  const closeModal = () => {
    setModalMode('closed')
    setEditingVacancy(null)
    setVacancyForm(emptyVacancyForm)
    setFormError(null)
  }

  const submitVacancy = async (event: React.FormEvent) => {
    event.preventDefault()
    setFormError(null)
    const salaryFrom = Number(vacancyForm.salaryFrom)
    const salaryTo = Number(vacancyForm.salaryTo)
    if (!Number.isFinite(salaryFrom) || !Number.isFinite(salaryTo) || salaryFrom <= 0 || salaryTo <= 0) {
      setFormError('Укажите обе границы зарплатной вилки')
      return
    }
    if (salaryTo < salaryFrom) {
      setFormError('Верхняя граница вилки не может быть меньше нижней')
      return
    }
    const stack = vacancyForm.stack
      .split(',')
      .map((item) => item.trim())
      .filter((item) => item.length > 0)
    if (stack.length === 0) {
      setFormError('Укажите хотя бы одну технологию стека')
      return
    }
    setIsSubmitting(true)
    try {
      if (modalMode === 'edit' && editingVacancy !== null) {
        const updated = await updateVacancy(editingVacancy.id, {
          title: vacancyForm.title,
          description: vacancyForm.description,
          stack,
          specialization: vacancyForm.specialization,
          grade: vacancyForm.grade,
          salary_from: salaryFrom,
          salary_to: salaryTo,
        })
        setVacancies((previous) => previous.map((item) => (item.id === updated.id ? updated : item)))
        closeModal()
        setSuccessNotice(`Вакансия «${updated.title}» обновлена`)
        return
      }
      const created = await createVacancy({
        title: vacancyForm.title,
        description: vacancyForm.description,
        stack,
        specialization: vacancyForm.specialization,
        grade: vacancyForm.grade,
        salary_from: salaryFrom,
        salary_to: salaryTo,
      })
      setVacancies((previous) => [created, ...previous])
      closeModal()
      setSuccessNotice(`Вакансия «${created.title}» опубликована`)
    } catch (exception) {
      if (exception instanceof ApiError) setFormError(exception.detail)
      else setFormError('Не удалось опубликовать вакансию')
    } finally {
      setIsSubmitting(false)
    }
  }

  const confirmClose = async (vacancyId: number) => {
    setIsClosing(true)
    try {
      const closed = await closeVacancy(vacancyId)
      setVacancies((previous) => previous.map((item) => (item.id === closed.id ? closed : item)))
      setConfirmingCloseId(null)
      setSuccessNotice(`Вакансия «${closed.title}» закрыта`)
    } catch (exception) {
      if (exception instanceof ApiError) setListError(exception.detail)
      else setListError('Не удалось закрыть вакансию')
    } finally {
      setIsClosing(false)
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-[1280px] flex-col gap-6 px-4 py-8 sm:px-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="flex flex-col gap-1">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="font-mono text-display font-extrabold tracking-tight text-ink">Вакансии компании</h1>
            {!isLoading ? (
              <span className="stat-pill bg-inset text-ink-secondary">
                {openCount} активных · {closedCount} в архиве
              </span>
            ) : null}
          </div>
          <p className="max-w-3xl font-sans text-body text-ink-secondary">
            Вилку указывать обязательно.
          </p>
        </div>
        <button className="btn-primary shrink-0" onClick={openModal} type="button">
          <span className="material-symbols-outlined text-[18px]">add</span>
          Опубликовать вакансию
        </button>
      </div>

      <div className="flex flex-col gap-4 rounded-panel bg-raised p-4 shadow-raised-sm lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-center gap-1 overflow-x-auto rounded-2xl bg-inset p-1 shadow-inset-sm">
          {(
            [
              { value: 'all', label: `Все (${vacancies.length})` },
              { value: 'open', label: `Активные (${openCount})` },
              { value: 'closed', label: `Архив (${closedCount})` },
            ] as { value: TabFilter; label: string }[]
          ).map((item) => (
            <button
              className={
                tab === item.value
                  ? 'whitespace-nowrap rounded-xl bg-raised px-4 py-2 font-mono text-[12px] font-bold text-pvn-blue shadow-raised-sm transition-all'
                  : 'whitespace-nowrap rounded-xl px-4 py-2 font-mono text-[12px] font-medium text-ink-secondary transition-all hover:text-ink'
              }
              key={item.value}
              onClick={() => setTab(item.value)}
              type="button"
            >
              {item.label}
            </button>
          ))}
        </div>
        <div className="relative flex-1 sm:w-80">
          <span className="material-symbols-outlined pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[18px] text-ink-muted">search</span>
          <input
            className="field py-2.5 pl-10 text-[14px]"
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Поиск по названию или стеку…"
            type="text"
            value={search}
          />
        </div>
      </div>

      <Toast message={successNotice} onClose={() => setSuccessNotice(null)} />

      {listError !== null ? (
        <div className="flex items-center gap-3 rounded-panel bg-pvn-red/10 px-5 py-4 font-sans text-caption text-pvn-red-ink shadow-raised-sm">
          <span className="material-symbols-outlined text-[18px]">error</span>
          <span>{listError}</span>
          <button className="ml-auto font-mono font-semibold underline" onClick={() => void loadVacancies(0)} type="button">Повторить</button>
        </div>
      ) : null}

      {isLoading ? (
        <div className="flex flex-col gap-4">
          <SkeletonVacancy />
          <SkeletonVacancy />
          <SkeletonVacancy />
        </div>
      ) : visibleVacancies.length === 0 ? (
        <div className="flex flex-col items-center gap-3 rounded-panel bg-raised p-12 text-center shadow-raised">
          <span className="material-symbols-outlined text-[40px] text-ink-muted">work_off</span>
          <span className="font-mono text-h2 font-bold text-ink">Ничего не найдено</span>
          <span className="max-w-md font-sans text-caption text-ink-secondary">
            {vacancies.length === 0 ? 'У вас пока нет опубликованных вакансий' : 'Под выбранный запрос и статус не подходит ни одна вакансия'}
          </span>
          {vacancies.length > 0 ? (
            <button
              className="font-mono text-[13px] font-semibold text-pvn-blue hover:underline"
              onClick={() => {
                setSearch('')
                setTab('all')
              }}
              type="button"
            >
              Сбросить фильтры
            </button>
          ) : null}
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {visibleVacancies.map((vacancy) => (
            <div
              className="flex w-full flex-col items-start justify-between gap-3 rounded-panel bg-raised p-4 shadow-raised lg:flex-row lg:items-center"
              key={vacancy.id}
            >
              <div className="flex max-w-2xl flex-col gap-1.5">
                <div className="flex flex-wrap items-center gap-2">
                  {vacancy.is_open ? (
                    <span className="stat-pill bg-pvn-blue/10 text-pvn-blue">Активна</span>
                  ) : (
                    <span className="stat-pill bg-sunken text-ink-secondary">Закрыта</span>
                  )}
                  {vacancy.specialization !== null ? <span className="chip">{specializationLabel(vacancy.specialization)}</span> : null}
                  {vacancy.grade !== null ? <span className="chip">{gradeLabel(vacancy.grade)}</span> : null}
                </div>
                <h2 className="font-mono text-h3 font-bold tracking-tight text-ink">{vacancy.title}</h2>
                {vacancy.description !== null && vacancy.description.length > 0 ? (
                  <p className="font-sans text-caption text-ink-secondary line-clamp-2">{vacancy.description}</p>
                ) : null}
                <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
                  {vacancy.stack.map((technology) => (
                    <span className="chip" key={technology}>{technology}</span>
                  ))}
                </div>
              </div>
              <div className="flex w-full shrink-0 flex-wrap items-center gap-3 lg:w-auto lg:justify-end">
                <span className="font-mono text-[18px] font-extrabold tracking-tight text-pvn-blue">
                  {formatSalary(vacancy.salary_from, vacancy.salary_to)}
                </span>
                <div className="flex flex-wrap items-center gap-2">
                  <button className="btn-ghost py-2 text-[13px]" onClick={() => setPreviewVacancy(vacancy)} type="button">
                    <span className="material-symbols-outlined text-[18px]">preview</span>
                    Предпросмотр
                  </button>
                  <button className="btn-ghost py-2 text-[13px]" onClick={() => openEditModal(vacancy)} type="button">
                    <span className="material-symbols-outlined text-[18px]">edit</span>
                    Редактировать
                  </button>
                  {vacancy.is_open ? (
                    confirmingCloseId === vacancy.id ? (
                      <div className="flex items-center gap-2">
                        <button
                          className="btn-primary py-2 text-[13px]"
                          disabled={isClosing}
                          onClick={() => void confirmClose(vacancy.id)}
                          type="button"
                        >
                          Да, закрыть
                        </button>
                        <button className="btn-ghost py-2 text-[13px]" onClick={() => setConfirmingCloseId(null)} type="button">
                          Отмена
                        </button>
                      </div>
                    ) : (
                      <button className="btn-ghost py-2 text-[13px] text-pvn-red-ink" onClick={() => setConfirmingCloseId(vacancy.id)} type="button">
                        <span className="material-symbols-outlined text-[18px]">close</span>
                        Закрыть
                      </button>
                    )
                  ) : null}
                </div>
              </div>
            </div>
          ))}
          {hasMore ? (
            <div className="flex flex-col items-center justify-between gap-4 sm:flex-row">
              <span className="font-mono text-[12px] text-ink-secondary">
                Показано <span className="font-bold text-ink">{vacancies.length}</span> вакансий
              </span>
              <button className="btn-ghost text-[13px]" disabled={isLoadingMore} onClick={() => void loadVacancies(vacancies.length)} type="button">
                <span className="material-symbols-outlined text-[18px]">expand_more</span>
                Показать ещё
              </button>
            </div>
          ) : null}
        </div>
      )}

        <Modal labelledBy="vacancy-preview-title" onClose={() => setPreviewVacancy(null)} open={previewVacancy !== null} panelClassName="relative w-full max-w-lg overflow-y-auto rounded-panel bg-raised p-6 shadow-raised-lg">
        {previewVacancy !== null ? (
          <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-1">
              <span className="font-mono text-[12px] uppercase tracking-wider text-ink-muted">Так видит вакансию кандидат</span>
              <h2 className="font-mono text-h3 font-bold tracking-tight text-ink" id="vacancy-preview-title">{previewVacancy.title}</h2>
              <span className="font-mono text-[13px] text-pvn-blue">
                {specializationLabel(previewVacancy.specialization)} · {gradeLabel(previewVacancy.grade)}
              </span>
            </div>
            <span className="font-mono text-[20px] font-extrabold tracking-tight text-pvn-blue">
              {formatSalary(previewVacancy.salary_from, previewVacancy.salary_to)}
            </span>
            {previewVacancy.description !== null && previewVacancy.description.length > 0 ? (
              <p className="font-sans text-body text-ink-secondary">{previewVacancy.description}</p>
            ) : null}
            <div className="flex flex-wrap gap-1.5">
              {previewVacancy.stack.map((technology) => (
                <span className="chip" key={technology}>{technology}</span>
              ))}
            </div>
            <div className="flex justify-end">
              <button className="btn-ghost" onClick={() => setPreviewVacancy(null)} type="button">Закрыть</button>
            </div>
          </div>
        ) : null}
      </Modal>

      {modalMode !== 'closed' ? (
        <Modal labelledBy="vacancy-modal-title" onClose={closeModal} open panelClassName="relative my-auto w-full max-w-3xl overflow-hidden rounded-panel bg-raised shadow-raised-lg">
          <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
            <div className="flex items-start justify-between gap-4 bg-inset px-6 py-4 shadow-inset-sm">
              <div className="flex flex-col gap-1">
                <h2 className="font-mono text-h2 font-extrabold tracking-tight text-ink" id="vacancy-modal-title">
                  {modalMode === 'edit' ? 'Редактирование вакансии' : 'Публикация вакансии'}
                </h2>
                <span className="flex items-center gap-1.5 font-mono text-[11px] font-semibold text-good-ink">
                  <span className="material-symbols-outlined text-[14px]">shield</span>
                  Фиксация зарплатной вилки обязательна
                </span>
              </div>
              <button
                className="flex h-9 w-9 items-center justify-center rounded-xl text-ink-muted transition-all hover:bg-raised hover:text-ink"
                onClick={closeModal}
                title="Закрыть"
                type="button"
              >
                <span className="material-symbols-outlined text-[20px]">close</span>
              </button>
            </div>
            <form className="flex flex-col gap-5 overflow-y-auto p-6" onSubmit={submitVacancy}>
              <div className="flex flex-col gap-1.5">
                <label className="label-cap" htmlFor="vacancy-title">Название должности *</label>
                <input
                  className="field text-[16px] font-medium"
                  id="vacancy-title"
                  onChange={(event) => setVacancyForm({ ...vacancyForm, title: event.target.value })}
                  placeholder="Senior Python / Highload Developer"
                  required
                  type="text"
                  value={vacancyForm.title}
                />
              </div>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="flex flex-col gap-1.5">
                  <label className="label-cap" htmlFor="vacancy-spec">Специализация *</label>
                  <select
                    className="field cursor-pointer py-2.5"
                    id="vacancy-spec"
                    onChange={(event) => setVacancyForm({ ...vacancyForm, specialization: event.target.value })}
                    value={vacancyForm.specialization}
                  >
                    {SPECIALIZATIONS.map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className="label-cap" htmlFor="vacancy-grade">Целевой грейд *</label>
                  <select
                    className="field cursor-pointer py-2.5"
                    id="vacancy-grade"
                    onChange={(event) => setVacancyForm({ ...vacancyForm, grade: event.target.value })}
                    value={vacancyForm.grade}
                  >
                    {GRADES.map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="label-cap" htmlFor="vacancy-stack">Технологический стек * · через запятую</label>
                <input
                  className="field"
                  id="vacancy-stack"
                  onChange={(event) => setVacancyForm({ ...vacancyForm, stack: event.target.value })}
                  placeholder="Python, FastAPI, PostgreSQL, Kafka, Docker"
                  required
                  type="text"
                  value={vacancyForm.stack}
                />
              </div>
              <div className="flex flex-col gap-3 rounded-2xl bg-inset p-4 shadow-inset-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="flex items-center gap-2 font-mono text-[13px] font-bold text-ink">
                    <span className="material-symbols-outlined text-[20px] text-pvn-blue">payments</span>
                    Зарплатная вилка (на руки, ₽) *
                  </span>
                  <span className="stat-pill bg-pvn-blue text-white">Правило платформы</span>
                </div>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div className="flex items-center rounded-xl bg-raised px-3 shadow-raised-sm focus-within:ring-2 focus-within:ring-pvn-blue/40">
                    <span className="font-mono text-[12px] text-ink-muted">от</span>
                    <input
                      className="w-full bg-transparent px-2 py-2.5 font-mono text-[16px] font-bold text-ink placeholder:font-normal placeholder:italic placeholder:text-ink-muted/45 focus:outline-none"
                      min={1}
                      onChange={(event) => setVacancyForm({ ...vacancyForm, salaryFrom: event.target.value })}
                      placeholder="220 000"
                      required
                      type="number"
                      value={vacancyForm.salaryFrom}
                    />
                  </div>
                  <div className="flex items-center rounded-xl bg-raised px-3 shadow-raised-sm focus-within:ring-2 focus-within:ring-pvn-blue/40">
                    <span className="font-mono text-[12px] text-ink-muted">до</span>
                    <input
                      className="w-full bg-transparent px-2 py-2.5 font-mono text-[16px] font-bold text-ink placeholder:font-normal placeholder:italic placeholder:text-ink-muted/45 focus:outline-none"
                      min={1}
                      onChange={(event) => setVacancyForm({ ...vacancyForm, salaryTo: event.target.value })}
                      placeholder="290 000"
                      required
                      type="number"
                      value={vacancyForm.salaryTo}
                    />
                  </div>
                </div>
                <p className="font-sans text-caption text-ink-secondary">
                  Указанная вилка фиксируется на платформе. Предложение кандидату ниже нижней границы недопустимо.
                </p>
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="label-cap" htmlFor="vacancy-description">Описание проекта и ключевые задачи</label>
                <textarea
                  className="field resize-none"
                  id="vacancy-description"
                  onChange={(event) => setVacancyForm({ ...vacancyForm, description: event.target.value })}
                  placeholder="Разработка отказоустойчивых сервисов и распределённой маршрутизации событий…"
                  rows={3}
                  value={vacancyForm.description}
                />
              </div>
              {formError !== null ? (
                <div className="flex items-center gap-2 rounded-xl bg-pvn-red/10 px-4 py-3 font-sans text-caption text-pvn-red-ink">
                  <span className="material-symbols-outlined text-[18px]">error</span>
                  <span>{formError}</span>
                </div>
              ) : null}
              <div className="sticky bottom-0 -mx-6 flex flex-col items-center justify-end gap-3 border-t border-ink/10 bg-raised px-6 pb-1 pt-4 sm:flex-row">
                <button className="btn-ghost w-full sm:w-auto" onClick={closeModal} type="button">Отмена</button>
                <button className="btn-primary w-full sm:w-auto" disabled={isSubmitting} type="submit">
                  {isSubmitting
                    ? modalMode === 'edit'
                      ? 'Сохранение…'
                      : 'Публикация…'
                    : modalMode === 'edit'
                      ? 'Сохранить изменения'
                      : 'Опубликовать вакансию'}
                  <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
                </button>
              </div>
            </form>
          </div>
        </Modal>
      ) : null}
    </div>
  )
}
