import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { ApiError, post } from '../api/client'
import { BrandLockup } from '../components/Brand'
import { gradeLabel, specializationLabel } from '../lib/format'

type Mode = 'login' | 'register'

function confirmationLink(url: string | null): string | null {
  if (url === null) return null
  const token = url.split('/').filter((part) => part !== '').pop()
  if (token === undefined) return null
  return `/auth/confirm/${token}`
}

const FALLBACK_SPECIALIZATIONS = ['backend', 'frontend', 'data', 'devops', 'mobile', 'qa', 'design'] as const
const GRADE_OPTIONS = ['junior', 'middle', 'senior'] as const
type Grade = (typeof GRADE_OPTIONS)[number]

function HeroArt() {
  return (
    <svg className="pointer-events-none absolute inset-x-0 bottom-0 h-72 w-full opacity-70" fill="none" viewBox="0 0 620 300" xmlns="http://www.w3.org/2000/svg">
      <path d="M -20 250 L 120 250 L 170 200 L 360 200 L 420 250 L 640 250" stroke="#8E86FF" strokeWidth="1.5" />
      <path d="M -20 200 L 140 200 L 210 130 L 400 130 L 470 195 L 640 195" stroke="#B7B1FF" strokeDasharray="5 5" strokeWidth="1.5" />
      <path d="M -20 155 L 90 155 L 150 100 L 330 100 L 390 155 L 640 155" stroke="#8E86FF" strokeWidth="1.5" />
      <path d="M 120 285 L 250 285 L 310 225 L 520 225 L 570 270 L 640 270" stroke="#8E86FF" strokeWidth="1" />
      <circle cx="170" cy="200" fill="#FFFFFF" r="5" />
      <circle cx="210" cy="130" fill="#FFFFFF" r="6" />
      <circle cx="150" cy="100" fill="#FFFFFF" r="4" />
      <circle cx="310" cy="225" fill="#EC1D35" r="6" stroke="#FFFFFF" strokeWidth="2" />
      <circle cx="470" cy="195" fill="#FFFFFF" r="4" />
      <path d="M 300 45 L 360 45 L 400 20 L 470 20" stroke="#B7B1FF" strokeDasharray="4 4" strokeWidth="1" />
    </svg>
  )
}

const HERO_CONTENT = {
  candidate: {
    headline: 'Работодатель находит вас по подтверждённым навыкам',
    description: 'Зарплата видна до первого контакта. Профиль анонимный, контакты открываются после принятия.',
    stats: [
      { value: '3 400+', label: 'разработчиков' },
      { value: '180+', label: 'компаний' },
      { value: '48 ч.', label: 'до оффера' },
    ],
  },
  employer: {
    headline: 'Найдите подтверждённых кандидатов за 48 часов',
    description: 'Анонимные анкеты с проверенным грейдом и прозрачным баллом. Вилка фиксируется до контакта.',
    stats: [
      { value: '3 400+', label: 'кандидатов' },
      { value: '180+', label: 'компаний' },
      { value: '48 ч.', label: 'до шортлиста' },
    ],
  },
} as const

