import { useCallback, useEffect, useMemo, useState } from 'react'
import { ApiError } from '../../api/client'
import {
  fetchSentInvitations,
  anonymousCandidateId,
  updateInvitation,
  withdrawInvitation,
} from '../../api/platform'
import type { Invitation, UpdateInvitationPayload } from '../../api/platform'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { Modal } from '../../components/Modal'
import { InvitationTimeline } from '../../components/InvitationTimeline'
import { ContactReveal } from '../../components/ContactReveal'
import { gradeLabel, specializationLabel } from '../../lib/format'
import { statusPill } from '../../lib/statusPill'

type StatusTab = 'all' | Invitation['status']

const STATUS_PILLS: Record<Invitation['status'], { label: string; className: string }> = {
  sent: { label: 'Отправлено', className: statusPill('info') },
  viewed: { label: 'Просмотрено', className: statusPill('info') },
  accepted: { label: 'Принято', className: statusPill('success') },
  rejected: { label: 'Отклонено', className: statusPill('neutral') },
  withdrawn: { label: 'Отозвано', className: statusPill('neutral') },
}

interface EditFormState {
  message: string
  salaryFrom: string
  salaryTo: string
  companyName: string
  contactMethod: string
}

function formatSalary(from: number, to: number): string {
  return `${from.toLocaleString('ru-RU')} – ${to.toLocaleString('ru-RU')} ₽`
}

function SkeletonInvitation() {
  return (
    <div className="flex w-full animate-pulse flex-col gap-4 rounded-panel bg-raised p-6 shadow-raised">
      <div className="h-5 w-48 rounded-lg bg-inset" />
      <div className="h-5 w-64 rounded-lg bg-inset" />
      <div className="h-16 rounded-xl bg-inset" />
    </div>
  )
}

