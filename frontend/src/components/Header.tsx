import { useEffect, useRef, useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { fetchEmployerProfile } from '../api/platform'
import { fetchCandidateProfile } from '../api/auth'
import { BrandLockup } from './Brand'
import { ConfirmDialog } from './ConfirmDialog'
import { isGenerationBusy } from '../lib/generationGuard'
import { LogoAvatar } from './LogoAvatar'
import type { LogoCrop } from '../lib/logoCrop'

const employerNav = [
  { to: '/employer', label: 'Подбор', end: true },
  { to: '/employer/search', label: 'Поиск', end: false },
  { to: '/employer/invitations', label: 'Приглашения', end: false },
  { to: '/employer/vacancies', label: 'Вакансии', end: false },
  { to: '/employer/applications', label: 'Отклики', end: false },
  { to: '/employer/regular-tasks', label: 'Задания', end: false },
]

const candidateNav = [
  { to: '/candidate', label: 'Профиль', end: true },
  { to: '/candidate/testing', label: 'Тестирование', end: false },
  { to: '/candidate/invitations', label: 'Приглашения', end: false },
  { to: '/candidate/vacancies', label: 'Вакансии', end: false },
  { to: '/candidate/applications', label: 'Мои отклики', end: false },
]

export function Header() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [logoutConfirmOpen, setLogoutConfirmOpen] = useState(false)
  const [leaveTarget, setLeaveTarget] = useState<string | null>(null)
  const [companyName, setCompanyName] = useState<string | null>(null)
  const [logo, setLogo] = useState<{ src: string; crop: LogoCrop } | null>(null)
  const [profileLoaded, setProfileLoaded] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (user === null) return
    let cancelled = false
    const loadProfile = () => {
      if (user.role === 'employer') {
        fetchEmployerProfile()
          .then((profile) => {
            if (cancelled) return
            setProfileLoaded(true)
            setCompanyName(profile.company_name.trim() || null)
            setLogo(
              profile.logo_data_url !== null
                ? {
                    src: profile.logo_data_url,
                    crop: { zoom: profile.logo_zoom, offsetX: profile.logo_offset_x, offsetY: profile.logo_offset_y },
                  }
                : null,
            )
          })
          .catch(() => {
            if (cancelled) return
            setProfileLoaded(true)
            setCompanyName(null)
            setLogo(null)
          })
        return
      }
      fetchCandidateProfile()
        .then((profile) => {
          if (cancelled) return
          setProfileLoaded(true)
          setCompanyName(null)
          setLogo(
            profile.avatar_data_url !== null
              ? {
                  src: profile.avatar_data_url,
                  crop: { zoom: profile.avatar_zoom, offsetX: profile.avatar_offset_x, offsetY: profile.avatar_offset_y },
                }
              : null,
          )
        })
        .catch(() => {
          if (!cancelled) {
            setProfileLoaded(true)
            setLogo(null)
          }
        })
    }
    loadProfile()
    window.addEventListener('syntax:profile-updated', loadProfile)
    return () => {
      cancelled = true
      window.removeEventListener('syntax:profile-updated', loadProfile)
    }
  }, [user])

  const employerProfilePending = user?.role === 'employer' && !profileLoaded

  const renderAvatar = (size: number) => {
    if (logo !== null) {
      return <LogoAvatar alt={user?.role === 'employer' ? companyName ?? 'Логотип компании' : 'Аватар'} crop={logo.crop} size={size} src={logo.src} />
    }
    if (employerProfilePending) {
      return (
        <span
          aria-hidden="true"
          className="shrink-0 animate-pulse rounded-full bg-ink/10"
          style={{ width: size, height: size }}
        />
      )
    }
    return (
      <span
        className="flex shrink-0 items-center justify-center rounded-full bg-pvn-blue font-mono font-bold text-white"
        style={{ width: size, height: size, fontSize: size <= 32 ? 12 : 13 }}
      >
        {initials}
      </span>
    )
  }

  useEffect(() => {
    const onClickCapture = (event: MouseEvent) => {
      if (!isGenerationBusy()) return
      const anchor = (event.target as HTMLElement | null)?.closest('a[href]')
      if (anchor === null || anchor === undefined) return
      const href = anchor.getAttribute('href')
      if (href === null || href.startsWith('#')) return
      event.preventDefault()
      event.stopPropagation()
      setLeaveTarget(href)
    }
    document.addEventListener('click', onClickCapture, true)
    return () => document.removeEventListener('click', onClickCapture, true)
  }, [])

  useEffect(() => {
    if (!menuOpen) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMenuOpen(false)
    }
    const onClickOutside = (event: MouseEvent) => {
      if (menuRef.current !== null && !menuRef.current.contains(event.target as Node)) setMenuOpen(false)
    }
    document.addEventListener('keydown', onKeyDown)
    document.addEventListener('mousedown', onClickOutside)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.removeEventListener('mousedown', onClickOutside)
    }
  }, [menuOpen])

  useEffect(() => {
    if (!mobileOpen) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMobileOpen(false)
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [mobileOpen])

  if (user === null) return null
  const links = user.role === 'employer' ? employerNav : candidateNav
  const initials = user.email.slice(0, 2).toUpperCase()
  const profileLink = user.role === 'employer' ? '/employer/company' : '/candidate'
  const profileLabel = user.role === 'employer' ? 'Профиль компании' : 'Мой профиль'

  const requestLogout = () => {
    setMobileOpen(false)
    setMenuOpen(false)
    setLogoutConfirmOpen(true)
  }

  const handleLogout = () => {
    setLogoutConfirmOpen(false)
    logout()
    navigate('/')
  }

  return (
    <header className="sticky top-0 z-50 w-full bg-base px-3 pt-3">
      <div className="mx-auto flex min-h-16 w-full max-w-[1280px] items-center justify-between gap-3 rounded-panel bg-pvn-blue px-4 py-2.5 shadow-blue-lg sm:gap-4 sm:px-5 sm:py-0">
        <div className="flex min-w-0 items-center gap-3 sm:gap-4">
          <button
            aria-expanded={mobileOpen}
            aria-label="Меню"
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-white/90 transition-all hover:bg-white/10 lg:hidden"
            onClick={() => setMobileOpen((previous) => !previous)}
            type="button"
          >
            <span className="material-symbols-outlined text-[24px]">{mobileOpen ? 'close' : 'menu'}</span>
          </button>
          <a className="flex shrink-0 items-center" href="#">
            <BrandLockup size={30} tone="light" />
          </a>
          <nav className="ml-2 hidden items-center gap-1 lg:flex">
            {links.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.end}
                className={({ isActive }) =>
                  isActive
                    ? 'rounded-full bg-white px-4 py-2 font-mono text-[13px] font-bold text-pvn-blue shadow-raised-sm transition-all'
                    : 'rounded-full px-4 py-2 font-mono text-[13px] font-medium text-white/80 transition-all hover:bg-white/10 hover:text-white'
                }
              >
                {link.label}
              </NavLink>
            ))}
          </nav>
        </div>
        <div className="relative flex shrink-0 items-center gap-3" ref={menuRef}>
          <button
            aria-expanded={menuOpen}
            aria-haspopup="menu"
            aria-label="Меню аккаунта"
            className="flex items-center gap-2 rounded-full bg-white p-1 shadow-raised-sm transition-all hover:shadow-raised sm:gap-3 sm:py-1 sm:pl-1 sm:pr-4"
            onClick={() => setMenuOpen((previous) => !previous)}
            type="button"
          >
            {renderAvatar(32)}
            <span className="hidden min-w-0 flex-col items-start leading-tight sm:flex sm:max-w-[200px]">
              {user.role === 'employer' && !profileLoaded ? (
                <span aria-hidden="true" className="h-3.5 w-28 max-w-full animate-pulse rounded bg-ink/15" />
              ) : (
                <span className="max-w-full truncate font-sans text-[13px] font-bold text-ink">
                  {user.role === 'employer' ? companyName ?? 'Профиль компании' : user.pvn_id ? `ПВН ${user.pvn_id}` : user.email.split('@')[0]}
                </span>
              )}
              <span className="font-mono text-[10px] uppercase tracking-wider text-ink-secondary">
                {user.role === 'employer' ? 'Работодатель' : 'Кандидат'}
              </span>
            </span>
            <span className={`material-symbols-outlined hidden text-[18px] text-ink-muted transition-transform sm:inline ${menuOpen ? 'rotate-180' : ''}`}>expand_more</span>
          </button>
          {menuOpen ? (
            <div
              className="absolute right-0 top-full z-50 mt-2 w-72 max-w-[calc(100vw-2rem)] overflow-hidden rounded-2xl border border-ink/10 bg-white shadow-[0_16px_40px_rgba(15,18,29,0.22)]"
              role="menu"
            >
              <div className="flex items-center gap-3 border-b border-ink/10 px-4 py-4">
                {renderAvatar(40)}
                <div className="flex min-w-0 flex-col">
                  {user.role === 'employer' && !profileLoaded ? (
                    <span aria-hidden="true" className="h-4 w-32 animate-pulse rounded bg-ink/15" />
                  ) : (
                    <span className="truncate font-sans text-[15px] font-semibold text-ink">
                      {user.role === 'employer' ? companyName ?? 'Профиль компании' : user.pvn_id ? `ПВН ${user.pvn_id}` : user.email.split('@')[0]}
                    </span>
                  )}
                  <span className="truncate font-sans text-caption text-ink-secondary">{user.email}</span>
                </div>
              </div>
              <div className="flex flex-col p-2">
                <button
                  className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left font-sans text-[14px] text-ink transition-all hover:bg-inset"
                  onClick={() => {
                    setMenuOpen(false)
                    navigate(profileLink)
                  }}
                  role="menuitem"
                  type="button"
                >
                  <span className="material-symbols-outlined text-[20px] text-pvn-blue">account_circle</span>
                  {profileLabel}
                </button>
                <button
                  className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left font-sans text-[14px] text-pvn-red-ink transition-all hover:bg-pvn-red/10"
                  onClick={requestLogout}
                  role="menuitem"
                  type="button"
                >
                  <span className="material-symbols-outlined text-[20px]">logout</span>
                  Выйти из аккаунта
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </div>

      {mobileOpen ? (
        <div className="mx-auto mt-2 w-full max-w-[1280px] overflow-hidden rounded-panel bg-pvn-blue p-2 shadow-blue-lg lg:hidden">
          <nav className="flex flex-col">
            {links.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.end}
                onClick={() => setMobileOpen(false)}
                className={({ isActive }) =>
                  isActive
                    ? 'rounded-xl bg-white px-4 py-3 font-mono text-[14px] font-bold text-pvn-blue'
                    : 'rounded-xl px-4 py-3 font-mono text-[14px] font-medium text-white/85 transition-all hover:bg-white/10 hover:text-white'
                }
              >
                {link.label}
              </NavLink>
            ))}
          </nav>
          <div className="mt-2 flex flex-col gap-1 border-t border-white/15 pt-2">
              <span className="px-4 py-1 font-mono text-[11px] lowercase tracking-wider text-white/50 break-all">{user.email.toLowerCase()}</span>
            <button
              className="flex items-center gap-2 rounded-xl px-4 py-3 text-left font-mono text-[14px] font-medium text-white/85 transition-all hover:bg-white/10"
              onClick={() => {
                setMobileOpen(false)
                navigate(profileLink)
              }}
              type="button"
            >
              <span className="material-symbols-outlined text-[18px]">account_circle</span>
              {profileLabel}
            </button>
            <button
              className="flex items-center gap-2 rounded-xl px-4 py-3 text-left font-mono text-[14px] font-medium text-white/85 transition-all hover:bg-white/10"
              onClick={requestLogout}
              type="button"
            >
              <span className="material-symbols-outlined text-[18px]">logout</span>
              Выйти
            </button>
          </div>
        </div>
      ) : null}
      <ConfirmDialog
        confirmLabel="Уйти со страницы"
        cancelLabel="Остаться"
        description="Генерация задания ещё идёт. Если уйти сейчас, результат будет потерян."
        onCancel={() => setLeaveTarget(null)}
        onConfirm={() => {
          const target = leaveTarget
          setLeaveTarget(null)
          if (target !== null) navigate(target)
        }}
        open={leaveTarget !== null}
        title="Генерация ещё идёт"
        tone="danger"
      />
      <ConfirmDialog
        confirmLabel="Выйти"
        onCancel={() => setLogoutConfirmOpen(false)}
        onConfirm={handleLogout}
        open={logoutConfirmOpen}
        title="Выйти из аккаунта?"
        tone="danger"
      />
    </header>
  )
}

