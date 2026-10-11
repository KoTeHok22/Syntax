import { useCallback, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ApiError } from '../../api/client'
import { fetchTestSession, fetchTestSessionReview, fetchTestSessions, startTestSession, submitAnswers } from '../../api/testing'
import type { AnswerPayload, TestSession, TestSessionResult, TestSessionReview } from '../../api/testing'
import { TaskStatement } from '../../components/TaskStatement'
import { ImageAnnotation } from '../../components/ImageAnnotation'
import type { AnnotationRect } from '../../components/ImageAnnotation'
import { Modal } from '../../components/Modal'
import { gradeLabel } from '../../lib/format'

const OPTION_LETTERS = ['А', 'Б', 'В', 'Г', 'Д', 'Е', 'Ж', 'З']

const TASKS_PER_SESSION = 20

const TEST_RULES = [
  'Одна попытка на каждую сессию тестирования — вернуться к уже начатому тесту можно, но начать заново нельзя.',
  'На всё тестирование отводится ограниченное время; по истечении таймера ответы отправляются автоматически.',
  'Тест проходит в полноэкранном режиме: вопросы и ответы скрыты, пока режим не включён.',
  'Выход из полноэкранного режима, переход в другую вкладку или приложение автоматически завершают тест: отвеченные вопросы зачтутся, остальные — как неверные.',
  'Грейд подтверждается только при наборе порога баллов для выбранного грейда.',
  'Подтверждённый грейд действует 12 месяцев, затем требуется пересдача.']

type Screen = 'start' | 'quiz' | 'result'

const gradeOptions = [
  {
    value: 'junior',
    title: 'Junior',
    description: 'Базовые алгоритмы, структуры данных и владение основным стеком разработки.',
    icon: 'eco',
  },
  {
    value: 'middle',
    title: 'Middle',
    description: 'Проектирование модулей, асинхронная обработка, оптимизация и код-ревью.',
    icon: 'bolt',
  },
  {
    value: 'senior',
    title: 'Senior',
    description: 'Архитектура распределённых систем, System Design и надёжность сервисов.',
    icon: 'military_tech',
  },
]

const verdictConfig: Record<string, { label: string; pill: string }> = {
  suggest_higher: { label: 'Грейд подтверждён', pill: 'bg-good/15 text-good-ink' },
  confirmed: { label: 'Грейд подтверждён', pill: 'bg-good/15 text-good-ink' },
  suggest_lower: { label: 'Грейд не подтверждён — балла не хватило', pill: 'bg-warn/15 text-warn-ink' },
}

const sessionStatusConfig: Record<TestSession['status'], { label: string; pill: string }> = {
  active: { label: 'В процессе', pill: 'bg-pvn-blue/10 text-pvn-blue' },
  completed: { label: 'Завершена', pill: 'bg-good/15 text-good-ink' },
}

function sessionStatus(status: TestSession['status']): { label: string; pill: string } {
  return sessionStatusConfig[status] ?? { label: 'В процессе', pill: 'bg-pvn-blue/10 text-pvn-blue' }
}

function verdictInfo(verdict: string | undefined): { label: string; pill: string } {
  if (verdict === undefined) return { label: 'Грейд подтверждён', pill: 'bg-good/15 text-good-ink' }
  return verdictConfig[verdict] ?? { label: verdict, pill: 'bg-sunken text-ink-secondary' }
}

function gradePassThreshold(grade: string): number {
  if (grade === 'senior') return 85
  if (grade === 'middle') return 75
  return 60
}

function scoreTone(score: number, threshold: number): string {
  if (score >= threshold) return 'text-good-ink'
  if (score >= threshold - 10) return 'text-pvn-blue'
  return 'text-pvn-red-ink'
}

