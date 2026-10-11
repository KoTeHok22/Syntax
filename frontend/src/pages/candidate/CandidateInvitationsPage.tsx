import { useCallback, useEffect, useState } from 'react'
import { ApiError } from '../../api/client'
import { acceptInvitation, fetchIncomingInvitations, rejectInvitation, viewInvitation } from '../../api/platform'
import type { Invitation } from '../../api/platform'
import { fetchCandidateProfile } from '../../api/auth'
import type { CandidateProfile } from '../../api/auth'
import { fetchTestSessions } from '../../api/testing'
import type { TestSession } from '../../api/testing'
import { statusPill } from '../../lib/statusPill'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { InvitationTimeline } from '../../components/InvitationTimeline'
import { ContactReveal } from '../../components/ContactReveal'

const invitationStatusConfig: Record<Invitation['status'], { label: string; pill: string; icon: string }> = {
  sent: { label: 'Новое', pill: statusPill('info'), icon: 'fiber_new' },
  viewed: { label: 'Просмотрено', pill: statusPill('info'), icon: 'visibility' },
  accepted: { label: 'Принято', pill: statusPill('success'), icon: 'check_circle' },
  rejected: { label: 'Отклонено', pill: statusPill('neutral'), icon: 'cancel' },
  withdrawn: { label: 'Отозвано', pill: statusPill('neutral'), icon: 'undo' },
}

function formatSalary(from: number, to: number): string {
  return `${from.toLocaleString('ru-RU')} – ${to.toLocaleString('ru-RU')} ₽`
}

type Tab = 'all' | 'new' | 'archive'

