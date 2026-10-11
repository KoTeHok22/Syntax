import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ApiError } from '../../api/client'
import { createInvitation, fetchDomains, fetchEmployerProfile, fetchMyVacancies, searchCandidates, anonymousCandidateId } from '../../api/platform'
import type { CandidateCard as CandidateCardData, Domain, Vacancy } from '../../api/platform'
import { CandidateCard } from '../../components/CandidateCard'
import { CandidateProofPanel } from '../../components/CandidateProofPanel'
import { CardColumns } from '../../components/CardColumns'
import { Modal } from '../../components/Modal'
import { Toast } from '../../components/Toast'

const PAGE_LIMIT = 20
const DEBOUNCE_MS = 400
const DOMAIN_SUGGESTION_LIMIT = 6
const VACANCY_PAGE_LIMIT = 200

const GRADES = [
  { value: '', label: 'Любой' },
  { value: 'junior', label: 'Junior' },
  { value: 'middle', label: 'Middle' },
  { value: 'senior', label: 'Senior' },
]

const MIN_SCORE_OPTIONS = [0, 50, 60, 70, 80]

interface InvitationFormState {
  message: string
  salaryFrom: string
  salaryTo: string
  companyName: string
  contactMethod: string
}

interface InvitationFieldErrors {
  salaryFrom: string | null
  salaryTo: string | null
  contactMethod: string | null
}

const emptyInvitationForm: InvitationFormState = {
  message: '',
  salaryFrom: '',
  salaryTo: '',
  companyName: '',
  contactMethod: '',
}

const emptyInvitationErrors: InvitationFieldErrors = {
  salaryFrom: null,
  salaryTo: null,
  contactMethod: null,
}

function SkeletonCard() {
  return (
    <div className="flex animate-pulse flex-col gap-4 rounded-panel bg-raised p-6 shadow-raised">
      <div className="h-5 w-40 rounded-lg bg-inset" />
      <div className="h-3 w-28 rounded-lg bg-inset" />
      <div className="h-6 w-3/4 rounded-full bg-inset" />
      <div className="h-24 rounded-xl bg-inset" />
      <div className="h-11 rounded-xl bg-inset" />
    </div>
  )
}

