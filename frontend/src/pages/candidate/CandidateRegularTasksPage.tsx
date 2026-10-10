import { useCallback, useEffect, useState } from 'react'
import { ApiError } from '../../api/client'
import { answerRegularTask, fetchActiveRegularTasks } from '../../api/platform'
import type { RegularTask, RegularTaskAnswerResult } from '../../api/platform'
import { Modal } from '../../components/Modal'
import { TaskStatement } from '../../components/TaskStatement'
import { taskFormatLabel } from '../../lib/format'

const OPTION_LETTERS = ['А', 'Б', 'В', 'Г', 'Д', 'Е', 'Ж', 'З']

interface TaskInlineError {
  taskId: number
  message: string
}

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
  const [tasks, setTasks] = useState<RegularTask[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [listError, setListError] = useState<string | null>(null)
  const [selections, setSelections] = useState<Record<number, number>>({})
  const [answeringId, setAnsweringId] = useState<number | null>(null)
  const [inlineError, setInlineError] = useState<TaskInlineError | null>(null)
  const [conflictNotice, setConflictNotice] = useState<string | null>(null)
  const [lastResult, setLastResult] = useState<RegularTaskAnswerResult | null>(null)
  const [confirmingTask, setConfirmingTask] = useState<RegularTask | null>(null)

  const loadTasks = useCallback(async () => {
    try {
      const loaded = await fetchActiveRegularTasks()
      setTasks(loaded)
      setListError(null)
    } catch (exception) {
      if (exception instanceof ApiError) setListError(exception.detail)
      else setListError('Не удалось загрузить задания')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void Promise.resolve().then(loadTasks)
  }, [loadTasks])

  const submitAnswer = async (task: RegularTask) => {
    const selected = selections[task.id]
    if (selected === undefined || answeringId !== null) return
    setAnsweringId(task.id)
    setInlineError(null)
    setConflictNotice(null)
    try {
      const result = await answerRegularTask(task.id, selected)
      setTasks((previous) => previous.filter((item) => item.id !== task.id))
      setSelections((previous) => {
        const next = { ...previous }
        delete next[task.id]
        return next
      })
      setLastResult(result)
    } catch (exception) {
      if (exception instanceof ApiError && exception.status === 409) {
        setTasks((previous) => previous.filter((item) => item.id !== task.id))
        setSelections((previous) => {
          const next = { ...previous }
          delete next[task.id]
          return next
        })
        setConflictNotice(exception.detail)
      } else if (exception instanceof ApiError) {
        setInlineError({ taskId: task.id, message: exception.detail })
      } else {
        setInlineError({ taskId: task.id, message: 'Не удалось отправить ответ' })
      }
    } finally {
      setAnsweringId(null)
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-8 sm:px-6">
      <div className="flex flex-col gap-1">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="font-mono text-display font-extrabold tracking-tight text-ink">Регулярные задания</h1>
          {!isLoading ? <span className="stat-pill bg-inset text-ink-secondary">{tasks.length} доступно</span> : null}
        </div>
        <p className="font-sans text-body text-ink-secondary">
          Одна попытка на задание. Верный ответ повышает балл.
        </p>
      </div>

      {lastResult !== null ? (
        <div className={`flex items-center gap-3 rounded-panel px-5 py-4 font-sans text-caption shadow-raised-sm ${lastResult.is_correct ? 'bg-good/15 text-good-ink' : 'bg-pvn-red/10 text-pvn-red-ink'}`}>
          <span className="material-symbols-outlined text-[18px]">{lastResult.is_correct ? 'check_circle' : 'cancel'}</span>
          <span className="font-semibold">{lastResult.is_correct ? 'Ответ верный' : 'Ответ неверный'}</span>
          <button className="ml-auto flex h-6 w-6 items-center justify-center rounded-full hover:bg-black/5" onClick={() => setLastResult(null)} type="button">
            <span className="material-symbols-outlined text-[16px]">close</span>
          </button>
        </div>
      ) : null}

      {conflictNotice !== null ? (
        <div className="flex items-center gap-3 rounded-panel bg-pvn-red/10 px-5 py-4 font-sans text-caption text-pvn-red-ink shadow-raised-sm">
          <span className="material-symbols-outlined text-[18px]">error</span>
          <span>{conflictNotice}</span>
        </div>
      ) : null}

      {listError !== null ? (
        <div className="flex items-center gap-3 rounded-panel bg-pvn-red/10 px-5 py-4 font-sans text-caption text-pvn-red-ink shadow-raised-sm">
          <span className="material-symbols-outlined text-[18px]">error</span>
          <span>{listError}</span>
          <button className="ml-auto font-mono font-semibold underline" onClick={() => void loadTasks()} type="button">Повторить</button>
        </div>
      ) : null}

      {isLoading ? (
        <div className="flex flex-col gap-4">
          <SkeletonTask />
          <SkeletonTask />
          <SkeletonTask />
        </div>
      ) : tasks.length === 0 ? (
        <div className="flex flex-col items-center gap-3 rounded-panel bg-raised p-12 text-center shadow-raised">
          <span className="material-symbols-outlined text-[40px] text-ink-muted">task_alt</span>
          <span className="font-mono text-h2 font-bold text-ink">Новых заданий нет</span>
          <span className="max-w-md font-sans text-caption text-ink-secondary">
            {listError === null
              ? 'Вы ответили на все активные задания. Загляните позже — работодатели публикуют новые.'
              : 'Не удалось получить список заданий'}
          </span>
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {tasks.map((task) => {
            const selected = selections[task.id]
            const isAnswering = answeringId === task.id
            return (
              <div className="flex w-full flex-col gap-4 rounded-panel bg-raised p-6 shadow-raised" key={task.id}>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="stat-pill bg-pvn-blue/10 text-pvn-blue">{taskFormatLabel(task.task_format)}</span>
                </div>
                <div className="rounded-2xl bg-inset p-5 shadow-inset-sm">
                  <TaskStatement statement={task.statement} />
                </div>
                <div className="flex flex-col gap-2.5">
                  {task.options.map((option, index) => {
                    const isSelected = selected === index
                    return (
                      <button
                        className={
                          isSelected
                            ? 'flex w-full items-center gap-3 rounded-xl bg-pvn-blue px-4 py-3 text-left font-sans text-[15px] text-white shadow-blue transition-all'
                            : 'flex w-full items-center gap-3 rounded-xl bg-inset px-4 py-3 text-left font-sans text-[15px] text-ink shadow-inset-sm transition-all hover:bg-raised hover:shadow-raised-sm'
                        }
                        key={index}
                        onClick={() => setSelections({ ...selections, [task.id]: index })}
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
                {inlineError !== null && inlineError.taskId === task.id ? (
                  <div className="flex items-center gap-2 rounded-xl bg-pvn-red/10 px-4 py-2.5 font-sans text-caption text-pvn-red-ink">
                    <span className="material-symbols-outlined text-[18px]">error</span>
                    <span>{inlineError.message}</span>
                  </div>
                ) : null}
                <div className="flex flex-wrap items-center justify-between gap-4 border-t border-ink/10 pt-4">
                  <span className="flex items-center gap-1.5 font-sans text-caption text-ink-secondary">
                    <span className="material-symbols-outlined text-[16px]">lock</span>
                    Одна попытка
                  </span>
                  <button
                    className="btn-primary"
                    disabled={selected === undefined || isAnswering}
                    onClick={() => setConfirmingTask(task)}
                    type="button"
                  >
                    {isAnswering ? 'Отправка…' : 'Ответить'}
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {confirmingTask !== null ? (
        <Modal labelledBy="confirm-task-title" onClose={() => setConfirmingTask(null)} open panelClassName="relative w-full max-w-md rounded-panel bg-raised p-6 shadow-raised-lg">
          <div className="flex flex-col gap-4">
            <div className="flex items-center gap-3">
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-warn/15">
                <span className="material-symbols-outlined text-[22px] text-warn-ink">lock</span>
              </span>
              <span className="font-mono text-h3 font-bold text-ink" id="confirm-task-title">Отправить ответ?</span>
            </div>
            <p className="font-sans text-body text-ink-secondary">
              На задание даётся одна попытка — изменить ответ после отправки нельзя.
            </p>
            <div className="flex items-center justify-end gap-3">
              <button className="btn-ghost" onClick={() => setConfirmingTask(null)} type="button">Отмена</button>
              <button
                className="btn-primary"
                disabled={answeringId !== null}
                onClick={() => {
                  const target = confirmingTask
                  setConfirmingTask(null)
                  if (target !== null) void submitAnswer(target)
                }}
                type="button"
              >
                {answeringId !== null ? 'Отправка…' : 'Да, отправить'}
              </button>
            </div>
          </div>
        </Modal>
      ) : null}
    </div>
  )
}
