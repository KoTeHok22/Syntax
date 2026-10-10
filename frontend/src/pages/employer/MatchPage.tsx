import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError } from '../../api/client'
import {
  createInvitation,
  fetchDomains,
  fetchEmployerProfile,
  searchCandidates,
  anonymousCandidateId,
} from '../../api/platform'
import type { CandidateCard as CandidateCardData, Domain, EmployerProfile } from '../../api/platform'
import { CandidateCard } from '../../components/CandidateCard'
import { CardColumns } from '../../components/CardColumns'
import { Modal } from '../../components/Modal'
import { Toast } from '../../components/Toast'

const PAGE_LIMIT = 20
const CATEGORY_PAGE_SIZE = 12

const MIN_SCORE_OPTIONS = [0, 50, 60, 70, 80]

const SORT_OPTIONS = [
  { value: 'relevance', label: 'Сначала релевантные' },
  { value: 'score', label: 'По баллам ПВН' },
] as const

type SortMode = (typeof SORT_OPTIONS)[number]['value']

interface InvitationFormState {
  message: string
  salaryFrom: string
  salaryTo: string
  companyName: string
  contactMethod: string
}

const emptyInvitationForm: InvitationFormState = {
  message: '',
  salaryFrom: '',
  salaryTo: '',
  companyName: '',
  contactMethod: '',
}

function SkeletonCard() {
  return (
    <div className="flex animate-pulse flex-col gap-4 rounded-panel bg-raised p-6 shadow-raised">
      <div className="flex items-start justify-between">
        <div className="flex flex-col gap-2">
          <div className="h-5 w-40 rounded-lg bg-inset" />
          <div className="h-3 w-28 rounded-lg bg-inset" />
        </div>
        <div className="h-8 w-16 rounded-xl bg-inset" />
      </div>
      <div className="flex gap-1.5">
        <div className="h-6 w-20 rounded-full bg-inset" />
        <div className="h-6 w-16 rounded-full bg-inset" />
        <div className="h-6 w-24 rounded-full bg-inset" />
      </div>
      <div className="h-24 rounded-xl bg-inset" />
      <div className="h-11 rounded-xl bg-inset" />
    </div>
  )
}