export function LoginPage() {
  const { login, register } = useAuth()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const [mode, setMode] = useState<Mode>(searchParams.get('tab') === 'register' ? 'register' : 'login')
  const [role, setRole] = useState<'candidate' | 'employer'>('candidate')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [pvnId, setPvnId] = useState('')
  const [specialization, setSpecialization] = useState('')
  const [grade, setGrade] = useState<Grade>('junior')
  const [consent, setConsent] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [info, setInfo] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [needsConfirmation, setNeedsConfirmation] = useState(false)
  const [resendNotice, setResendNotice] = useState<string | null>(null)
  const [resendUrl, setResendUrl] = useState<string | null>(null)
  const [isResending, setIsResending] = useState(false)
  const [sessionExpired] = useState(searchParams.get('expired') === '1')

  useEffect(() => {
    if (searchParams.get('expired') !== '1') return
    const nextParams = new URLSearchParams(searchParams)
    nextParams.delete('expired')
    setSearchParams(nextParams, { replace: true })
  }, [searchParams, setSearchParams])

  const switchMode = (next: Mode) => {
    setMode(next)
    setError(null)
    setInfo(null)
    setNeedsConfirmation(false)
    setResendNotice(null)
    setResendUrl(null)
  }

  const hero = HERO_CONTENT[role]

  const submitLabel = mode === 'login' ? 'Войти' : 'Создать профиль'

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    setError(null)
    setInfo(null)
    setNeedsConfirmation(false)
    setResendNotice(null)
    setResendUrl(null)
    if (email.trim() === '') {
      setError('Укажите email')
      return
    }
    if (!email.includes('@') || !email.includes('.')) {
      setError('Укажите корректный email')
      return
    }
    if (password === '') {
      setError('Укажите пароль')
      return
    }
    if (mode === 'register' && password.length < 8) {
      setError('Пароль должен содержать не менее 8 символов')
      return
    }
    if (mode === 'register' && !consent) {
      setError('Подтвердите согласие на обработку данных, чтобы зарегистрироваться')
      return
    }
    if (mode === 'register' && role === 'candidate' && specialization.trim() === '') {
      setError('Укажите направление / специализацию')
      return
    }
    setIsSubmitting(true)
    try {
      if (mode === 'login') {
        const user = await login(email, password)
        navigate(user.role === 'employer' ? '/employer' : '/candidate', { replace: true })
      } else {
        const created = await register(
          email,
          password,
          role,
          pvnId,
          role === 'candidate' ? { specialization, grade } : undefined,
        )
        setInfo('Аккаунт создан. Проверьте почту — мы отправили ссылку для подтверждения.')
        setNeedsConfirmation(true)
        setResendUrl(confirmationLink(created.confirmation_url))
        setMode('login')
      }
    } catch (exception) {
      if (exception instanceof ApiError) {
        setError(exception.detail)
        if (exception.status === 403) setNeedsConfirmation(true)
      } else setError('Не удалось связаться с сервером')
    } finally {
      setIsSubmitting(false)
    }
  }

  const onResend = async () => {
    setError(null)
    setResendNotice(null)
    setResendUrl(null)
    if (email.trim() === '') {
      setError('Укажите email, указанный при регистрации')
      return
    }
    setIsResending(true)
    try {
      const result = await post<{ message: string; confirmation_url: string | null }>('/auth/resend-confirmation', { email })
      setResendNotice(result.message)
      setResendUrl(confirmationLink(result.confirmation_url))
    } catch (exception) {
      if (exception instanceof ApiError) setError(exception.detail)
      else setError('Не удалось связаться с сервером')
    } finally {
      setIsResending(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-base p-4 sm:p-8 lg:p-10">
      <div className="mx-auto flex w-full max-w-[1280px] flex-col justify-center gap-6 lg:grid lg:grid-cols-12 lg:items-center lg:gap-8">
        <section className="relative hidden flex-col justify-between gap-4 overflow-hidden rounded-panel bg-pvn-blue p-8 shadow-blue-lg sm:p-10 lg:col-span-5 lg:flex lg:self-center lg:p-10">
          <HeroArt />
          <div className="relative z-10 space-y-8">
            <BrandLockup size={40} tone="light" />
            <h1 className="font-mono text-[34px] font-extrabold leading-[1.15] tracking-tight text-white sm:text-[40px]">
              {hero.headline}
            </h1>
            <p className="max-w-md font-sans text-[16px] leading-relaxed text-white/90 [text-shadow:0_1px_2px_rgba(15,18,29,0.45)]">
              {hero.description}
            </p>
          </div>
          <div className="relative z-10 grid grid-cols-3 gap-3 border-t border-white/20 pt-4">
            {hero.stats.map((stat) => (
              <div key={stat.label}>
                <div className="font-mono text-[22px] font-bold text-white">{stat.value}</div>
                <div className="font-mono text-[10px] uppercase tracking-wider text-white/60">{stat.label}</div>
              </div>
            ))}
          </div>
        </section>

        <section className="flex flex-col self-center rounded-panel bg-raised p-6 shadow-raised-lg sm:p-10 lg:col-span-7">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <h2 className="font-mono text-[26px] font-extrabold tracking-tight text-ink sm:text-[30px]">
              {mode === 'login' ? 'Вход в платформу' : 'Регистрация'}
            </h2>
            <div className="flex items-center gap-1 rounded-full bg-inset p-1 shadow-inset-sm">
              <button
                className={mode === 'login' ? 'rounded-full bg-pvn-blue px-4 py-1.5 font-mono text-[12px] font-bold text-white shadow-blue' : 'rounded-full px-4 py-1.5 font-mono text-[12px] font-medium text-ink-secondary transition-all'}
                onClick={() => switchMode('login')}
                type="button"
              >
                Вход
              </button>
              <button
                className={mode === 'register' ? 'rounded-full bg-pvn-blue px-4 py-1.5 font-mono text-[12px] font-bold text-white shadow-blue' : 'rounded-full px-4 py-1.5 font-mono text-[12px] font-medium text-ink-secondary transition-all'}
                onClick={() => switchMode('register')}
                type="button"
              >
                Регистрация
              </button>
            </div>
          </div>

          {mode === 'register' ? (
          <div className="mt-6 grid grid-cols-2 gap-2 rounded-2xl bg-inset p-1.5 shadow-inset-sm">
            <button
              className={
                role === 'candidate'
                  ? 'flex items-center justify-center gap-2 rounded-xl bg-pvn-blue py-3 font-mono text-[13px] font-bold text-white shadow-blue'
                  : 'flex items-center justify-center gap-2 rounded-xl py-3 font-mono text-[13px] font-medium text-ink-secondary transition-all hover:text-ink'
              }
              onClick={() => { setRole('candidate'); setError(null); setInfo(null) }}
              type="button"
            >
              Я кандидат
            </button>
            <button
              className={
                role === 'employer'
                  ? 'flex items-center justify-center gap-2 rounded-xl bg-pvn-blue py-3 font-mono text-[13px] font-bold text-white shadow-blue'
                  : 'flex items-center justify-center gap-2 rounded-xl py-3 font-mono text-[13px] font-medium text-ink-secondary transition-all hover:text-ink'
              }
              onClick={() => { setRole('employer'); setError(null); setInfo(null) }}
              type="button"
            >
              Я работодатель
            </button>
          </div>
          ) : null}

          <form className="mt-6 flex flex-col gap-4" noValidate onSubmit={onSubmit}>
            <div className="relative">
              <span className="material-symbols-outlined pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[20px] text-ink-muted">mail</span>
              <input
                autoComplete="email"
                autoFocus
                className="field pl-12"
                id="user-email"
                name="email"
                onChange={(event) => setEmail(event.target.value)}
                placeholder="Email"
                type="email"
                value={email}
              />
            </div>
            <div className="relative">
              <span className="material-symbols-outlined pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[20px] text-ink-muted">lock</span>
              <input
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                className="field pl-12"
                id="user-password"
                name="password"
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Пароль"
                type="password"
                value={password}
              />
            </div>
            {mode === 'register' && role === 'candidate' ? (
              <div className="flex flex-col gap-3">
                <div className="flex flex-col gap-1.5">
                  <label className="font-mono text-[12px] font-medium text-ink-secondary" htmlFor="candidate-specialization">
                    Направление / специализация
                  </label>
                  <select
                    className="field cursor-pointer"
                    id="candidate-specialization"
                    name="specialization"
                    onChange={(event) => setSpecialization(event.target.value)}
                    value={specialization}
                  >
                    <option disabled value="">Выберите направление</option>
                    {FALLBACK_SPECIALIZATIONS.map((item) => (
                      <option key={item} value={item}>{specializationLabel(item)}</option>
                    ))}
                  </select>
                </div>
                <div className="flex flex-col gap-1.5">
                  <span className="font-mono text-[12px] font-medium text-ink-secondary">Предполагаемый грейд</span>
                  <div className="grid grid-cols-3 gap-2 rounded-2xl bg-inset p-1.5 shadow-inset-sm">
                    {GRADE_OPTIONS.map((option) => (
                      <button
                        aria-pressed={grade === option}
                        className={
                          grade === option
                            ? 'rounded-xl bg-pvn-blue py-2.5 font-mono text-[13px] font-bold text-white shadow-blue'
                            : 'rounded-xl py-2.5 font-mono text-[13px] font-medium text-ink-secondary transition-all hover:text-ink'
                        }
                        key={option}
                        onClick={() => setGrade(option)}
                        type="button"
                      >
                        {gradeLabel(option)}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ) : null}
            {mode === 'register' && role === 'candidate' ? (
              <div className="relative">
                <span className="material-symbols-outlined pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[20px] text-ink-muted">badge</span>
                <input
                  autoComplete="off"
                  className="field pl-12"
                  id="pvn-id"
                  name="pvn_id"
                  onChange={(event) => setPvnId(event.target.value)}
                  placeholder="ПВН ID (необязательно)"
                  type="text"
                  value={pvnId}
                />
              </div>
            ) : null}

            {error !== null ? (
              <div className="rounded-xl bg-pvn-red/10 px-4 py-3 font-sans text-caption text-pvn-red-ink">{error}</div>
            ) : null}
            {error === null && sessionExpired && mode === 'login' ? (
              <div className="rounded-xl bg-pvn-red/10 px-4 py-3 font-sans text-caption text-pvn-red-ink">
                Сессия истекла — войдите снова, чтобы продолжить
              </div>
            ) : null}
            {info !== null ? (
              <div className="break-all rounded-xl bg-pvn-blue/10 px-4 py-3 font-sans text-caption text-pvn-blue">{info}</div>
            ) : null}

            {mode === 'login' && needsConfirmation ? (
              <div className="flex flex-col gap-3 rounded-xl bg-inset px-4 py-3 shadow-inset-sm">
                <p className="font-sans text-caption leading-snug text-ink-secondary">
                  Не пришло письмо? Отправим ссылку для подтверждения ещё раз.
                </p>
                <button
                  className="self-start rounded-full bg-pvn-blue px-4 py-2 font-mono text-[12px] font-bold text-white shadow-blue disabled:opacity-60"
                  disabled={isResending}
                  onClick={onResend}
                  type="button"
                >
                  {isResending ? 'Отправляем…' : 'Отправить письмо повторно'}
                </button>
                {resendNotice !== null ? (
                  <p className="font-sans text-caption leading-snug text-ink-secondary">{resendNotice}</p>
                ) : null}
                {resendUrl !== null ? (
                  <Link
                    className="self-start font-mono text-[12px] font-bold text-pvn-blue underline"
                    to={resendUrl}
                  >
                    Подтвердить сейчас
                  </Link>
                ) : null}
              </div>
            ) : null}

            <button className="btn-primary mt-2 w-full py-4 text-[16px]" disabled={isSubmitting} type="submit">
              {isSubmitting ? 'Отправка…' : submitLabel}
              <span className="material-symbols-outlined text-[20px]">arrow_forward</span>
            </button>
          </form>

          {mode === 'register' ? (
            <div className="mt-6 flex flex-col gap-3 border-t border-ink/10 pt-5">
              <label className="flex cursor-pointer items-center gap-3">
                <input
                  checked={consent}
                  className="h-5 w-5 shrink-0 rounded-md accent-pvn-blue"
                  onChange={(event) => setConsent(event.target.checked)}
                  type="checkbox"
                />
                <span className="font-sans text-caption leading-snug text-ink-secondary">
                  {role === 'candidate'
                    ? 'Согласен на обработку персональных данных и публикацию анонимного профиля'
                    : 'Согласен с условиями платформы и обработкой персональных данных'}
                </span>
              </label>
            </div>
          ) : null}
        </section>
      </div>
    </div>
  )
}