export function EmployerInvitationsPage() {
  const [invitations, setInvitations] = useState<Invitation[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [listError, setListError] = useState<string | null>(null)
  const [tab, setTab] = useState<StatusTab>('all')
  const [editing, setEditing] = useState<Invitation | null>(null)
  const [editForm, setEditForm] = useState<EditFormState>({ message: '', salaryFrom: '', salaryTo: '', companyName: '', contactMethod: '' })
  const [editError, setEditError] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [withdrawing, setWithdrawing] = useState<Invitation | null>(null)
  const [isWithdrawing, setIsWithdrawing] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  const replaceInvitation = useCallback((updated: Invitation) => {
    setInvitations((previous) => previous.map((item) => (item.id === updated.id ? updated : item)))
  }, [])

  const openEdit = (invitation: Invitation) => {
    setEditing(invitation)
    setEditError(null)
    setEditForm({
      message: invitation.message ?? '',
      salaryFrom: String(invitation.salary_from),
      salaryTo: String(invitation.salary_to),
      companyName: invitation.company_name ?? '',
      contactMethod: invitation.contact_method ?? '',
    })
  }

  const submitEdit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (editing === null) return
    const salaryFrom = Number(editForm.salaryFrom)
    const salaryTo = Number(editForm.salaryTo)
    if (editForm.message.trim().length === 0 || editForm.companyName.trim().length === 0 || editForm.contactMethod.trim().length === 0) {
      setEditError('Заполните все поля приглашения')
      return
    }
    if (!Number.isInteger(salaryFrom) || !Number.isInteger(salaryTo) || salaryFrom < 0 || salaryTo < salaryFrom) {
      setEditError('Проверьте вилку зарплаты: нижняя граница не больше верхней')
      return
    }
    const payload: UpdateInvitationPayload = {
      message: editForm.message.trim(),
      salary_from: salaryFrom,
      salary_to: salaryTo,
      company_name: editForm.companyName.trim(),
      contact_method: editForm.contactMethod.trim(),
    }
    setIsSaving(true)
    setEditError(null)
    try {
      const updated = await updateInvitation(editing.id, payload)
      replaceInvitation(updated)
      setEditing(null)
    } catch (exception) {
      if (exception instanceof ApiError) setEditError(exception.detail)
      else setEditError('Не удалось сохранить изменения')
    } finally {
      setIsSaving(false)
    }
  }

  const confirmWithdraw = async () => {
    if (withdrawing === null) return
    setIsWithdrawing(true)
    setActionError(null)
    try {
      const updated = await withdrawInvitation(withdrawing.id)
      replaceInvitation(updated)
      setWithdrawing(null)
    } catch (exception) {
      if (exception instanceof ApiError) setActionError(exception.detail)
      else setActionError('Не удалось отозвать приглашение')
      setWithdrawing(null)
    } finally {
      setIsWithdrawing(false)
    }
  }

  const loadInvitations = useCallback(async () => {
    setIsLoading(true)
    setListError(null)
    try {
      const loaded = await fetchSentInvitations()
      setInvitations(loaded)
    } catch (exception) {
      if (exception instanceof ApiError) setListError(exception.detail)
      else setListError('Не удалось загрузить приглашения')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadInvitations()
  }, [loadInvitations])

  const statusCount = useCallback(
    (status: Invitation['status']) => invitations.filter((invitation) => invitation.status === status).length,
    [invitations],
  )

  const visibleInvitations = useMemo(() => {
    if (tab === 'all') return invitations
    return invitations.filter((invitation) => invitation.status === tab)
  }, [invitations, tab])

  return (
    <div className="mx-auto flex w-full max-w-[1280px] flex-col gap-6 px-4 py-8 sm:px-6">
      <div className="flex flex-col gap-1">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="font-mono text-display font-extrabold tracking-tight text-ink">Приглашения</h1>
          {!isLoading ? (
            <span className="stat-pill bg-pvn-blue/10 text-pvn-blue">{invitations.length}</span>
          ) : null}
        </div>
        <p className="max-w-3xl font-sans text-body text-ink-secondary">
          Контакты кандидатов раскрываются только после принятия приглашения.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-1 rounded-panel bg-raised p-2 shadow-raised-sm">
        {(
          [
            { value: 'all', label: 'Все', count: invitations.length },
            { value: 'sent', label: 'Отправленные', count: statusCount('sent') },
            { value: 'viewed', label: 'Просмотренные', count: statusCount('viewed') },
            { value: 'accepted', label: 'Принятые', count: statusCount('accepted') },
            { value: 'rejected', label: 'Отклонённые', count: statusCount('rejected') },
            { value: 'withdrawn', label: 'Отозванные', count: statusCount('withdrawn') },
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
          <button className="ml-auto font-mono font-semibold underline" onClick={() => void loadInvitations()} type="button">
            Повторить
          </button>
        </div>
      ) : null}

      {actionError !== null ? (
        <div className="flex items-center gap-3 rounded-panel bg-pvn-red/10 px-5 py-4 font-sans text-caption text-pvn-red-ink shadow-raised-sm">
          <span className="material-symbols-outlined text-[18px]">error</span>
          <span>{actionError}</span>
        </div>
      ) : null}

      {isLoading ? (
        <div className="flex flex-col gap-4">
          <SkeletonInvitation />
          <SkeletonInvitation />
          <SkeletonInvitation />
        </div>
      ) : visibleInvitations.length === 0 ? (
        <div className="flex flex-col items-center gap-3 rounded-panel bg-raised p-12 text-center shadow-raised">
          <span className="material-symbols-outlined text-[40px] text-ink-muted">forward_to_inbox</span>
          <span className="font-mono text-h2 font-bold text-ink">Ничего не найдено</span>
          <span className="max-w-md font-sans text-caption text-ink-secondary">
            {invitations.length === 0
              ? 'Вы ещё не отправляли приглашения кандидатам'
              : 'В этом статусе нет ни одного приглашения'}
          </span>
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {visibleInvitations.map((invitation) => {
            const contacts =
              invitation.status === 'accepted' && invitation.candidate_contacts !== null
                ? Object.entries(invitation.candidate_contacts)
                : []
            return (
              <article className="flex w-full flex-col gap-4 rounded-panel bg-raised p-6 shadow-raised" key={invitation.id}>
                <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
                  <div className="flex flex-col gap-2">
                    <div className="flex flex-wrap items-center gap-2.5">
                      <span className="font-sans text-h3 font-bold text-ink">
                        {invitation.company_name ?? 'Приглашение'}
                      </span>
                      <span className={`stat-pill ${STATUS_PILLS[invitation.status].className}`}>
                        {STATUS_PILLS[invitation.status].label}
                      </span>
                      <span className="font-mono text-[12px] text-ink-secondary">
                        Кандидат {anonymousCandidateId(invitation.candidate_profile_id)}
                      </span>
                    </div>
                    {invitation.candidate_grade !== null || invitation.candidate_specialization !== null ? (
                      <div className="flex flex-wrap items-center gap-1.5">
                        {invitation.candidate_specialization !== null ? (
                          <span className="chip">{specializationLabel(invitation.candidate_specialization)}</span>
                        ) : null}
                        {invitation.candidate_grade !== null ? (
                          <span className="chip">{gradeLabel(invitation.candidate_grade)}</span>
                        ) : null}
                        {invitation.candidate_stack.slice(0, 4).map((item) => (
                          <span className="chip-blue" key={item}>{item}</span>
                        ))}
                      </div>
                    ) : null}
                    <span className="font-mono text-[20px] font-extrabold tracking-tight text-pvn-blue">
                      {formatSalary(invitation.salary_from, invitation.salary_to)}
                    </span>
                  </div>
                </div>
                {invitation.message !== null && invitation.message.length > 0 ? (
                  <div className="flex items-start gap-3 rounded-xl bg-inset p-4 text-ink shadow-inset-sm">
                    <span className="material-symbols-outlined mt-0.5 shrink-0 text-[20px] text-pvn-blue">chat</span>
                    <div className="font-sans text-body">{invitation.message}</div>
                  </div>
                ) : null}
                <InvitationTimeline invitation={invitation} />
                {contacts.length > 0 ? (
                  <ContactReveal companyName={invitation.company_name} contacts={Object.fromEntries(contacts)} />
                ) : invitation.status !== 'rejected' && invitation.status !== 'withdrawn' ? (
                  <div className="flex items-center gap-2 rounded-xl bg-inset p-4 text-ink-secondary shadow-inset-sm">
                    <span className="material-symbols-outlined text-[18px] text-ink-muted">lock</span>
                    <span className="font-mono text-[13px]">Контакты скрыты до принятия</span>
                  </div>
                ) : null}
                {invitation.status === 'sent' || invitation.status === 'viewed' ? (
                  <div className="flex flex-wrap items-center gap-2 border-t border-ink/10 pt-4">
                    {invitation.status === 'sent' ? (
                      <button className="btn-ghost py-2 text-[13px]" onClick={() => openEdit(invitation)} type="button">
                        <span className="material-symbols-outlined text-[18px]">edit</span>
                        Изменить
                      </button>
                    ) : null}
                    <button className="btn-ghost py-2 text-[13px] text-pvn-red-ink" onClick={() => setWithdrawing(invitation)} type="button">
                      <span className="material-symbols-outlined text-[18px]">undo</span>
                      Отозвать
                    </button>
                  </div>
                ) : null}
              </article>
            )
          })}
        </div>
      )}

      <Modal labelledBy="edit-invitation-title" onClose={() => setEditing(null)} open={editing !== null} panelClassName="relative my-auto w-full max-w-xl rounded-panel bg-raised p-6 shadow-raised-lg">
        <form className="flex flex-col gap-5" noValidate onSubmit={(event) => void submitEdit(event)}>
          <h2 className="font-mono text-h2 font-bold text-ink" id="edit-invitation-title">Изменить приглашение</h2>
          <label className="flex flex-col gap-1.5">
            <span className="label-cap">Сообщение кандидату</span>
            <textarea
              className="field min-h-[96px]"
              maxLength={4000}
              onChange={(event) => setEditForm((previous) => ({ ...previous, message: event.target.value }))}
              value={editForm.message}
            />
          </label>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <label className="flex flex-col gap-1.5">
              <span className="label-cap">Зарплата от, ₽</span>
              <input className="field" inputMode="numeric" onChange={(event) => setEditForm((previous) => ({ ...previous, salaryFrom: event.target.value }))} value={editForm.salaryFrom} />
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="label-cap">Зарплата до, ₽</span>
              <input className="field" inputMode="numeric" onChange={(event) => setEditForm((previous) => ({ ...previous, salaryTo: event.target.value }))} value={editForm.salaryTo} />
            </label>
          </div>
          <label className="flex flex-col gap-1.5">
            <span className="label-cap">Название компании</span>
            <input className="field" onChange={(event) => setEditForm((previous) => ({ ...previous, companyName: event.target.value }))} value={editForm.companyName} />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="label-cap">Контакт для кандидата</span>
            <input className="field" onChange={(event) => setEditForm((previous) => ({ ...previous, contactMethod: event.target.value }))} value={editForm.contactMethod} />
          </label>
          {editError !== null ? (
            <div className="flex items-center gap-2 rounded-xl bg-pvn-red/10 px-4 py-3 font-sans text-caption text-pvn-red-ink">
              <span className="material-symbols-outlined text-[18px]">error</span>
              <span>{editError}</span>
            </div>
          ) : null}
          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
            <button className="btn-ghost" onClick={() => setEditing(null)} type="button">Отмена</button>
            <button className="btn-primary" disabled={isSaving} type="submit">{isSaving ? 'Сохраняем...' : 'Сохранить'}</button>
          </div>
        </form>
      </Modal>

      <ConfirmDialog
        confirmLabel="Отозвать"
        busy={isWithdrawing}
        description="Кандидат больше не сможет принять это приглашение."
        onCancel={() => setWithdrawing(null)}
        onConfirm={() => void confirmWithdraw()}
        open={withdrawing !== null}
        title="Отозвать приглашение?"
        tone="danger"
      />
    </div>
  )
}