export function MatchPage() {
  const navigate = useNavigate()
  const [domains, setDomains] = useState<Domain[]>([])
  const [categoriesError, setCategoriesError] = useState<string | null>(null)
  const [isLoadingCategories, setIsLoadingCategories] = useState(true)
  const [activeDomain, setActiveDomain] = useState<Domain | null>(null)
  const [cards, setCards] = useState<CandidateCardData[]>([])
  const [cardsError, setCardsError] = useState<string | null>(null)
  const [isLoadingCards, setIsLoadingCards] = useState(false)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const [hasMore, setHasMore] = useState(false)
  const [stackInput, setStackInput] = useState('')
  const [stackFilters, setStackFilters] = useState<string[]>([])
  const [hasPvn, setHasPvn] = useState(false)
  const [minScore, setMinScore] = useState<number>(0)
  const [sortBy, setSortBy] = useState<SortMode>('relevance')
  const [inviteCard, setInviteCard] = useState<CandidateCardData | null>(null)
  const [invitationForm, setInvitationForm] = useState<InvitationFormState>(emptyInvitationForm)
  const [employerProfile, setEmployerProfile] = useState<EmployerProfile | null>(null)
  const [invitationError, setInvitationError] = useState<string | null>(null)
  const [isSubmittingInvitation, setIsSubmittingInvitation] = useState(false)
  const [successNotice, setSuccessNotice] = useState<string | null>(null)

  const [categorySearch, setCategorySearch] = useState('')
  const [categoryTotal, setCategoryTotal] = useState(0)
  const [poolTotal, setPoolTotal] = useState(0)
  const [isLoadingMoreCategories, setIsLoadingMoreCategories] = useState(false)

  const loadCategories = useCallback(async (query: string, skip: number) => {
    if (skip === 0) setIsLoadingCategories(true)
    else setIsLoadingMoreCategories(true)
    setCategoriesError(null)
    try {
      const page = await fetchDomains({ q: query, skip, limit: CATEGORY_PAGE_SIZE })
      setDomains((previous) => (skip === 0 ? page.items : [...previous, ...page.items]))
      setCategoryTotal(page.total)
      if (skip === 0 && page.items.length > 0) setActiveDomain((current) => current ?? page.items[0])
      if (skip === 0 && query === '') {
        setPoolTotal(page.items.reduce((sum, domain) => sum + domain.candidate_count, 0))
      }
    } catch (exception) {
      if (exception instanceof ApiError) setCategoriesError(exception.detail)
      else setCategoriesError('Не удалось загрузить направления')
    } finally {
      setIsLoadingCategories(false)
      setIsLoadingMoreCategories(false)
    }
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadCategories(categorySearch.trim(), 0)
    }, categorySearch === '' ? 0 : 250)
    return () => window.clearTimeout(timer)
  }, [categorySearch, loadCategories])


  const loadCards = useCallback(
    async (skip: number) => {
      if (activeDomain === null) return
      if (skip === 0) setIsLoadingCards(true)
      else setIsLoadingMore(true)
      setCardsError(null)
      try {
        const loaded = await searchCandidates({
          specialization: activeDomain.slug,
          q: activeDomain.title,
          stack: stackFilters.length > 0 ? stackFilters : undefined,
          has_pvn: hasPvn ? true : undefined,
          min_score: minScore > 0 ? minScore : undefined,
          skip,
          limit: PAGE_LIMIT,
        })
        setCards((previous) => (skip === 0 ? loaded : [...previous, ...loaded]))
        setHasMore(loaded.length === PAGE_LIMIT)
      } catch (exception) {
        if (exception instanceof ApiError) setCardsError(exception.detail)
        else setCardsError('Не удалось загрузить кандидатов')
      } finally {
        setIsLoadingCards(false)
        setIsLoadingMore(false)
      }
    },
    [activeDomain, stackFilters, hasPvn, minScore],
  )

  const stackKey = stackFilters.join(',')
  const activeSlug = activeDomain?.slug ?? ''

  useEffect(() => {
    if (activeSlug === '') return
    const controller = new AbortController()
    void (async () => {
      if (controller.signal.aborted) return
      await loadCards(0)
    })()
    return () => controller.abort()
  }, [activeSlug, stackKey, hasPvn, minScore, loadCards])

  useEffect(() => {
    fetchEmployerProfile()
      .then((profile) => setEmployerProfile(profile))
      .catch(() => setEmployerProfile(null))
  }, [])

  const totalPool = poolTotal

  const sortedDomains = useMemo(
    () => [...domains].sort((left, right) => Number(right.candidate_count > 0) - Number(left.candidate_count > 0)),
    [domains],
  )

  const sortedCards = useMemo(() => {
    const sorted = [...cards]
    if (sortBy === 'score') sorted.sort((left, right) => right.score - left.score)
    else sorted.sort((left, right) => right.final_score - left.final_score)
    return sorted
  }, [cards, sortBy])

  const addStackFilter = () => {
    const parsed = stackInput
      .split(/[,\s]+/)
      .map((item) => item.trim())
      .filter((item) => item.length > 0)
    setStackInput('')
    if (parsed.length === 0) return
    setStackFilters((previous) => [...new Set([...previous, ...parsed])])
  }

  const openInvitationModal = (card: CandidateCardData) => {
    setInviteCard(card)
    setInvitationForm({
      ...emptyInvitationForm,
      companyName: employerProfile?.company_name ?? '',
      contactMethod: employerProfile?.contacts?.email ?? '',
    })
    setInvitationError(null)
  }

  const closeInvitationModal = () => {
    setInviteCard(null)
    setInvitationForm(emptyInvitationForm)
    setInvitationError(null)
  }

  const submitInvitation = async (event: React.FormEvent) => {
    event.preventDefault()
    if (inviteCard === null) return
    setInvitationError(null)
    const salaryFrom = Number(invitationForm.salaryFrom)
    const salaryTo = Number(invitationForm.salaryTo)
    if (!Number.isFinite(salaryFrom) || !Number.isFinite(salaryTo) || salaryFrom <= 0 || salaryTo <= 0) {
      setInvitationError('Укажите обе границы зарплатной вилки')
      return
    }
    if (salaryTo < salaryFrom) {
      setInvitationError('Верхняя граница вилки не может быть меньше нижней')
      return
    }
    if (invitationForm.message.trim().length === 0) {
      setInvitationError('Добавьте описание предложения — кандидат видит его до принятия')
      return
    }
    if (invitationForm.companyName.trim().length === 0) {
      setInvitationError('Укажите название компании')
      return
    }
    if (invitationForm.contactMethod.trim().length === 0) {
      setInvitationError('Укажите способ связи — он раскроется кандидату после принятия')
      return
    }
    setIsSubmittingInvitation(true)
    try {
      await createInvitation({
        candidate_profile_id: inviteCard.candidate_profile_id,
        message: invitationForm.message,
        salary_from: salaryFrom,
        salary_to: salaryTo,
        company_name: invitationForm.companyName,
        contact_method: invitationForm.contactMethod,
      })
      closeInvitationModal()
      setSuccessNotice(`Приглашение кандидату отправлено`)
    } catch (exception) {
      if (exception instanceof ApiError) setInvitationError(exception.detail)
      else setInvitationError('Не удалось отправить приглашение')
    } finally {
      setIsSubmittingInvitation(false)
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-[1280px] flex-col gap-6 px-4 py-8 sm:px-6">
      <div className="flex flex-col gap-1">
        <h1 className="font-mono text-display font-extrabold tracking-tight text-ink">Подбор кандидатов</h1>
        {!isLoadingCategories && totalPool > 0 ? (
          <p className="font-sans text-body text-ink-secondary">
            {totalPool.toLocaleString('ru-RU')} кандидатов. Контакты откроются после принятия приглашения.
          </p>
        ) : null}
      </div>

      <Toast actionLabel="К приглашениям" message={successNotice} onAction={() => navigate('/employer/invitations')} onClose={() => setSuccessNotice(null)} />

      <section className="flex flex-col gap-4 rounded-panel bg-raised p-5 shadow-raised">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <span className="font-mono text-[12px] uppercase tracking-wider text-ink-secondary">
            Направления
          </span>
          <div className="relative w-full md:max-w-xs">
            <span className="material-symbols-outlined pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[18px] text-ink-muted">search</span>
            <input
              aria-label="Поиск направления"
              className="field w-full py-2.5 pl-10 text-[14px]"
              onChange={(event) => setCategorySearch(event.target.value)}
              placeholder="Направление"
              type="search"
              value={categorySearch}
            />
          </div>
        </div>

        {domains.length === 0 && !isLoadingCategories ? (
          <span className="font-sans text-caption text-ink-secondary">Ничего не найдено по запросу</span>
        ) : (
          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {sortedDomains.map((domain) => {
              const isActive = domain.slug === activeSlug
              return (
                <button
                  aria-pressed={isActive}
                  className={`flex items-center gap-2.5 rounded-xl px-4 py-3 text-left transition-all ${
                    isActive
                      ? 'bg-pvn-blue text-white shadow-blue'
                      : domain.candidate_count === 0
                        ? 'bg-inset/60 text-ink-secondary shadow-inset-sm hover:bg-white hover:text-ink hover:shadow-raised-sm'
                        : 'bg-inset text-ink shadow-inset-sm hover:bg-white hover:shadow-raised-sm'
                  }`}
                  key={domain.id}
                  onClick={() => setActiveDomain(domain)}
                  type="button"
                >
                  <span className="min-w-0 truncate font-mono text-[13px] font-bold">{domain.title}</span>
                  <span className={`shrink-0 whitespace-nowrap font-mono text-[12px] font-semibold ${isActive ? 'text-white/80' : domain.candidate_count === 0 ? 'text-ink-muted' : 'text-ink-secondary'}`}>
                    · {domain.candidate_count}
                  </span>
                </button>
              )
            })}
          </div>
        )}

        {domains.length < categoryTotal ? (
          <div className="flex justify-center">
            <button
              className="btn-ghost py-2 text-[13px]"
              disabled={isLoadingMoreCategories}
              onClick={() => void loadCategories(categorySearch.trim(), domains.length)}
              type="button"
            >
              {isLoadingMoreCategories ? 'Загружаем...' : `Показать ещё (${categoryTotal - domains.length})`}
            </button>
          </div>
        ) : null}
      </section>

      {isLoadingCategories ? (
        <div className="flex flex-col gap-4 rounded-panel bg-raised p-6 shadow-raised">
          <div className="h-7 w-64 rounded-lg bg-inset" />
          <div className="h-11 rounded-xl bg-inset" />
          <div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </div>
        </div>
      ) : categoriesError !== null ? (
        <div className="flex items-center gap-3 rounded-panel bg-pvn-red/10 px-5 py-4 font-sans text-caption text-pvn-red-ink shadow-raised-sm">
          <span className="material-symbols-outlined text-[18px]">error</span>
          <span>{categoriesError}</span>
          <button className="ml-auto font-mono font-semibold underline" onClick={() => void loadCategories(categorySearch.trim(), 0)} type="button">
            Повторить
          </button>
        </div>
      ) : domains.length === 0 ? (
        <div className="flex flex-col items-center gap-3 rounded-panel bg-raised p-12 text-center shadow-raised">
          <span className="material-symbols-outlined text-[40px] text-ink-muted">category</span>
          <span className="font-mono text-h2 font-bold text-ink">Ничего не найдено</span>
          <span className="font-sans text-caption text-ink-secondary">Направления кандидатов пока не сформированы</span>
        </div>
      ) : (
        <>
          <div className="flex flex-col gap-5 rounded-panel bg-raised p-6 shadow-raised">
            {activeDomain !== null ? (
              <div className="flex flex-col gap-2 border-b border-ink/10 pb-5 md:flex-row md:items-end md:justify-between">
                <h2 className="font-mono text-h2 font-extrabold tracking-tight text-ink">{activeDomain.title}</h2>
                <span className="font-sans text-caption text-ink-secondary">{activeDomain.candidate_count} кандидатов</span>
              </div>
            ) : null}

            <div className="flex flex-col gap-4 rounded-2xl bg-inset p-4 shadow-inset-sm xl:flex-row xl:items-center xl:justify-between">
              <div className="flex flex-1 flex-wrap items-center gap-2">
                <div className="relative min-w-[240px] flex-1">
                  <span className="material-symbols-outlined pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[18px] text-ink-muted">search</span>
                  <input
                    className="field py-2.5 pl-10 text-[14px]"
                    onChange={(event) => setStackInput(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter') {
                        event.preventDefault()
                        addStackFilter()
                      }
                    }}
                    placeholder="Поиск по навыкам"
                    type="text"
                    value={stackInput}
                  />
                </div>
                {stackFilters.map((technology) => (
                  <span className="chip" key={technology}>
                    {technology}
                    <button
                      className="ml-1 flex items-center text-ink-muted hover:text-pvn-red-ink"
                      onClick={() => setStackFilters(stackFilters.filter((item) => item !== technology))}
                      type="button"
                    >
                      <span className="material-symbols-outlined text-[14px]">close</span>
                    </button>
                  </span>
                ))}
                <button className="flex items-center gap-1 rounded-full px-3 py-1.5 font-mono text-[12px] font-semibold text-pvn-blue hover:bg-pvn-blue/10" onClick={addStackFilter} type="button">
                  <span className="material-symbols-outlined text-[16px]">add</span> Добавить
                </button>
              </div>
              <div className="flex flex-wrap items-center gap-4 border-t border-ink/10 pt-3 xl:border-t-0 xl:pt-0">
                <label className="flex cursor-pointer select-none items-center gap-2">
                  <input
                    checked={hasPvn}
                    className="h-4 w-4 rounded accent-pvn-blue"
                    onChange={(event) => setHasPvn(event.target.checked)}
                    type="checkbox"
                  />
                  <span className="font-sans text-caption font-medium text-ink">Только с ПВН</span>
                </label>
                <label className="flex items-center gap-2">
                  <span className="font-mono text-[11px] uppercase tracking-wider text-ink-muted">Балл</span>
                  <select
                    className="rounded-lg bg-base px-2 py-1.5 font-mono text-[12px] font-medium text-ink shadow-raised-sm focus:outline-none"
                    onChange={(event) => setMinScore(Number(event.target.value))}
                    value={minScore}
                  >
                    {MIN_SCORE_OPTIONS.map((option) => (
                      <option key={option} value={option}>
                        {option === 0 ? 'любой' : `от ${option}`}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="flex items-center gap-2">
                  <span className="font-mono text-[11px] uppercase tracking-wider text-ink-muted">Сортировка</span>
                  <select
                    className="rounded-lg bg-base px-2 py-1.5 font-mono text-[12px] font-medium text-ink shadow-raised-sm focus:outline-none"
                    onChange={(event) => setSortBy(event.target.value as SortMode)}
                    value={sortBy}
                  >
                    {SORT_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            </div>

            {cardsError !== null ? (
              <div className="flex items-center gap-3 rounded-xl bg-pvn-red/10 px-4 py-3 font-sans text-caption text-pvn-red-ink">
                <span className="material-symbols-outlined text-[18px]">error</span>
                <span>{cardsError}</span>
                <button className="ml-auto font-mono font-semibold underline" onClick={() => void loadCards(0)} type="button">
                  Повторить
                </button>
              </div>
            ) : null}

            {isLoadingCards ? (
              <div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
                <SkeletonCard />
                <SkeletonCard />
                <SkeletonCard />
              </div>
            ) : !isLoadingCards && cards.length === 0 && cardsError === null ? (
              <div className="flex flex-col items-center gap-3 rounded-2xl bg-inset p-12 text-center shadow-inset-sm">
                <span className="material-symbols-outlined text-[36px] text-ink-muted">person_search</span>
                <span className="font-mono text-h2 font-bold text-ink">Ничего не найдено</span>
                <span className="max-w-md font-sans text-caption text-ink-secondary">
                  Под выбранные фильтры в этом направлении не подходит ни один кандидат
                </span>
                <button
                  className="font-mono text-[13px] font-semibold text-pvn-blue hover:underline"
                  onClick={() => {
                    setStackFilters([])
                    setHasPvn(false)
                    setMinScore(0)
                  }}
                  type="button"
                >
                  Сбросить фильтры
                </button>
              </div>
            ) : (
              <>
                <CardColumns
                  columns={3}
                  getKey={(card) => card.candidate_profile_id}
                  items={sortedCards}
                  renderItem={(card) => (
                    <CandidateCard card={card} onInvite={openInvitationModal} relevanceLabel="Совпадение с направлением" />
                  )}
                />
                <div className="flex flex-col items-center justify-between gap-4 pt-2 sm:flex-row">
                  <span className="font-mono text-[12px] text-ink-secondary">
                    Показано <span className="font-bold text-ink">{cards.length}</span> кандидатов
                  </span>
                  {hasMore ? (
                    <button
                      className="btn-ghost text-[13px]"
                      disabled={isLoadingMore}
                      onClick={() => void loadCards(cards.length)}
                      type="button"
                    >
                      <span className="material-symbols-outlined text-[18px]">expand_more</span>
                      Показать ещё
                    </button>
                  ) : null}
                </div>
              </>
            )}
          </div>
        </>
      )}

      {inviteCard !== null ? (
        <Modal labelledBy="match-invite-title" onClose={closeInvitationModal} open panelClassName="relative w-full max-w-2xl overflow-hidden rounded-panel bg-raised shadow-raised-lg">
          <div className="flex items-center justify-between border-b border-ink/10 px-6 py-4">
            <h3 className="font-mono text-h2 font-extrabold tracking-tight text-ink" id="match-invite-title">
                Приглашение кандидату {anonymousCandidateId(inviteCard.candidate_profile_id)}
              </h3>
              <button
                className="flex h-9 w-9 items-center justify-center rounded-xl text-ink-muted transition-all hover:bg-inset hover:text-ink"
                onClick={closeInvitationModal}
                title="Закрыть"
                type="button"
              >
                <span className="material-symbols-outlined text-[20px]">close</span>
              </button>
            </div>
            <div className="flex items-center justify-between gap-3 bg-inset px-6 py-3 shadow-inset-sm">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-[13px] font-bold text-ink">
                  Кандидат {anonymousCandidateId(inviteCard.candidate_profile_id)}
                </span>
                {inviteCard.stack.slice(0, 3).map((technology) => (
                  <span className="chip bg-base" key={technology}>
                    {technology}
                  </span>
                ))}
              </div>
              <div className="flex items-baseline gap-1">
                <span className="font-mono text-[18px] font-extrabold text-pvn-blue">{Math.round(inviteCard.score)}</span>
                <span className="font-mono text-[12px] text-ink-secondary">/ 100</span>
              </div>
            </div>
            <form className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-6" noValidate onSubmit={submitInvitation}>
              <div className="flex flex-col gap-1.5">
                <label className="font-mono text-[12px] font-semibold uppercase tracking-wider text-ink" htmlFor="invite-message">
                  Описание предложения
                </label>
                <textarea
                  className="field resize-none leading-relaxed"
                  id="invite-message"
                  onChange={(event) => setInvitationForm({ ...invitationForm, message: event.target.value })}
                  placeholder="Проект, команда, задачи…"
                  required
                  rows={3}
                  value={invitationForm.message}
                />
              </div>
              <div className="flex flex-col gap-2 rounded-2xl bg-inset p-4 shadow-inset-sm">
                <label className="font-mono text-[12px] font-bold uppercase tracking-wider text-ink">
                  Зарплата, ₽ <span className="text-pvn-red-ink">*</span>
                </label>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div className="flex items-center rounded-xl bg-raised px-3 shadow-raised-sm focus-within:ring-2 focus-within:ring-pvn-blue/40">
                    <span className="font-mono text-[12px] text-ink-muted">от</span>
                    <input
                      className="w-full bg-transparent px-2 py-2.5 font-mono text-[16px] font-bold text-ink placeholder:font-normal placeholder:italic placeholder:text-ink-muted/45 focus:outline-none"
                      min={1}
                      onChange={(event) => setInvitationForm({ ...invitationForm, salaryFrom: event.target.value })}
                      placeholder="180 000"
                      required
                      type="number"
                      value={invitationForm.salaryFrom}
                    />
                  </div>
                  <div className="flex items-center rounded-xl bg-raised px-3 shadow-raised-sm focus-within:ring-2 focus-within:ring-pvn-blue/40">
                    <span className="font-mono text-[12px] text-ink-muted">до</span>
                    <input
                      className="w-full bg-transparent px-2 py-2.5 font-mono text-[16px] font-bold text-ink placeholder:font-normal placeholder:italic placeholder:text-ink-muted/45 focus:outline-none"
                      min={1}
                      onChange={(event) => setInvitationForm({ ...invitationForm, salaryTo: event.target.value })}
                      placeholder="240 000"
                      required
                      type="number"
                      value={invitationForm.salaryTo}
                    />
                  </div>
                </div>
                <p className="font-sans text-[12px] text-ink-secondary">Пример: от 180 000 до 240 000 ₽</p>
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="font-mono text-[12px] font-semibold uppercase tracking-wider text-ink" htmlFor="invite-contact">
                  Способ связи
                </label>
                <input
                  className="field"
                  id="invite-contact"
                  onChange={(event) => setInvitationForm({ ...invitationForm, contactMethod: event.target.value })}
                  placeholder="tg: @hr_techno"
                  required
                  type="text"
                  value={invitationForm.contactMethod}
                />
              </div>
              <p className="font-sans text-[13px] text-ink-secondary">Кандидат увидит зарплату и описание до ответа.</p>
              {invitationError !== null ? (
                <div className="flex items-center gap-2 rounded-xl bg-pvn-red/10 px-4 py-3 font-sans text-caption text-pvn-red-ink">
                  <span className="material-symbols-outlined text-[18px]">error</span>
                  <span>{invitationError}</span>
                </div>
              ) : null}
              <div className="sticky bottom-0 -mx-6 flex items-center justify-end gap-3 border-t border-ink/10 bg-raised px-6 pb-1 pt-4">
                <button className="btn-ghost" onClick={closeInvitationModal} type="button">
                  Отмена
                </button>
                <button className="btn-primary" disabled={isSubmittingInvitation} type="submit">
                  {isSubmittingInvitation ? 'Отправка…' : 'Отправить'}
                </button>
              </div>
            </form>
        </Modal>
      ) : null}
    </div>
  )
}