export function CandidateInvitationsPage() {
  const [invitations, setInvitations] = useState<Invitation[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionErrors, setActionErrors] = useState<Record<number, string>>({})
  const [busyIds, setBusyIds] = useState<number[]>([])
  const [profile, setProfile] = useState<CandidateProfile | null>(null)
  const [sessions, setSessions] = useState<TestSession[]>([])
  const [tab, setTab] = useState<Tab>('all')
  const [rejectingInvitation, setRejectingInvitation] = useState<Invitation | null>(null)

  const markViewed = useCallback(async (list: Invitation[]) => {
    for (const item of list) {
      if (item.status !== 'sent') continue
      try {
        const updated = await viewInvitation(item.id)
        setInvitations((previous) => previous.map((candidate) => (candidate.id === updated.id ? updated : candidate)))
      } catch (exception) {
        if (exception instanceof ApiError) setActionErrors((previous) => ({ ...previous, [item.id]: exception.detail }))
      }
    }
  }, [])

  const load = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const list = await fetchIncomingInvitations()
      setInvitations(list)
      setIsLoading(false)
      void markViewed(list)
    } catch (exception) {
      if (exception instanceof ApiError) setError(exception.detail)
      else setError('Не удалось связаться с сервером')
      setIsLoading(false)
    }
  }, [markViewed])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    fetchCandidateProfile().then(setProfile).catch(() => setProfile(null))
    fetchTestSessions().then(setSessions).catch(() => setSessions([]))
  }, [])

  const runAction = async (invitation: Invitation, action: (id: number) => Promise<Invitation>) => {
    setBusyIds((previous) => [...previous, invitation.id])
    setActionErrors((previous) => {
      const next = { ...previous }
      delete next[invitation.id]
      return next
    })
    try {
      const updated = await action(invitation.id)
      setInvitations((previous) => previous.map((item) => (item.id === updated.id ? updated : item)))
    } catch (exception) {
      if (exception instanceof ApiError) setActionErrors((previous) => ({ ...previous, [invitation.id]: exception.detail }))
      else setActionErrors((previous) => ({ ...previous, [invitation.id]: 'Не удалось связаться с сервером' }))
    } finally {
      setBusyIds((previous) => previous.filter((id) => id !== invitation.id))
    }
  }

  const newCount = invitations.filter((item) => item.status === 'sent').length
  const profileScore = profile === null ? null : Math.round(profile.score)

  const visibleInvitations = invitations.filter((item) => {
    if (tab === 'new') return item.status === 'sent' || item.status === 'viewed'
    if (tab === 'archive') return item.status === 'accepted' || item.status === 'rejected' || item.status === 'withdrawn'
    return true
  })

  return (
    <div className="mx-auto flex w-full max-w-[1280px] flex-col gap-6 px-4 py-8 sm:px-6">
      <div className="flex flex-col gap-1">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="font-mono text-display font-extrabold tracking-tight text-ink">Входящие приглашения</h1>
          {newCount > 0 ? <span className="stat-pill bg-pvn-blue text-white">{newCount} новых</span> : null}
        </div>
        <p className="max-w-3xl font-sans text-body text-ink-secondary">
          Предложения от работодателей по подтверждённым навыкам
        </p>
      </div>

      {error !== null ? (
        <div className="flex items-start gap-3 rounded-panel bg-pvn-red/10 px-5 py-4 font-sans text-caption text-pvn-red-ink shadow-raised-sm">
          <span className="material-symbols-outlined shrink-0 text-[18px]">error</span>
          <span>{error}</span>
        </div>
      ) : null}

      <div className="grid grid-cols-1 items-start gap-6 xl:grid-cols-12">
        <section className="flex flex-col gap-4 xl:col-span-8">
          <div className="flex w-fit items-center gap-1 rounded-panel bg-raised p-1.5 shadow-raised-sm">
            {(
              [
                { value: 'all', label: 'Все' },
                { value: 'new', label: 'Новые' },
                { value: 'archive', label: 'Архив' },
              ] as { value: Tab; label: string }[]
            ).map((item) => (
              <button
                className={
                  tab === item.value
                    ? 'rounded-xl bg-pvn-blue px-5 py-2 font-mono text-[12px] font-bold text-white shadow-blue'
                    : 'rounded-xl px-5 py-2 font-mono text-[12px] font-medium text-ink-secondary transition-all hover:text-ink'
                }
                key={item.value}
                onClick={() => setTab(item.value)}
                type="button"
              >
                {item.label}
              </button>
            ))}
          </div>

          {isLoading ? (
            <div className="flex flex-col gap-4">
              {[0, 1, 2].map((index) => (
                <div className="flex animate-pulse flex-col gap-3 rounded-panel bg-raised p-6 shadow-raised" key={index}>
                  <div className="h-6 w-2/5 rounded-lg bg-inset" />
                  <div className="h-4 w-full rounded-lg bg-inset" />
                  <div className="h-8 w-1/2 rounded-lg bg-inset" />
                </div>
              ))}
            </div>
          ) : visibleInvitations.length === 0 ? (
            <div className="flex flex-col items-center gap-3 rounded-panel bg-raised p-12 text-center text-ink-secondary shadow-raised">
              <span className="material-symbols-outlined text-[48px] text-ink-muted">mark_email_unread</span>
              <span className="font-mono text-h2 font-semibold text-ink">Приглашений пока нет</span>
              <span className="max-w-md font-sans text-body">
                Подтвердите грейд и заполните профиль — работодатели найдут вас по анонимной карточке.
              </span>
            </div>
          ) : (
            <div className="flex flex-col gap-4">
              {visibleInvitations.map((invitation) => {
                const statusConfig = invitationStatusConfig[invitation.status]
                const isBusy = busyIds.includes(invitation.id)
                const actionError = actionErrors[invitation.id]
                const isPending = invitation.status === 'sent' || invitation.status === 'viewed'
                return (
                  <div className="flex flex-col gap-4 rounded-panel bg-raised p-6 shadow-raised" key={invitation.id}>
                    <div className="flex items-start gap-4">
                      <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-pvn-blue/10">
                        <span className="material-symbols-outlined text-[24px] text-pvn-blue">business</span>
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <h2 className="font-sans text-[17px] font-bold text-ink">{invitation.company_name ?? 'Компания скрыта'}</h2>
                          <span className={`stat-pill ${statusConfig.pill}`}>
                            <span className="material-symbols-outlined text-[13px]">{statusConfig.icon}</span>
                            {statusConfig.label}
                          </span>
                        </div>
                        {invitation.message !== null ? (
                          <p className="mt-1.5 font-sans text-caption leading-relaxed text-ink-secondary line-clamp-2">{invitation.message}</p>
                        ) : null}
                      </div>
                      <div className="flex shrink-0 flex-col items-end">
                        <span className="font-mono text-[18px] font-extrabold text-pvn-blue">{formatSalary(invitation.salary_from, invitation.salary_to)}</span>
                      </div>
                    </div>

                    <InvitationTimeline invitation={invitation} />

                    {invitation.status === 'accepted' && invitation.candidate_contacts !== null ? (
                      <ContactReveal companyName={invitation.company_name} contacts={invitation.candidate_contacts} />
                    ) : null}

                    {actionError !== undefined ? (
                      <div className="flex items-start gap-2 rounded-xl bg-pvn-red/10 p-3 font-sans text-caption text-pvn-red-ink">
                        <span className="material-symbols-outlined shrink-0 text-[16px]">error</span>
                        <span>{actionError}</span>
                      </div>
                    ) : null}

                    {isPending ? (
                      <div className="flex flex-col items-stretch gap-3 border-t border-ink/10 pt-4 sm:flex-row sm:items-center">
                        <button
                          className="btn-primary flex-1 py-3 text-[14px]"
                          disabled={isBusy}
                          onClick={() => void runAction(invitation, acceptInvitation)}
                          type="button"
                        >
                          <span className="material-symbols-outlined text-[18px]">check</span>
                          {isBusy ? 'Обработка…' : 'Принять приглашение'}
                        </button>
                        <button
                          className="btn-ghost flex-1 py-3 text-[14px]"
                          disabled={isBusy}
                          onClick={() => setRejectingInvitation(invitation)}
                          type="button"
                        >
                          Отклонить
                        </button>
                      </div>
                    ) : null}
                  </div>
                )
              })}
            </div>
          )}
        </section>

        <aside className="flex flex-col gap-5 xl:col-span-4">
          <div className="flex flex-col gap-4 rounded-panel bg-raised p-6 shadow-raised">
            <span className="font-mono text-h2 font-bold text-ink">Ваш профиль</span>
            <div>
              <div className="font-mono text-[56px] font-extrabold leading-none tracking-tight text-pvn-blue">
                {profileScore === null ? '—' : `${profileScore}%`}
              </div>
              <span className="font-mono text-[13px] text-ink-secondary">балл профиля: тесты, достижения ПВН и полнота</span>
            </div>
            <div className="h-3 w-full overflow-hidden rounded-full bg-sunken shadow-inset-sm">
              <div className="h-full rounded-full bg-pvn-blue" style={{ width: `${profileScore ?? 0}%` }} />
            </div>
            <div className="flex flex-col gap-3 border-t border-ink/10 pt-4">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 font-sans text-caption text-ink-secondary">
                  <span className="material-symbols-outlined text-[18px] text-ink-muted">workspace_premium</span>
                  Навыков в профиле
                </span>
                <span className="font-mono text-[15px] font-bold text-ink">{profile?.stack.length ?? 0}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 font-sans text-caption text-ink-secondary">
                  <span className="material-symbols-outlined text-[18px] text-ink-muted">fact_check</span>
                  Пройдено тестов
                </span>
                <span className="font-mono text-[15px] font-bold text-ink">{sessions.filter((item) => item.status === 'completed').length}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 font-sans text-caption text-ink-secondary">
                  <span className="material-symbols-outlined text-[18px] text-ink-muted">mail</span>
                  Приглашений всего
                </span>
                <span className="font-mono text-[15px] font-bold text-ink">{invitations.length}</span>
              </div>
            </div>
          </div>
        </aside>
      </div>

      <ConfirmDialog
        confirmLabel="Отклонить приглашение"
        description="Приглашение перейдёт в архив, и принять его будет уже нельзя."
        onCancel={() => setRejectingInvitation(null)}
        onConfirm={() => {
          const target = rejectingInvitation
          setRejectingInvitation(null)
          if (target !== null) void runAction(target, rejectInvitation)
        }}
        open={rejectingInvitation !== null}
        title="Отклонить приглашение?"
        tone="danger"
      />
    </div>
  )
}