export function CandidateTestingPage() {
  const [searchParams] = useSearchParams()
  const [screen, setScreen] = useState<Screen>('start')
  const [session, setSession] = useState<TestSession | null>(null)
  const [result, setResult] = useState<TestSessionResult | null>(null)
  const [resumable, setResumable] = useState<TestSession | null>(null)
  const [history, setHistory] = useState<TestSession[]>([])
  const [historyLoading, setHistoryLoading] = useState(true)
  const [taskIndex, setTaskIndex] = useState(0)
  const [answers, setAnswers] = useState<Record<number, number>>({})
  const [annotations, setAnnotations] = useState<Record<number, AnnotationRect | null>>({})
  const [notes, setNotes] = useState<Record<number, string>>({})
  const [selectedGrade, setSelectedGrade] = useState<string | null>(searchParams.get('grade'))
  const [error, setError] = useState<string | null>(null)
  const [isBusy, setIsBusy] = useState(false)
  const [remainingSeconds, setRemainingSeconds] = useState<number | null>(null)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [rulesGrade, setRulesGrade] = useState<string | null>(null)
  const [rulesAccepted, setRulesAccepted] = useState(false)
  const [review, setReview] = useState<TestSessionReview | null>(null)
  const [reviewLoading, setReviewLoading] = useState(false)
  const submittingRef = useRef(false)

  useEffect(() => {
    const requested = searchParams.get('grade')
    if (requested !== null && gradeOptions.some((option) => option.value === requested)) {
      setSelectedGrade(requested)
    }
  }, [searchParams])

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true)
    try {
      const sessions = await fetchTestSessions()
      setHistory(sessions)
      setResumable(sessions.find((item) => item.status === 'active') ?? null)
    } catch (exception) {
      if (exception instanceof ApiError) setError(exception.detail)
      else setError('Не удалось связаться с сервером')
    } finally {
      setHistoryLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadHistory()
  }, [loadHistory])

  const beginSession = (next: TestSession) => {
    setSession(next)
    setAnswers({})
    setAnnotations({})
    setNotes({})
    setTaskIndex(0)
    setSelectedGrade(null)
    setError(null)
    setScreen('quiz')
    void document.documentElement.requestFullscreen?.().catch(() => undefined)
  }

  const openReview = async (sessionId: number) => {
    setReviewLoading(true)
    setError(null)
    try {
      setReview(await fetchTestSessionReview(sessionId))
    } catch (exception) {
      if (exception instanceof ApiError) setError(exception.detail)
      else setError('Не удалось загрузить разбор сессии')
    } finally {
      setReviewLoading(false)
    }
  }

  const resume = async (target: TestSession) => {
    setError(null)
    setIsBusy(true)
    try {
      const full = await fetchTestSession(target.id)
      beginSession(full)
    } catch (exception) {
      if (exception instanceof ApiError) setError(exception.detail)
      else setError('Не удалось загрузить незавершённую сессию')
    } finally {
      setIsBusy(false)
    }
  }

  const start = async (grade: string) => {
    setError(null)
    setIsBusy(true)
    try {
      const created = await startTestSession(grade)
      beginSession(created)
    } catch (exception) {
      if (exception instanceof ApiError) setError(exception.detail)
      else setError('Не удалось связаться с сервером')
    } finally {
      setIsBusy(false)
    }
  }

  const tasks = session?.tasks ?? []
  const task = tasks[taskIndex]
  const totalTasks = tasks.length
  const isLastTask = taskIndex === totalTasks - 1

  const isAnswered = useCallback(
    (item: TestSession['tasks'][number]) =>
      item.task_format === 'design_annotation'
        ? annotations[item.id] !== null && annotations[item.id] !== undefined && (notes[item.id] ?? '').trim().length > 0
        : answers[item.id] !== undefined,
    [annotations, notes, answers],
  )

  const submitSession = useCallback(
    async (allowPartial: boolean) => {
      if (session === null || submittingRef.current) return
      const answeredCount = session.tasks.filter((item) => isAnswered(item)).length
      if (!allowPartial && answeredCount < session.tasks.length) {
        setError('Ответьте на все вопросы перед завершением теста')
        return
      }
      submittingRef.current = true
      setError(null)
      setIsBusy(true)
      try {
        if (document.fullscreenElement) await document.exitFullscreen().catch(() => undefined)
        const payload: AnswerPayload[] = []
        session.tasks.forEach((item) => {
          if (item.task_format === 'design_annotation') {
            const annotation = annotations[item.id]
            const note = (notes[item.id] ?? '').trim()
            if (annotation !== null && annotation !== undefined && note !== '') {
              payload.push({ task_id: item.id, answer: note, annotation })
            }
            return
          }
          if (answers[item.id] !== undefined) {
            payload.push({ task_id: item.id, option_index: answers[item.id] })
          }
        })
        const submitted = await submitAnswers(session.id, payload)
        setResult(submitted)
        setScreen('result')
        void loadHistory()
      } catch (exception) {
        submittingRef.current = false
        if (exception instanceof ApiError) setError(exception.detail)
        else setError('Не удалось связаться с сервером')
      } finally {
        setIsBusy(false)
      }
    },
    [session, loadHistory, annotations, notes, answers, isAnswered],
  )

  const finish = () => submitSession(false)

  useEffect(() => {
    if (screen !== 'quiz' || session?.expires_at === null || session?.expires_at === undefined) {
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
  }, [screen, session?.expires_at, submitSession])

  useEffect(() => {
    if (screen !== 'quiz') {
      if (document.fullscreenElement) void document.exitFullscreen().catch(() => undefined)
      return
    }
    const prevent = (event: Event) => event.preventDefault()
    const onCopy = (event: Event) => event.preventDefault()
    document.addEventListener('copy', onCopy)
    document.addEventListener('cut', onCopy)
    document.addEventListener('paste', onCopy)
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
      document.removeEventListener('copy', onCopy)
      document.removeEventListener('cut', onCopy)
      document.removeEventListener('paste', onCopy)
      document.removeEventListener('contextmenu', prevent)
      document.removeEventListener('fullscreenchange', onFullscreenChange)
      document.removeEventListener('visibilitychange', onVisibility)
      window.removeEventListener('blur', onBlur)
    }
  }, [screen, submitSession])

  const enterFullscreen = () => {
    const element = document.documentElement
    void element.requestFullscreen?.().catch(() => undefined)
  }

  return (
    <div className="mx-auto flex w-full max-w-[1280px] flex-col gap-6 px-4 py-8 sm:px-6">
      <div className="flex flex-col gap-1">
        <h1 className="font-mono text-display font-extrabold tracking-tight text-ink">
          {screen === 'quiz' && session !== null ? `Тестирование на грейд ${session.grade}` : 'Тестирование и подтверждение грейда'}
        </h1>
        {screen === 'start' ? (
          <p className="max-w-3xl font-sans text-body text-ink-secondary">
            Пройдите тест, чтобы работодатели видели подтверждённый грейд.
          </p>
        ) : null}
      </div>

      {error !== null ? (
        <div className="flex items-start gap-3 rounded-panel bg-pvn-red/10 px-5 py-4 font-sans text-caption text-pvn-red-ink shadow-raised-sm">
          <span className="material-symbols-outlined shrink-0 text-[18px]">error</span>
          <span>{error}</span>
        </div>
      ) : null}

      {screen === 'result' && result !== null ? (
        <div className="flex flex-col items-center gap-0 rounded-panel bg-raised px-6 py-5 shadow-raised sm:flex-row sm:justify-between">
          {[
            { num: 1, label: 'Опрос' },
            { num: 2, label: 'Грейд' },
            { num: 3, label: 'Результат' },
          ].map((step, index) => {
            return (
              <div className="flex flex-1 items-center" key={step.num}>
                <div className="flex items-center gap-3">
                  <span className="flex h-8 w-8 items-center justify-center rounded-full bg-pvn-blue font-mono text-[13px] font-bold text-white shadow-blue">
                    <span className="material-symbols-outlined text-[18px]">check</span>
                  </span>
                  <span className="font-mono text-[13px] font-semibold text-ink">{step.label}</span>
                </div>
                {index < 2 ? <span className="mx-4 h-px flex-1 bg-ink/15" /> : null}
              </div>
            )
          })}
        </div>
      ) : null}

      {screen === 'start' ? (
        <section className="flex flex-col gap-5">
          {resumable !== null ? (
            <div className="flex flex-col justify-between gap-4 rounded-panel bg-raised p-5 shadow-raised md:flex-row md:items-center">
              <div className="flex items-center gap-4">
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-pvn-blue text-white shadow-blue">
                  <span className="material-symbols-outlined text-[22px]">play_arrow</span>
                </span>
                <div className="flex flex-col">
                  <span className="font-mono text-[11px] font-bold uppercase tracking-wider text-ink">Незавершённая сессия</span>
                  <span className="font-sans text-caption text-ink-secondary">Тест на грейд {resumable.grade} · {resumable.task_count} вопросов · прогресс сохранён</span>
                </div>
              </div>
              <button className="btn-primary shrink-0" disabled={isBusy} onClick={() => void resume(resumable)} type="button">
                {isBusy ? 'Загрузка…' : 'Продолжить'}
                <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
              </button>
            </div>
          ) : null}

          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            {gradeOptions.map((option) => {
              const isSelected = selectedGrade === option.value
              return (
                <button
                  className={`flex flex-col gap-3 rounded-panel p-5 text-left transition-all ${
                    isSelected ? 'bg-raised shadow-raised ring-2 ring-pvn-blue' : 'bg-raised shadow-raised-sm hover:shadow-raised'
                  }`}
                  key={option.value}
                  onClick={() => setSelectedGrade(option.value)}
                  type="button"
                >
                  <div className="flex items-center gap-3">
                    <span className={isSelected ? 'flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-pvn-blue' : 'h-5 w-5 shrink-0 rounded-full border-2 border-ink/20'}>
                      {isSelected ? <span className="h-2 w-2 rounded-full bg-white" /> : null}
                    </span>
                    <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-pvn-blue/10">
                      <span className="material-symbols-outlined text-[22px] text-pvn-blue">{option.icon}</span>
                    </span>
                    <span className="font-mono text-h2 font-bold text-ink">{option.title}</span>
                  </div>
                  <span className="font-sans text-caption leading-relaxed text-ink-secondary">{option.description}</span>
                </button>
              )
            })}
          </div>

          <button
            className="btn-primary self-start"
            disabled={selectedGrade === null || isBusy}
            onClick={() => {
              if (selectedGrade !== null) {
                setRulesAccepted(false)
                setRulesGrade(selectedGrade)
              }
            }}
            type="button"
          >
            <span className="material-symbols-outlined text-[18px]">quiz</span>
            {isBusy ? 'Запуск…' : 'Начать тестирование'}
          </button>

          <div className="flex flex-col gap-4 rounded-panel bg-raised p-6 shadow-raised">
            <span className="label-cap">История сессий</span>
            {historyLoading ? (
              <div className="flex flex-col gap-2">
                {[0, 1, 2].map((index) => (<div className="h-12 animate-pulse rounded-xl bg-inset" key={index} />))}
              </div>
            ) : history.length === 0 ? (
              <div className="flex flex-col items-center gap-3 py-8 text-ink-secondary">
                <span className="material-symbols-outlined text-[36px] text-ink-muted">history</span>
                <span className="font-sans text-body">Сессий пока нет — начните первое тестирование</span>
              </div>
            ) : (
              <div className="flex flex-col divide-y divide-ink/10">
                {history.map((item) => {
                  const statusConfig = sessionStatus(item.status)
                  return (
                    <div className="flex items-center justify-between gap-4 py-3 first:pt-0 last:pb-0" key={item.id}>
                      <div className="flex flex-col">
                        <span className="font-mono text-[13px] font-semibold uppercase tracking-wider text-ink">{item.grade}</span>
                        <span className="font-sans text-caption text-ink-secondary">{item.task_count} вопросов</span>
                      </div>
                      <div className="flex items-center gap-4">
                        {typeof item.result_score === 'number' ? (
                          <span className="font-mono text-[15px] font-bold text-pvn-blue">{item.result_score} / 100</span>
                        ) : null}
                        <span className={`stat-pill ${statusConfig.pill}`}>{statusConfig.label}</span>
                        {item.status === 'completed' ? (
                          <button className="btn-ghost py-1.5 text-[13px]" disabled={reviewLoading} onClick={() => void openReview(item.id)} type="button">
                            Посмотреть
                          </button>
                        ) : null}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </section>
      ) : null}

      {screen === 'quiz' && task !== undefined ? (
        <div className="flex flex-col gap-5">
          <div className="flex w-full items-center gap-3 rounded-panel bg-raised px-6 py-4 shadow-raised-sm">
            <div className="flex flex-1 items-center gap-1.5">
              {tasks.map((item, index) => {
                const isCurrent = index === taskIndex
                const answered = isAnswered(item)
                return (
                  <div
                    className={`h-2 flex-1 rounded-full transition-colors ${isCurrent ? 'bg-pvn-blue' : answered ? 'bg-good' : 'bg-sunken shadow-inset-sm'}`}
                    key={index}
                  />
                )
              })}
            </div>
            {remainingSeconds !== null ? (
              <span
                className={`ml-3 shrink-0 rounded-full px-3 py-1 font-mono text-[13px] font-bold ${
                  remainingSeconds <= 60 ? 'bg-pvn-red/10 text-pvn-red-ink' : 'bg-inset text-ink'
                }`}
              >
                {String(Math.floor(remainingSeconds / 60)).padStart(2, '0')}:{String(remainingSeconds % 60).padStart(2, '0')}
              </span>
            ) : null}
            <span className="ml-3 shrink-0 font-mono text-[13px] font-bold text-ink">{taskIndex + 1} / {totalTasks}</span>
          </div>

          {!isFullscreen ? (
            <section className="flex flex-col items-center gap-4 rounded-panel bg-raised p-12 text-center shadow-raised">
              <span className="material-symbols-outlined text-[44px] text-pvn-blue">fullscreen</span>
              <span className="font-mono text-h2 font-bold text-ink">Перейдите в полноэкранный режим</span>
              <span className="max-w-md font-sans text-caption text-ink-secondary">
                Вопросы и ответы скрыты до перехода в полноэкранный режим. Выход из полноэкрана, переход в другую вкладку или приложение автоматически завершают тест.
              </span>
              <button className="btn-primary" onClick={enterFullscreen} type="button">
                <span className="material-symbols-outlined text-[18px]">fullscreen</span>
                Перейти в полноэкранный режим
              </button>
            </section>
          ) : (
            <div className="flex flex-col gap-6 rounded-panel bg-raised p-6 shadow-raised sm:p-8">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-ink/10 pb-4">
              <div className="flex items-center gap-2">
                <span className="font-mono text-[12px] text-ink-muted">ВОПРОС {taskIndex + 1}</span>
                <span className="stat-pill bg-pvn-blue/10 text-pvn-blue">ГРЕЙД {session?.grade.toUpperCase()}</span>
              </div>
            </div>

            <h2 className="font-mono text-[15px] font-bold uppercase tracking-wider text-ink-secondary">Задание</h2>
            <TaskStatement statement={task.statement} />

            {task.task_format === 'design_annotation' && task.image_data_url ? (
              <div className="flex flex-col gap-4">
                <ImageAnnotation
                  onChange={(rect) => setAnnotations((previous) => ({ ...previous, [task.id]: rect }))}
                  src={task.image_data_url}
                  value={annotations[task.id] ?? null}
                />
                <div className="flex flex-col gap-1.5">
                  <label className="label-cap" htmlFor={`annotation-${task.id}`}>Что не так с выделенным элементом?</label>
                  <textarea
                    className="field min-h-[96px] resize-y"
                    id={`annotation-${task.id}`}
                    onChange={(event) => setNotes((previous) => ({ ...previous, [task.id]: event.target.value }))}
                    placeholder="Опишите, что нарушено и почему это мешает пользователю"
                    value={notes[task.id] ?? ''}
                  />
                  <span className="font-sans text-[12px] text-ink-secondary">Ответ проверит ИИ: важны и выделенная область, и пояснение.</span>
                </div>
              </div>
            ) : (
              <div className="flex flex-col gap-3">
                {task.options.map((option, optionIndex) => {
                  const isSelected = answers[task.id] === optionIndex
                  return (
                    <label className="relative flex cursor-pointer items-start" key={optionIndex}>
                      <input
                        checked={isSelected}
                        className="sr-only"
                        name={`answer-${task.id}`}
                        onChange={() => setAnswers((previous) => ({ ...previous, [task.id]: optionIndex }))}
                        type="radio"
                      />
                      <div
                        className={`flex w-full items-start gap-4 rounded-xl p-4 transition-all ${
                          isSelected ? 'bg-inset shadow-inset-sm ring-2 ring-pvn-blue' : 'bg-raised shadow-raised-sm hover:shadow-raised'
                        }`}
                      >
                        <span
                          className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full transition-all ${
                            isSelected ? 'bg-pvn-blue' : 'border-2 border-ink/20'
                          }`}
                        >
                          {isSelected ? <span className="h-2 w-2 rounded-full bg-white" /> : null}
                        </span>
                        <span className="font-sans text-[15px] font-medium text-ink">
                          <span className="font-mono font-bold text-pvn-blue">{OPTION_LETTERS[optionIndex] ?? optionIndex + 1}.</span> {option}
                        </span>
                      </div>
                    </label>
                  )
                })}
              </div>
            )}

            <div className="flex flex-col items-center justify-between gap-4 border-t border-ink/10 pt-5 sm:flex-row">
              <button
                className="btn-ghost w-full sm:w-auto"
                disabled={taskIndex === 0}
                onClick={() => setTaskIndex((previous) => Math.max(0, previous - 1))}
                type="button"
              >
                <span className="material-symbols-outlined text-[18px]">arrow_back</span>
                Назад
              </button>
              <div className="flex w-full items-center justify-end gap-4 sm:w-auto">
                {isLastTask ? (
                  <button className="btn-primary w-full sm:w-auto" disabled={isBusy} onClick={() => void finish()} type="button">
                    {isBusy ? 'Отправка…' : 'Завершить тест'}
                  </button>
                ) : (
                  <button
                    className="btn-primary w-full sm:w-auto"
                    onClick={() => setTaskIndex((previous) => Math.min(totalTasks - 1, previous + 1))}
                    type="button"
                  >
                    Следующий вопрос
                    <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
                  </button>
                )}
              </div>
            </div>
          </div>
          )}
          <span className="font-mono text-[12px] text-ink-muted">Ответ сохранится автоматически · без таймера</span>
        </div>
      ) : null}

      {screen === 'quiz' && task === undefined ? (
        <section className="flex flex-col items-center gap-4 rounded-panel bg-raised p-12 text-center shadow-raised">
          <span className="material-symbols-outlined text-[40px] text-ink-muted">hourglass_empty</span>
          <span className="font-mono text-h2 font-bold text-ink">Вопросы недоступны</span>
          <span className="max-w-md font-sans text-caption text-ink-secondary">
            Не удалось загрузить вопросы сессии. Вернитесь на стартовый экран и попробуйте начать заново.
          </span>
          <button
            className="btn-blue"
            onClick={() => {
              setSession(null)
              setScreen('start')
              void loadHistory()
            }}
            type="button"
          >
            Вернуться к началу
          </button>
        </section>
      ) : null}

      {screen === 'result' && result !== null ? (
        <section className="flex max-w-3xl flex-col gap-5 rounded-panel bg-raised p-6 shadow-raised sm:p-8">
          <span className="label-cap">Результат сессии</span>
          {(() => {
            const threshold = gradePassThreshold(result.grade)
            const tone = scoreTone(result.result_score, threshold)
            const verdict = verdictInfo(result.verdict)
            return (
              <>
                <div className="flex flex-col items-start justify-between gap-4 rounded-2xl bg-inset p-5 shadow-inset-sm sm:flex-row sm:items-center">
                  <div className="flex flex-col">
                    <span className={`font-mono text-[40px] font-extrabold leading-none ${tone}`}>
                      {result.result_score}
                      <span className="font-mono text-[20px] font-normal text-ink-secondary"> / 100</span>
                    </span>
                    <span className="mt-1 font-sans text-caption text-ink-secondary">Верных ответов: {result.correct_count} из {result.task_count}</span>
                  </div>
                  <div className="flex flex-col items-start gap-2 sm:items-end">
                    <span className="font-mono text-[16px] font-bold uppercase text-pvn-blue">{result.grade}</span>
                    {result.suggested_grade !== null && result.suggested_grade !== undefined ? (
                      <span className="font-sans text-caption text-ink-secondary">Рекомендованный грейд: {result.suggested_grade}</span>
                    ) : null}
                  </div>
                </div>
                <div className="flex flex-col gap-1.5">
                  <div className="relative h-3 w-full overflow-hidden rounded-full bg-sunken shadow-inset-sm">
                    <div className={`h-full rounded-full transition-all ${result.result_score >= threshold ? 'bg-good' : 'bg-pvn-blue'}`} style={{ width: `${result.result_score}%` }} />
                    <span className="absolute inset-y-0 w-0.5 bg-ink/60" style={{ left: `${threshold}%` }} />
                  </div>
                  <span className="font-sans text-[12px] text-ink-secondary">Порог грейда {result.grade}: {threshold} / 100</span>
                </div>
                <div className={`flex items-center gap-2 rounded-xl px-4 py-3 font-sans text-caption ${verdict.pill}`}>
                  <span className="material-symbols-outlined text-[18px]">{result.verdict === 'suggest_lower' ? 'info' : 'check_circle'}</span>
                  {verdict.label}
                </div>
              </>
            )
          })()}
          {result.grade_applied ? (
            <div className="flex items-center gap-2 rounded-xl bg-good/15 px-4 py-3 font-sans text-caption text-ink">
              <span className="material-symbols-outlined text-[18px] text-good-ink">workspace_premium</span>
              Подтверждён грейд <span className="font-bold uppercase">{result.grade}</span> — профиль обновлён.
            </div>
          ) : null}

          {result.review.length > 0 ? (
            <div className="flex flex-col gap-3">
              <span className="label-cap">Разбор ответов</span>
              <div className="flex flex-col gap-3">
                {result.review.map((item, index) => {
                  const selected = item.selected_index
                  const correct = item.reference_answer
                  return (
                    <div className="flex flex-col gap-3 rounded-2xl bg-inset p-4 shadow-inset-sm" key={item.task_id}>
                      <div className="flex items-center gap-3">
                        <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full font-mono text-[12px] font-bold text-white ${item.is_correct ? 'bg-good' : 'bg-pvn-red'}`}>
                          {item.is_correct ? '✓' : '×'}
                        </span>
                        <span className="font-mono text-[12px] font-bold uppercase tracking-wider text-ink-secondary">Вопрос {index + 1}</span>
                      </div>
                      <TaskStatement statement={item.statement} />
                      {item.task_format === 'design_annotation' && item.image_data_url ? (
                        <div className="flex flex-col gap-3">
                          <img alt="Макет задания" className="w-full max-w-sm rounded-xl shadow-raised-sm" src={item.image_data_url} />
                          {item.answer_text ? (
                            <span className="font-sans text-[13px] text-ink">
                              <span className="font-mono text-[11px] font-bold uppercase tracking-wider text-ink-secondary">Ваше пояснение: </span>
                              {item.answer_text}
                            </span>
                          ) : null}
                          {item.feedback ? (
                            <span className="rounded-xl bg-raised px-3 py-2 font-sans text-[13px] text-ink-secondary shadow-raised-sm">{item.feedback}</span>
                          ) : null}
                        </div>
                      ) : (
                      <div className="flex flex-col gap-1.5">
                        {item.options.map((option, optionIndex) => {
                          const isCorrectOption = correct === optionIndex
                          const isSelectedOption = selected === optionIndex
                          return (
                            <div
                              className={`flex items-start gap-2 rounded-xl px-3 py-2 font-sans text-[13px] ${
                                isCorrectOption ? 'bg-good/10 text-ink ring-1 ring-good/30' : isSelectedOption ? 'bg-pvn-red/10 text-ink ring-1 ring-pvn-red/30' : 'text-ink-secondary'
                              }`}
                              key={optionIndex}
                            >
                              <span className="font-mono font-bold text-pvn-blue">{OPTION_LETTERS[optionIndex] ?? optionIndex + 1}.</span>
                              <span>{option}</span>
                              {isCorrectOption ? <span className="ml-auto shrink-0 font-mono text-[11px] font-bold uppercase text-good-ink">верно</span> : null}
                              {isSelectedOption && !isCorrectOption ? <span className="ml-auto shrink-0 font-mono text-[11px] font-bold uppercase text-pvn-red-ink">ваш ответ</span> : null}
                            </div>
                          )
                        })}
                      </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          ) : null}

          <div className="flex flex-wrap items-center gap-3">
            <button
              className="btn-blue"
              onClick={() => {
                setResult(null)
                setSession(null)
                setScreen('start')
                void loadHistory()
              }}
              type="button"
            >
              Пройти тест снова
            </button>
            <button
              className="btn-ghost"
              onClick={() => {
                setResult(null)
                setSession(null)
                setScreen('start')
                void loadHistory()
              }}
              type="button"
            >
              Вернуться к началу
            </button>
          </div>
        </section>
      ) : null}

      <Modal
        labelledBy="session-review-title"
        onClose={() => setReview(null)}
        open={review !== null}
        panelClassName="relative flex w-full max-w-3xl flex-col max-h-[calc(100dvh-2rem)] overflow-hidden rounded-panel bg-raised shadow-raised-lg"
      >
        <div className="flex flex-col gap-1 border-b border-ink/10 px-6 py-5">
          <h2 className="font-mono text-h3 font-extrabold text-ink" id="session-review-title">
            Разбор теста
          </h2>
          {review !== null ? (
            <p className="font-sans text-caption text-ink-secondary">
              Грейд {gradeLabel(review.grade)} · {review.correct_count} из {review.task_count} верно · {review.result_score ?? 0} / 100
            </p>
          ) : null}
        </div>
        <div className="flex flex-1 flex-col gap-3 overflow-y-auto px-6 py-5">
          {review !== null && review.review.length === 0 ? (
            <div className="flex flex-col items-center gap-3 py-8 text-center text-ink-secondary">
              <span className="material-symbols-outlined text-[40px] text-ink-muted">history_toggle_off</span>
              <span className="font-mono text-h3 font-bold text-ink">Разбор недоступен</span>
              <span className="max-w-md font-sans text-caption">
                Для этой сессии не сохранены ответы — возможно, она была пройдена или загружена до появления разбора. Пройдите тест заново, чтобы увидеть разбор.
              </span>
            </div>
          ) : null}
          {review !== null
            ? review.review.map((item, index) => (
                <div className="flex flex-col gap-3 rounded-2xl bg-inset p-4 shadow-inset-sm" key={item.task_id}>
                  <div className="flex items-center gap-3">
                    <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full font-mono text-[12px] font-bold text-white ${item.is_correct ? 'bg-good' : 'bg-pvn-red'}`}>
                      {item.is_correct ? '✓' : '×'}
                    </span>
                    <span className="font-mono text-[12px] font-bold uppercase tracking-wider text-ink-secondary">Вопрос {index + 1}</span>
                  </div>
                  <TaskStatement statement={item.statement} />
                  {item.task_format === 'design_annotation' && item.image_data_url ? (
                    <div className="flex flex-col gap-3">
                      <img alt="Макет задания" className="w-full max-w-sm rounded-xl shadow-raised-sm" src={item.image_data_url} />
                      {item.answer_text ? (
                        <span className="font-sans text-[13px] text-ink">
                          <span className="font-mono text-[11px] font-bold uppercase tracking-wider text-ink-secondary">Ваше пояснение: </span>
                          {item.answer_text}
                        </span>
                      ) : null}
                      {item.feedback ? (
                        <span className="rounded-xl bg-raised px-3 py-2 font-sans text-[13px] text-ink-secondary shadow-raised-sm">{item.feedback}</span>
                      ) : null}
                    </div>
                  ) : (
                    <div className="flex flex-col gap-1.5">
                      {item.options.map((option, optionIndex) => {
                        const isCorrectOption = item.reference_answer === optionIndex
                        const isSelectedOption = item.selected_index === optionIndex
                        return (
                          <div
                            className={`flex items-start gap-2 rounded-xl px-3 py-2 font-sans text-[13px] ${
                              isCorrectOption ? 'bg-good/10 text-ink ring-1 ring-good/30' : isSelectedOption ? 'bg-pvn-red/10 text-ink ring-1 ring-pvn-red/30' : 'text-ink-secondary'
                            }`}
                            key={optionIndex}
                          >
                            <span className="font-mono font-bold text-pvn-blue">{OPTION_LETTERS[optionIndex] ?? optionIndex + 1}.</span>
                            <span>{option}</span>
                            {isCorrectOption ? <span className="ml-auto shrink-0 font-mono text-[11px] font-bold uppercase text-good-ink">верно</span> : null}
                            {isSelectedOption && !isCorrectOption ? <span className="ml-auto shrink-0 font-mono text-[11px] font-bold uppercase text-pvn-red-ink">ваш ответ</span> : null}
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              ))
            : null}
        </div>
        <div className="sticky bottom-0 border-t border-ink/10 bg-raised px-6 py-4">
          <button className="btn-ghost" onClick={() => setReview(null)} type="button">Закрыть</button>
        </div>
      </Modal>

      <Modal
        labelledBy="test-rules-title"
        onClose={() => setRulesGrade(null)}
        open={rulesGrade !== null}
        panelClassName="relative flex w-full max-w-lg flex-col max-h-[calc(100dvh-2rem)] overflow-hidden rounded-panel bg-raised shadow-raised-lg"
      >
        <div className="flex flex-col gap-1 border-b border-ink/10 px-6 py-5">
          <h2 className="font-mono text-h3 font-extrabold text-ink" id="test-rules-title">
            Правила сдачи теста
          </h2>
          <p className="font-sans text-caption text-ink-secondary">
            Грейд {rulesGrade !== null ? gradeLabel(rulesGrade) : ''} · {TASKS_PER_SESSION} вопросов
          </p>
        </div>
        <div className="flex-1 overflow-y-auto px-6 py-5">
          <ul className="flex flex-col gap-3">
            {TEST_RULES.map((rule) => (
              <li className="flex items-start gap-3" key={rule}>
                <span className="material-symbols-outlined mt-0.5 shrink-0 text-[18px] text-pvn-blue">check_circle</span>
                <span className="font-sans text-caption leading-relaxed text-ink-secondary">{rule}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="sticky bottom-0 flex flex-col gap-3 border-t border-ink/10 bg-raised px-6 py-4">
          <label className="flex cursor-pointer items-start gap-3">
            <input
              checked={rulesAccepted}
              className="mt-0.5 h-5 w-5 shrink-0 rounded-md accent-pvn-blue"
              onChange={(event) => setRulesAccepted(event.target.checked)}
              type="checkbox"
            />
            <span className="font-sans text-caption leading-snug text-ink-secondary">
              Я ознакомлен(а) с правилами и согласен(на) начать тестирование
            </span>
          </label>
          <div className="flex flex-wrap gap-3">
            <button
              className="btn-primary"
              disabled={!rulesAccepted || isBusy}
              onClick={() => {
                const grade = rulesGrade
                setRulesGrade(null)
                if (grade !== null) void start(grade)
              }}
              type="button"
            >
              {isBusy ? 'Создаём тест…' : 'Согласен, начать тест'}
            </button>
            <button className="btn-ghost" onClick={() => setRulesGrade(null)} type="button">
              Не согласен
            </button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