export function EmployerSearchPage() {
  const [vacancies, setVacancies] = useState<Vacancy[]>([])
  const [vacancyId, setVacancyId] = useState<number | undefined>()
  const [vacanciesError, setVacanciesError] = useState<string | null>(null)
  const [isLoadingVacancies, setIsLoadingVacancies] = useState(true)
  const [vacanciesReloadToken, setVacanciesReloadToken] = useState(0)
  const [stackInput, setStackInput] = useState('')
  const [stackFilters, setStackFilters] = useState<string[]>([])
  const [domainInput, setDomainInput] = useState('')
  const [selectedDomain, setSelectedDomain] = useState<Domain | null>(null)
  const [domainSuggestions, setDomainSuggestions] = useState<Domain[]>([])
  const [isDomainFocused, setIsDomainFocused] = useState(false)
  const [grade, setGrade] = useState('')
  const [hasPvn, setHasPvn] = useState(false)
  const [verifiedOnly, setVerifiedOnly] = useState(false)
  const [minScore, setMinScore] = useState(0)
  const [cards, setCards] = useState<CandidateCardData[]>([])
  const [searchError, setSearchError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const [hasMore, setHasMore] = useState(false)
  const [inviteCard, setInviteCard] = useState<CandidateCardData | null>(null)
  const [invitationForm, setInvitationForm] = useState<InvitationFormState>(emptyInvitationForm)
  const [invitationFieldErrors, setInvitationFieldErrors] = useState<InvitationFieldErrors>(emptyInvitationErrors)
  const [companyName, setCompanyName] = useState('')
  const [invitationError, setInvitationError] = useState<string | null>(null)
  const [isSubmittingInvitation, setIsSubmittingInvitation] = useState(false)
  const [inviteSuccess, setInviteSuccess] = useState<string | null>(null)

  const [debouncedStackInput, setDebouncedStackInput] = useState('')
  const [debouncedDomainInput, setDebouncedDomainInput] = useState('')
  const [reloadToken, setReloadToken] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    const loadVacancies = async () => {
      setVacanciesError(null)
      try {
        const loaded: Vacancy[] = []
        let page: Vacancy[]
        do {
          page = await fetchMyVacancies({ skip: loaded.length, limit: VACANCY_PAGE_LIMIT }, controller.signal)
          if (controller.signal.aborted) return
          loaded.push(...page)
        } while (page.length === VACANCY_PAGE_LIMIT)
        setVacancies(loaded)
      } catch (exception) {
        if (controller.signal.aborted) return
        setVacanciesError(exception instanceof ApiError ? exception.detail : 'Не удалось загрузить вакансии. Поиск по фильтрам доступен.')
      } finally {
        if (!controller.signal.aborted) setIsLoadingVacancies(false)
      }
    }
    void loadVacancies()
    return () => controller.abort()
  }, [vacanciesReloadToken])

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedStackInput(stackInput.trim()), DEBOUNCE_MS)
    return () => window.clearTimeout(timer)
  }, [stackInput])

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedDomainInput(domainInput.trim()), DEBOUNCE_MS)
    return () => window.clearTimeout(timer)
  }, [domainInput])

  useEffect(() => {
    if (debouncedDomainInput.length === 0) {
      setDomainSuggestions([])
      return
    }
    const controller = new AbortController()
    fetchDomains({ q: debouncedDomainInput, limit: DOMAIN_SUGGESTION_LIMIT })
      .then((page) => {
        if (!controller.signal.aborted) setDomainSuggestions(page.items)
      })
      .catch(() => {
        if (!controller.signal.aborted) setDomainSuggestions([])
      })
    return () => controller.abort()
  }, [debouncedDomainInput])

  const liveStackFilters = useMemo(() => {
    if (debouncedStackInput.length === 0) return stackFilters
    const parsed = debouncedStackInput
      .split(/[,\s]+/)
      .map((item) => item.trim())
      .filter((item) => item.length > 0)
    return [...new Set([...stackFilters, ...parsed])]
  }, [stackFilters, debouncedStackInput])

  const stackKey = liveStackFilters.join(',')
  const domainSlug = selectedDomain?.slug ?? ''
  const domainQuery = selectedDomain === null ? domainInput.trim() : ''
  const requestKey = `${vacancyId ?? ''}|${stackKey}|${domainSlug}|${domainQuery}|${grade}|${hasPvn}|${verifiedOnly}|${minScore}`
  const filtersRef = useRef({ requestKey, vacancyId, stackKey, domainSlug, domainQuery, grade, hasPvn, verifiedOnly, minScore })
  const searchGenerationRef = useRef(0)

  const loadCards = useCallback(async (skip: number, signal: AbortSignal) => {
    const current = filtersRef.current
    const generation = searchGenerationRef.current
    const activeStackFilters = current.stackKey.length > 0 ? current.stackKey.split(',') : []
    if (skip === 0) {
      setIsLoading(true)
      setIsLoadingMore(false)
      setCards([])
      setHasMore(false)
    } else setIsLoadingMore(true)
    setSearchError(null)
    try {
      const loaded = await searchCandidates(
        {
          vacancy_id: current.vacancyId,
          stack: activeStackFilters.length > 0 ? activeStackFilters : undefined,
          specialization: current.domainSlug !== '' ? current.domainSlug : undefined,
          q: current.domainSlug === '' && current.domainQuery !== '' ? current.domainQuery : undefined,
          grade: current.grade !== '' ? current.grade : undefined,
          has_pvn: current.hasPvn ? true : undefined,
          verified_only: current.verifiedOnly ? true : undefined,
          min_score: current.minScore > 0 ? current.minScore : undefined,
          skip,
          limit: PAGE_LIMIT,
        },
        signal,
      )
      if (signal.aborted || generation !== searchGenerationRef.current) return
      setCards((previous) => (skip === 0 ? loaded : [...previous, ...loaded]))
      setHasMore(loaded.length === PAGE_LIMIT)
    } catch (exception) {
      if (signal.aborted || generation !== searchGenerationRef.current || (exception instanceof DOMException && exception.name === 'AbortError')) return
      if (exception instanceof ApiError) setSearchError(exception.detail)
      else setSearchError('Не удалось выполнить поиск')
    } finally {
      if (!signal.aborted && generation === searchGenerationRef.current) {
        setIsLoading(false)
        setIsLoadingMore(false)
      }
    }
  }, [])

  useEffect(() => {
    filtersRef.current = { requestKey, vacancyId, stackKey, domainSlug, domainQuery, grade, hasPvn, verifiedOnly, minScore }
  }, [requestKey, vacancyId, stackKey, domainSlug, domainQuery, grade, hasPvn, verifiedOnly, minScore])

  useEffect(() => {
    searchGenerationRef.current += 1
    const controller = new AbortController()
    void loadCards(0, controller.signal)
    return () => {
      controller.abort()
      searchGenerationRef.current += 1
    }
  }, [requestKey, loadCards, reloadToken])

  const retrySearch = () => {
    setReloadToken((value) => value + 1)
  }

  const appliedChips = useMemo(() => {
    const chips: { label: string; onRemove: () => void }[] = []
    if (vacancyId !== undefined) {
      const vacancy = vacancies.find((item) => item.id === vacancyId)
      chips.push({ label: `Вакансия: ${vacancy?.title ?? 'выбрана'}`, onRemove: () => setVacancyId(undefined) })
    }
    if (selectedDomain !== null) {
      chips.push({ label: selectedDomain.title, onRemove: () => setSelectedDomain(null) })
    } else if (domainQuery !== '') {
      chips.push({ label: domainQuery, onRemove: () => setDomainInput('') })
    }
    if (grade !== '') {
      const label = GRADES.find((item) => item.value === grade)?.label ?? grade
      chips.push({ label, onRemove: () => setGrade('') })
    }
    stackFilters.forEach((technology) => {
      chips.push({
        label: technology,
        onRemove: () => setStackFilters((previous) => previous.filter((item) => item !== technology)),
      })
    })
    if (hasPvn) chips.push({ label: 'Только с ПВН', onRemove: () => setHasPvn(false) })
    if (verifiedOnly) chips.push({ label: 'Только с ПВН ID', onRemove: () => setVerifiedOnly(false) })
    if (minScore > 0) chips.push({ label: `Балл от ${minScore}`, onRemove: () => setMinScore(0) })
    return chips
  }, [vacancyId, vacancies, selectedDomain, domainQuery, grade, stackFilters, hasPvn, verifiedOnly, minScore])

  const applyStackInput = () => {
    const parsed = stackInput
      .split(/[,\s]+/)
      .map((item) => item.trim())
      .filter((item) => item.length > 0)
    setStackInput('')
    setDebouncedStackInput('')
    if (parsed.length === 0) return
    setStackFilters((previous) => [...new Set([...previous, ...parsed])])
  }

  const resetFilters = () => {
    setVacancyId(undefined)
    setStackFilters([])
    setSelectedDomain(null)
    setDomainInput('')
    setDomainSuggestions([])
    setGrade('')
    setHasPvn(false)
    setMinScore(0)
    setStackInput('')
    setDebouncedStackInput('')
  }

  useEffect(() => {
    let active = true
    const loadCompany = async () => {
      try {
        const profile = await fetchEmployerProfile()
        if (active) setCompanyName(profile.company_name ?? '')
      } catch {
        if (active) setCompanyName('')
      }
    }
    void loadCompany()
    return () => { active = false }
  }, [])

  const openInvitationModal = (card: CandidateCardData) => {
    setInviteCard(card)
    setInvitationForm(emptyInvitationForm)
    setInvitationFieldErrors(emptyInvitationErrors)
    setInvitationError(null)
  }

  const closeInvitationModal = () => {
    setInviteCard(null)
    setInvitationForm(emptyInvitationForm)
    setInvitationFieldErrors(emptyInvitationErrors)
    setInvitationError(null)
  }

  const submitInvitation = async (event: React.FormEvent) => {
    event.preventDefault()
    if (inviteCard === null) return
    setInvitationError(null)
    const salaryFrom = Number(invitationForm.salaryFrom)
    const salaryTo = Number(invitationForm.salaryTo)
    const fieldErrors: InvitationFieldErrors = { salaryFrom: null, salaryTo: null, contactMethod: null }
    if (invitationForm.salaryFrom.trim() === '' || !Number.isFinite(salaryFrom) || salaryFrom <= 0) {
      fieldErrors.salaryFrom = 'Укажите нижнюю границу вилки'
    }
    if (invitationForm.salaryTo.trim() === '' || !Number.isFinite(salaryTo) || salaryTo <= 0) {
      fieldErrors.salaryTo = 'Укажите верхнюю границу вилки'
    }
    if (invitationForm.contactMethod.trim() === '') {
      fieldErrors.contactMethod = 'Укажите способ связи — кандидат увидит его после принятия'
    }
    if (fieldErrors.salaryFrom !== null || fieldErrors.salaryTo !== null || fieldErrors.contactMethod !== null) {
      setInvitationFieldErrors(fieldErrors)
      setInvitationError('Заполните обязательные поля, отмеченные звёздочкой')
      return
    }
    setInvitationFieldErrors(emptyInvitationErrors)
    if (salaryTo < salaryFrom) {
      setInvitationFieldErrors({ ...emptyInvitationErrors, salaryTo: 'Верхняя граница не может быть меньше нижней' })
      setInvitationError('Проверьте зарплатную вилку')
      return
    }
    if (companyName.trim().length === 0) {
      setInvitationError('Заполните название компании в профиле — оно будет указано в приглашении')
      return
    }
    setIsSubmittingInvitation(true)
    try {
      await createInvitation({
        candidate_profile_id: inviteCard.candidate_profile_id,
        message: invitationForm.message,
        salary_from: salaryFrom,
        salary_to: salaryTo,
        company_name: companyName,
        contact_method: invitationForm.contactMethod,
      })
      closeInvitationModal()
      setInviteSuccess(`Приглашение кандидату ${anonymousCandidateId(inviteCard.candidate_profile_id)} отправлено`)
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
        <h1 className="font-mono text-display font-extrabold tracking-tight text-ink">Поиск кандидатов</h1>
        <p className="max-w-3xl font-sans text-body text-ink-secondary">
          Анонимные анкеты кандидатов: стек, грейд и подтверждённые результаты.
        </p>
      </div>

      <Toast message={inviteSuccess} onClose={() => setInviteSuccess(null)} />

      <div className="flex flex-col gap-4 rounded-panel bg-raised p-6 shadow-raised">
        <div className="flex flex-col gap-1.5">
          <label className="label-cap" htmlFor="search-vacancy">Подобрать для вакансии</label>
          <select
            aria-describedby="search-vacancy-help"
            className="field cursor-pointer py-2.5"
            disabled={isLoadingVacancies || vacanciesError !== null || vacancies.length === 0}
            id="search-vacancy"
            onChange={(event) => setVacancyId(event.target.value === '' ? undefined : Number(event.target.value))}
            value={vacancyId ?? ''}
          >
            <option value="">{isLoadingVacancies ? 'Загрузка вакансий…' : 'Без вакансии — поиск по фильтрам'}</option>
            {vacancies.map((vacancy) => (
              <option key={vacancy.id} value={vacancy.id}>
                {vacancy.title}{vacancy.is_open ? '' : ' (закрыта)'}
              </option>
            ))}
          </select>
          <p className="font-sans text-caption text-ink-secondary" id="search-vacancy-help">
            {vacancyId !== undefined
              ? 'Порядок кандидатов — по технологиям и смыслу опыта выбранной вакансии.'
              : !isLoadingVacancies && vacancies.length === 0 && vacanciesError === null
                ? 'У вас пока нет вакансий. Можно искать кандидатов по фильтрам ниже.'
                : 'Без вакансии кандидаты подбираются по фильтрам ниже.'}
          </p>
          {vacanciesError !== null ? (
            <div className="flex flex-wrap items-center gap-2 font-sans text-caption text-pvn-red-ink" role="alert">
              <span>{vacanciesError}</span>
              <button
                className="font-semibold underline"
                onClick={() => {
                  setIsLoadingVacancies(true)
                  setVacanciesReloadToken((value) => value + 1)
                }}
                type="button"
              >
                Повторить загрузку
              </button>
            </div>
          ) : null}
        </div>
        <form
          className="relative w-full"
          onSubmit={(event) => {
            event.preventDefault()
            applyStackInput()
          }}
        >
          <span className="material-symbols-outlined pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[20px] text-ink-muted">
            search
          </span>
          <input
            aria-label="Поиск по навыкам"
            className="field py-3.5 pl-12 pr-[7.5rem] sm:pr-32"
            onChange={(event) => setStackInput(event.target.value)}
            placeholder="Навык: Python, Kafka…"
            type="search"
            value={stackInput}
          />
          <button className="btn-blue absolute right-2 top-1/2 -translate-y-1/2 px-3 py-2 text-[13px] sm:px-4" type="submit">
            Добавить
          </button>
        </form>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="relative flex flex-col gap-1.5">
            <label className="label-cap" htmlFor="search-domain">Направление</label>
            <input
              aria-label="Поиск направления"
              className="field py-2.5"
              id="search-domain"
              onChange={(event) => {
                setDomainInput(event.target.value)
                setSelectedDomain(null)
              }}
              onFocus={() => setIsDomainFocused(true)}
              onBlur={() => window.setTimeout(() => setIsDomainFocused(false), 150)}
              placeholder="Backend, ML, аналитика…"
              type="search"
              value={selectedDomain !== null ? selectedDomain.title : domainInput}
            />
            {isDomainFocused && selectedDomain === null && domainSuggestions.length > 0 ? (
              <ul className="absolute left-0 right-0 top-full z-20 mt-1 flex max-h-64 flex-col overflow-auto rounded-xl bg-raised py-1 shadow-raised">
                {domainSuggestions.map((domain) => (
                  <li key={domain.id}>
                    <button
                      className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left transition-all hover:bg-inset"
                      onMouseDown={(event) => event.preventDefault()}
                      onClick={() => {
                        setSelectedDomain(domain)
                        setDomainInput('')
                        setDomainSuggestions([])
                        setIsDomainFocused(false)
                      }}
                      type="button"
                    >
                      <span className="min-w-0 truncate font-sans text-[13px] font-medium text-ink">{domain.title}</span>
                      <span className="shrink-0 font-mono text-[11px] text-ink-secondary">{domain.candidate_count}</span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="label-cap" htmlFor="search-grade">Грейд</label>
            <select
              className="field cursor-pointer py-2.5"
              id="search-grade"
              onChange={(event) => setGrade(event.target.value)}
              value={grade}
            >
              {GRADES.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="label-cap" htmlFor="search-score">Минимальный балл</label>
            <select
              className="field cursor-pointer py-2.5"
              id="search-score"
              onChange={(event) => setMinScore(Number(event.target.value))}
              value={minScore}
            >
              {MIN_SCORE_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option === 0 ? 'Не имеет значения' : `от ${option} / 100`}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <span className="label-cap">Дополнительно</span>
            <label className="flex cursor-pointer select-none items-center gap-2 py-2.5">
              <input
                checked={hasPvn}
                className="h-4 w-4 rounded accent-pvn-blue"
                onChange={(event) => setHasPvn(event.target.checked)}
                type="checkbox"
              />
              <span className="font-sans text-caption font-medium text-ink">Только с достижениями ПВН</span>
            </label>
            <label className="flex cursor-pointer select-none items-center gap-2 py-2.5">
              <input
                checked={verifiedOnly}
                className="h-4 w-4 rounded accent-pvn-blue"
                onChange={(event) => setVerifiedOnly(event.target.checked)}
                type="checkbox"
              />
              <span className="font-sans text-caption font-medium text-ink">Только с подтверждённым ПВН ID</span>
            </label>
          </div>
        </div>
        {appliedChips.length > 0 ? (
          <div className="flex flex-wrap items-center gap-2 border-t border-ink/10 pt-3">
            {appliedChips.map((chip) => (
              <span className="chip" key={chip.label}>
                {chip.label}
                <button aria-label={`Убрать фильтр: ${chip.label}`} className="ml-1 flex items-center text-ink-muted hover:text-pvn-red-ink" onClick={chip.onRemove} type="button">
                  <span className="material-symbols-outlined text-[14px]">close</span>
                </button>
              </span>
            ))}
            <button className="px-2 font-mono text-[12px] font-semibold text-pvn-red-ink hover:underline" onClick={resetFilters} type="button">
              Сбросить все
            </button>
          </div>
        ) : null}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <span className="font-mono text-h2 font-bold text-ink">
          {isLoading ? 'Поиск…' : `Найдено: ${cards.length}${hasMore ? '+' : ''}`}
        </span>
        <span className="font-sans text-caption text-ink-secondary">
          {isLoading
            ? ''
            : hasMore
              ? 'показаны первые — нажмите «Показать ещё», чтобы увидеть остальных'
              : cards.length === 0
                ? 'ни один кандидат не подходит под фильтры'
                : 'кандидатов соответствуют фильтрам'}
        </span>
      </div>

      {searchError !== null ? (
        <div className="flex items-center gap-3 rounded-panel bg-pvn-red/10 px-5 py-4 font-sans text-caption text-pvn-red-ink shadow-raised-sm">
          <span className="material-symbols-outlined text-[18px]">error</span>
          <span>{searchError}</span>
          <button className="ml-auto font-mono font-semibold underline" onClick={retrySearch} type="button">
            Повторить
          </button>
        </div>
      ) : null}

      {isLoading ? (
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : !isLoading && cards.length === 0 && searchError === null ? (
        <div className="flex flex-col items-center gap-3 rounded-panel bg-raised p-12 text-center shadow-raised">
          <span className="material-symbols-outlined text-[40px] text-ink-muted">person_search</span>
          <span className="font-mono text-h2 font-bold text-ink">Ничего не найдено</span>
          <span className="max-w-md font-sans text-caption text-ink-secondary">
            Под выбранные фильтры не подходит ни один кандидат. Искать можно по домену навыка — например,{' '}
            <span className="font-semibold text-ink">Python</span>, <span className="font-semibold text-ink">Kafka</span> или{' '}
            <span className="font-semibold text-ink">React</span>.
          </span>
          <div className="flex flex-wrap items-center justify-center gap-2">
            {['Python', 'Kafka', 'React', 'PostgreSQL'].map((skill) => (
              <button
                className="chip transition-all hover:bg-pvn-blue/10"
                key={skill}
                onClick={() => {
                  setStackFilters((previous) => (previous.includes(skill) ? previous : [...previous, skill]))
                }}
                type="button"
              >
                <span className="material-symbols-outlined text-[14px]">add</span>
                {skill}
              </button>
            ))}
          </div>
          <button className="font-mono text-[13px] font-semibold text-pvn-blue hover:underline" onClick={resetFilters} type="button">
            Сбросить фильтры
          </button>
        </div>
      ) : (
        <>
          <CardColumns
            columns={2}
            getKey={(card) => card.candidate_profile_id}
            items={cards}
            renderItem={(card) => (
              <div className="flex flex-col gap-3">
                <CandidateProofPanel card={card} />
                <CandidateCard card={card} onInvite={openInvitationModal} relevanceLabel={vacancyId !== undefined ? 'Совпадение с вакансией' : 'Совпадение с фильтрами'} />
              </div>
            )}
          />
          <div className="flex flex-col items-center justify-between gap-4 sm:flex-row">
            <span className="font-mono text-[12px] text-ink-secondary">
              Показано <span className="font-bold text-ink">{cards.length}</span> кандидатов
              {hasMore ? ' — есть ещё' : ''}
            </span>
            {hasMore ? (
              <button className="btn-ghost text-[13px]" disabled={isLoadingMore || searchError !== null} onClick={() => void loadCards(cards.length, new AbortController().signal)} type="button">
                <span className="material-symbols-outlined text-[18px]">expand_more</span>
                Показать ещё
              </button>
            ) : null}
          </div>
        </>
      )}



      {inviteCard !== null ? (
        <Modal labelledBy="search-invite-title" onClose={closeInvitationModal} open>
          <div className="flex items-center justify-between border-b border-ink/10 px-6 py-4">
            <h3 className="font-mono text-h2 font-extrabold tracking-tight text-ink" id="search-invite-title">
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
                  <span className="chip bg-base" key={technology}>{technology}</span>
                ))}
              </div>
              <div className="flex items-baseline gap-1">
                <span className="font-mono text-[18px] font-extrabold text-pvn-blue">{Math.round(inviteCard.score)}</span>
                <span className="font-mono text-[12px] text-ink-secondary">/ 100</span>
              </div>
            </div>
            <form className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-6" noValidate onSubmit={submitInvitation}>
              <div className="flex flex-col gap-1.5">
                <label className="font-mono text-[12px] font-semibold uppercase tracking-wider text-ink" htmlFor="search-invite-message">
                  Описание предложения
                </label>
                <textarea
                  className="field resize-none leading-relaxed"
                  id="search-invite-message"
                  onChange={(event) => setInvitationForm({ ...invitationForm, message: event.target.value })}
                  placeholder="Проект, команда, задачи…"
                  rows={3}
                  value={invitationForm.message}
                />
              </div>
              <div className="flex flex-col gap-2 rounded-2xl bg-inset p-4 shadow-inset-sm">
                <label className="font-mono text-[12px] font-bold uppercase tracking-wider text-ink">
                  Зарплата, ₽ <span className="text-pvn-red-ink">*</span>
                </label>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div className={`flex items-center rounded-xl bg-raised px-3 shadow-raised-sm focus-within:ring-2 focus-within:ring-pvn-blue/40 ${invitationFieldErrors.salaryFrom !== null ? 'ring-2 ring-pvn-red/40' : ''}`}>
                    <span className="font-mono text-[12px] text-ink-muted">от</span>
                    <input
                      className="w-full bg-transparent px-2 py-2.5 font-mono text-[16px] font-bold text-ink placeholder:font-normal placeholder:italic placeholder:text-ink-muted/35 focus:outline-none"
                      min={1}
                      onChange={(event) => {
                        setInvitationForm({ ...invitationForm, salaryFrom: event.target.value })
                        setInvitationFieldErrors((previous) => ({ ...previous, salaryFrom: null }))
                      }}
                      placeholder="например, 180 000"
                      type="number"
                      value={invitationForm.salaryFrom}
                    />
                  </div>
                  <div className={`flex items-center rounded-xl bg-raised px-3 shadow-raised-sm focus-within:ring-2 focus-within:ring-pvn-blue/40 ${invitationFieldErrors.salaryTo !== null ? 'ring-2 ring-pvn-red/40' : ''}`}>
                    <span className="font-mono text-[12px] text-ink-muted">до</span>
                    <input
                      className="w-full bg-transparent px-2 py-2.5 font-mono text-[16px] font-bold text-ink placeholder:font-normal placeholder:italic placeholder:text-ink-muted/35 focus:outline-none"
                      min={1}
                      onChange={(event) => {
                        setInvitationForm({ ...invitationForm, salaryTo: event.target.value })
                        setInvitationFieldErrors((previous) => ({ ...previous, salaryTo: null }))
                      }}
                      placeholder="например, 240 000"
                      type="number"
                      value={invitationForm.salaryTo}
                    />
                  </div>
                </div>
                {invitationFieldErrors.salaryFrom !== null ? (
                  <span className="font-sans text-[12px] font-semibold text-pvn-red-ink">{invitationFieldErrors.salaryFrom}</span>
                ) : null}
                {invitationFieldErrors.salaryTo !== null ? (
                  <span className="font-sans text-[12px] font-semibold text-pvn-red-ink">{invitationFieldErrors.salaryTo}</span>
                ) : null}
                <p className="font-sans text-[12px] text-ink-secondary">Укажите нижнюю и верхнюю границу вилки — кандидат увидит обе.</p>
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="font-mono text-[12px] font-semibold uppercase tracking-wider text-ink" htmlFor="search-invite-contact">
                  Способ связи <span className="text-pvn-red-ink">*</span>
                </label>
                <input
                  className={`field ${invitationFieldErrors.contactMethod !== null ? 'border-pvn-red/50 ring-1 ring-pvn-red/30' : ''}`}
                  id="search-invite-contact"
                  onChange={(event) => {
                    setInvitationForm({ ...invitationForm, contactMethod: event.target.value })
                    setInvitationFieldErrors((previous) => ({ ...previous, contactMethod: null }))
                  }}
                  placeholder="tg: @nickname"
                  type="text"
                  value={invitationForm.contactMethod}
                />
                {invitationFieldErrors.contactMethod !== null ? (
                  <span className="font-sans text-[12px] font-semibold text-pvn-red-ink">{invitationFieldErrors.contactMethod}</span>
                ) : null}
              </div>
              <p className="font-sans text-[13px] text-ink-secondary">Кандидат увидит зарплату и описание до ответа.</p>
              {invitationError !== null ? (
                <div className="flex items-center gap-2 rounded-xl bg-pvn-red/10 px-4 py-3 font-sans text-caption text-pvn-red-ink">
                  <span className="material-symbols-outlined text-[18px]">error</span>
                  <span>{invitationError}</span>
                </div>
              ) : null}
              <div className="sticky bottom-0 -mx-6 flex items-center justify-end gap-3 border-t border-ink/10 bg-raised px-6 pb-1 pt-4">
                <button className="btn-ghost" onClick={closeInvitationModal} type="button">Отмена</button>
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
