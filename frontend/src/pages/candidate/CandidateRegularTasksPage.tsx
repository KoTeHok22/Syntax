import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ApiError } from '../../api/client'
import {
  startRegularTaskSession,
  submitRegularTaskAnswers,
} from '../../api/platform'
import type { RegularTaskSession, RegularTaskSessionResult } from '../../api/platform'
import { CandidateVacancyPicker } from '../../components/CandidateVacancyPicker'
import { Modal } from '../../components/Modal'
import { TaskStatement } from '../../components/TaskStatement'

const OPTION_LETTERS = ['А', 'Б', 'В', 'Г', 'Д', 'Е', 'Ж', 'З']

function SkeletonTask() {
  return (
    <div className="flex w-full animate-pulse flex-col gap-4 rounded-panel bg-raised p-6 shadow-raised">
      <div className="h-5 w-64 rounded-lg bg-inset" />
      <div className="h-12 rounded-xl bg-inset" />
      <div className="h-12 rounded-xl bg-inset" />
      <div className="h-10 w-40 rounded-xl bg-inset" />
    </div>
  )
}

export function CandidateRegularTasksPage() {
  const [searchParams] = useSearchParams()
  const vacancyParam = searchParams.get('vacancy') ?? ''
  const vacancyId = Number(vacancyParam)
  const hasVacancy = vacancyParam !== '' && Number.isInteger(vacancyId) && vacancyId > 0
  const [session, setSession] = useState<RegularTaskSession | null>(null)
  const [result, setResult] = useState<RegularTaskSessionResult | null>(null)
  const [taskIndex, setTaskIndex] = useState(0)
  const [answers, setAnswers] = useState<Record<number, number>>({})
  const [isBusy, setIsBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [remainingSeconds, setRemainingSeconds] = useState<number | null>(null)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [confirmingFinish, setConfirmingFinish] = useState(false)
  const submittingRef = useRef(false)

  const beginSession = (next: RegularTaskSession) => {
    setSession(next)
    setAnswers({})
    setTaskIndex(0)
    setError(null)
    void document.documentElement.requestFullscreen?.().catch(() => undefined)
  }

  useEffect(() => {
    submittingRef.current = false
    setSession(null)
    setResult(null)
    setAnswers({})
    setTaskIndex(0)
    setError(null)
    setConfirmingFinish(false)
  }, [vacancyId])

  const start = useCallback(async () => {
    if (!hasVacancy) return
    setError(null)
    setIsBusy(true)
    try {
      beginSession(await startRegularTaskSession(vacancyId))
    } catch (exception) {
      if (exception instanceof ApiError) setError(exception.detail)
      else setError('Не удалось начать задания')
    } finally {
      setIsBusy(false)
    }
  }, [hasVacancy, vacancyId])

  const tasks = session?.tasks ?? []
  const task = tasks[taskIndex]
  const totalTasks = tasks.length

  const submitSession = useCallback(
    async (allowPartial: boolean) => {
      if (session === null || submittingRef.current) return
      const answeredCount = session.tasks.filter((item) => answers[item.id] !== undefined).length
      if (!allowPartial && answeredCount < session.tasks.length) {
        setError('Ответьте на все задания перед завершением')
        return
      }
      submittingRef.current = true
      setError(null)
      setIsBusy(true)
      try {
        if (document.fullscreenElement) await document.exitFullscreen().catch(() => undefined)
        const payload = session.tasks
          .filter((item) => answers[item.id] !== undefined)
          .map((item) => ({ regular_task_id: item.id, option_index: answers[item.id] }))
        setResult(await submitRegularTaskAnswers(session.id, payload))
      } catch (exception) {
        submittingRef.current = false
        if (exception instanceof ApiError) setError(exception.detail)
        else setError('Не удалось отправить ответы')
      } finally {
        setIsBusy(false)
      }
    },
    [session, answers],
  )

  useEffect(() => {
    if (session === null || session.expires_at === null) {
      setRemainingSeconds(null)
      return
    }
    const deadline = new Date(session.expires_at).getTime()
    const tick = () => {
      const left = Math.max(0, Math.round((deadline - Date.now()) / 1000))
      setRemainingSeconds(left)
      if (left <= 0) void submitSession(true)
    }
    tick()
    const handle = window.setInterval(tick, 1000)
    return () => window.clearInterval(handle)
  }, [session, submitSession])

  useEffect(() => {
    if (session === null || result !== null) {
      if (document.fullscreenElement) void document.exitFullscreen().catch(() => undefined)
      return
    }
    const prevent = (event: Event) => event.preventDefault()
    document.addEventListener('copy', prevent)
    document.addEventListener('cut', prevent)
    document.addEventListener('paste', prevent)
    document.addEventListener('contextmenu', prevent)
    const onFullscreenChange = () => {
      const active = document.fullscreenElement !== null
      setIsFullscreen(active)
      if (!active && !submittingRef.current) void submitSession(true)
    }
    const onVisibility = () => {
      if (document.hidden && !submittingRef.current) void submitSession(true)
    }
    const onBlur = () => {
      if (!submittingRef.current) void submitSession(true)
    }
    document.addEventListener('fullscreenchange', onFullscreenChange)
    document.addEventListener('visibilitychange', onVisibility)
    window.addEventListener('blur', onBlur)
    return () => {
      document.removeEventListener('copy', prevent)
      document.removeEventListener('cut', prevent)
      document.removeEventListener('paste', prevent)
      document.removeEventListener('contextmenu', prevent)
      document.removeEventListener('fullscreenchange', onFullscreenChange)
      document.removeEventListener('visibilitychange', onVisibility)
      window.removeEventListener('blur', onBlur)
    }
  }, [session, result, submitSession])

  const enterFullscreen = () => {
    void document.documentElement.requestFullscreen?.().catch(() => undefined)
  }

  const answeredCount = tasks.filter((item) => answers[item.id] !== undefined).length

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-8 sm:px-6">
      <div className="flex flex-col gap-1">
        <h1 className="font-mono text-display font-extrabold tracking-tight text-ink">Задания к вакансии</h1>
        <p className="max-w-3xl font-sans text-body text-ink-secondary">
          Проверочные задания работодателя. Ответы видны ему в вашем отклике.
        </p>
      </div>

      <CandidateVacancyPicker activeVacancyId={hasVacancy ? vacancyId : null} />

      {error !== null ? (
        <div className="flex items-start gap-3 rounded-panel bg-pvn-red/10 px-5 py-4 font-sans text-caption text-pvn-red-ink shadow-raised-sm">
          <span className="material-symbols-outlined shrink-0 text-[18px]">error</span>
          <span>{error}</span>
        </div>
      ) : null}

      {!hasVacancy ? null : result !== null ? (
        <div className="flex flex-col gap-4 rounded-panel bg-raised p-6 shadow-raised">
          <div className="flex items-center gap-3">
            <span className={result.forced_finish ? 'flex h-11 w-11 items-center justify-center rounded-xl bg-warn/15' : 'flex h-11 w-11 items-center justify-center rounded-xl bg-good/15'}>
              <span className={`material-symbols-outlined text-[22px] ${result.forced_finish ? 'text-warn-ink' : 'text-good-ink'}`}>
                {result.forced_finish ? 'timer_off' : 'task_alt'}
              </span>
            </span>
            <div className="flex flex-col">
              <span className="font-mono text-h3 font-bold text-ink">
                {result.correct_count} из {result.task_count} верно
              </span>
              <span className="font-sans text-caption text-ink-secondary">
                {result.forced_finish
                  ? 'Попытка завершена досрочно: выход из полноэкранного режима или переключение окна.'
                  : 'Результат отправлен работодателю в отклике.'}
              </span>
            </div>
            <span className="ml-auto font-mono text-h2 font-extrabold text-pvn-blue">{result.result_score} / 100</span>
          </div>
          <p className="font-sans text-caption text-ink-secondary">
            Повторно пройти задания по этой вакансии нельзя. Правильные ответы работодатель не раскрывает, чтобы задания оставались действующими для других кандидатов.
          </p>
          <div className="flex items-center gap-3">
            <Link className="btn-primary" to="/candidate/applications">К моим откликам</Link>
          </div>
        </div>
      ) : session === null ? (
        <div className="flex flex-col items-start gap-4 rounded-panel bg-raised p-6 shadow-raised">
          <div className="flex flex-col gap-2">
            <span className="font-mono text-h2 font-bold text-ink">Готовы приступить?</span>
            <span className="font-sans text-caption text-ink-secondary">
              Задания открываются в полноэкранном режиме. Тест нельзя поставить на паузу, копирование и вставка отключены. Выход из полноэкранного режима, переход в другую вкладку или приложение завершают попытку: отвеченные задания зачтутся, остальные — как неверные.
            </span>
          </div>
          <button className="btn-primary" disabled={isBusy} onClick={() => void start()} type="button">
            {isBusy ? 'Загрузка…' : 'Начать задания'}
          </button>
        </div>
      ) : task === undefined ? (
        <SkeletonTask />
      ) : (
        <div className="flex flex-col gap-5">
          <div className="flex w-full items-center gap-3 rounded-panel bg-raised px-6 py-4 shadow-raised-sm">
            <div className="flex flex-1 items-center gap-1.5">
              {tasks.map((item, index) => (
                <div
                  className={`h-2 flex-1 rounded-full transition-colors ${index === taskIndex ? 'bg-pvn-blue' : answers[item.id] !== undefined ? 'bg-good' : 'bg-sunken shadow-inset-sm'}`}
                  key={item.id}
                />
              ))}
            </div>
            {remainingSeconds !== null ? (
              <span className={`ml-3 shrink-0 rounded-full px-3 py-1 font-mono text-[13px] font-bold ${remainingSeconds <= 60 ? 'bg-pvn-red/10 text-pvn-red-ink' : 'bg-inset text-ink'}`}>
                {String(Math.floor(remainingSeconds / 60)).padStart(2, '0')}:{String(remainingSeconds % 60).padStart(2, '0')}
              </span>
            ) : null}
          </div>

          {!isFullscreen ? (
            <div className="flex flex-wrap items-center gap-3 rounded-panel bg-warn/15 px-5 py-4 font-sans text-caption text-warn-ink shadow-raised-sm">
              <span className="material-symbols-outlined text-[18px]">fullscreen</span>
              <span>Полноэкранный режим обязателен. Пока он не включён, попытка завершится как досрочная.</span>
              <button className="btn-ghost ml-auto py-1.5 text-[13px]" onClick={enterFullscreen} type="button">Включить</button>
            </div>
          ) : null}

          <div className="flex w-full flex-col gap-5 rounded-panel bg-raised p-6 shadow-raised">
            <div className="flex flex-wrap items-center gap-3">
              <span className="stat-pill bg-inset text-ink-secondary">
                Задание {taskIndex + 1} из {totalTasks}
              </span>
              <span className="stat-pill bg-inset text-ink-secondary">отвечено: {answeredCount}</span>
            </div>
            <div className="rounded-2xl bg-inset p-5 shadow-inset-sm">
              <TaskStatement statement={task.statement} />
            </div>
            <div className="flex flex-col gap-2.5">
              {task.options.map((option, index) => {
                const isSelected = answers[task.id] === index
                return (
                  <button
                    className={
                      isSelected
                        ? 'flex w-full items-center gap-3 rounded-xl bg-pvn-blue px-4 py-3 text-left font-sans text-[15px] text-white shadow-blue transition-all'
                        : 'flex w-full items-center gap-3 rounded-xl bg-inset px-4 py-3 text-left font-sans text-[15px] text-ink shadow-inset-sm transition-all hover:bg-raised hover:shadow-raised-sm'
                    }
                    key={index}
                    onClick={() => setAnswers((previous) => ({ ...previous, [task.id]: index }))}
                    type="button"
                  >
                    <span
                      className={
                        isSelected
                          ? 'flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-white/25 font-mono text-[13px] font-bold text-white'
                          : 'flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-raised font-mono text-[13px] font-semibold text-ink-secondary shadow-raised-sm'
                      }
                    >
                      {OPTION_LETTERS[index] ?? index + 1}
                    </span>
                    <span className="min-w-0 break-words">{option}</span>
                  </button>
                )
              })}
            </div>
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-ink/10 pt-4">
              <button
                className="btn-ghost"
                disabled={taskIndex === 0}
                onClick={() => setTaskIndex((previous) => Math.max(0, previous - 1))}
                type="button"
              >
                Назад
              </button>
              {taskIndex < totalTasks - 1 ? (
                <button className="btn-primary" onClick={() => setTaskIndex((previous) => previous + 1)} type="button">
                  Далее
                  <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
                </button>
              ) : (
                <button className="btn-primary" disabled={isBusy} onClick={() => setConfirmingFinish(true)} type="button">
                  {isBusy ? 'Отправка…' : 'Завершить'}
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {confirmingFinish ? (
        <Modal labelledBy="finish-task-title" onClose={() => setConfirmingFinish(false)} open panelClassName="relative w-full max-w-md rounded-panel bg-raised p-6 shadow-raised-lg">
          <div className="flex flex-col gap-4">
            <span className="font-mono text-h3 font-bold text-ink" id="finish-task-title">Завершить задания?</span>
            <p className="font-sans text-body text-ink-secondary">
              Отвечено {answeredCount} из {totalTasks}. Неотвеченные задания засчитываются как неверные, повторная попытка недоступна.
            </p>
            <div className="flex items-center justify-end gap-3">
              <button className="btn-ghost" onClick={() => setConfirmingFinish(false)} type="button">Отмена</button>
              <button
                className="btn-primary"
                disabled={isBusy}
                onClick={() => {
                  setConfirmingFinish(false)
                  void submitSession(false)
                }}
                type="button"
              >
                {isBusy ? 'Отправка…' : 'Да, завершить'}
              </button>
            </div>
          </div>
        </Modal>
      ) : null}
    </div>
  )
}
