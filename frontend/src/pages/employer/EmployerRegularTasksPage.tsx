import { useCallback, useEffect, useState } from 'react'
import { ApiError } from '../../api/client'
import {
  closeRegularTask,
  createRegularTask,
  fetchConcepts,
  fetchEmployerRegularTasks,
  fetchMyVacancies,
  fetchVacancyTaskResults,
  anonymousCandidateId,
} from '../../api/platform'
import type { ApplicationTaskResult, Concept, RegularTask, Vacancy } from '../../api/platform'
import { Toast } from '../../components/Toast'
import { useGenerationGuard } from '../../lib/generationGuard'
import { Modal } from '../../components/Modal'
import { TaskStatement } from '../../components/TaskStatement'

const OPTION_LETTERS = ['А', 'Б', 'В', 'Г', 'Д', 'Е', 'Ж', 'З']

type CreateMode = 'concept' | 'manual'

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' })
}

function SkeletonTask() {
  return (
    <div className="flex w-full animate-pulse flex-col gap-3 rounded-panel bg-raised p-6 shadow-raised">
      <div className="h-5 w-64 rounded-lg bg-inset" />
      <div className="h-4 w-full rounded-lg bg-inset" />
      <div className="h-4 w-48 rounded-lg bg-inset" />
    </div>
  )
}

export function EmployerRegularTasksPage() {
  const [vacancies, setVacancies] = useState<Vacancy[]>([])
  const [selectedVacancyId, setSelectedVacancyId] = useState<number | null>(null)
  const [tasks, setTasks] = useState<RegularTask[]>([])
  const [results, setResults] = useState<ApplicationTaskResult[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [listError, setListError] = useState<string | null>(null)
  const [createMode, setCreateMode] = useState<CreateMode>('concept')
  const [conceptId, setConceptId] = useState('')
  const [conceptQuery, setConceptQuery] = useState('')
  const [highlightedConcept, setHighlightedConcept] = useState(0)
  const [statement, setStatement] = useState('')
  const [options, setOptions] = useState<string[]>(['', ''])
  const [correctIndex, setCorrectIndex] = useState(0)
  const [formError, setFormError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [confirmingCloseId, setConfirmingCloseId] = useState<number | null>(null)
  const [isClosing, setIsClosing] = useState(false)
  const [successNotice, setSuccessNotice] = useState<string | null>(null)
  const [concepts, setConcepts] = useState<Concept[]>([])
  const [previewTask, setPreviewTask] = useState<RegularTask | null>(null)
  useGenerationGuard(isSubmitting)

  const loadVacancies = useCallback(async () => {
    try {
      const loaded = await fetchMyVacancies({ limit: 200 })
      const open = loaded.filter((vacancy) => vacancy.is_open)
      setVacancies(open)
      setSelectedVacancyId((previous) => previous ?? open[0]?.id ?? null)
    } catch (exception) {
      if (exception instanceof ApiError) setListError(exception.detail)
      else setListError('Не удалось загрузить вакансии')
    }
  }, [])

  const loadVacancyData = useCallback(async (vacancyId: number) => {
    setIsLoading(true)
    try {
      const [loadedTasks, loadedResults] = await Promise.all([
        fetchEmployerRegularTasks(vacancyId),
        fetchVacancyTaskResults(vacancyId),
      ])
      setTasks(loadedTasks)
      setResults(loadedResults)
      setListError(null)
    } catch (exception) {
      if (exception instanceof ApiError) setListError(exception.detail)
      else setListError('Не удалось загрузить задания')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadVacancies()
  }, [loadVacancies])

  useEffect(() => {
    if (selectedVacancyId !== null) void loadVacancyData(selectedVacancyId)
  }, [selectedVacancyId, loadVacancyData])

  useEffect(() => {
    fetchConcepts().then(setConcepts).catch(() => setConcepts([]))
  }, [])

  const filteredConcepts = concepts.filter((concept) => {
    const query = conceptQuery.trim().toLowerCase()
    if (query === '') return true
    return [concept.name, concept.domain, concept.grade].some((field) => field.toLowerCase().includes(query))
  })

  const selectConcept = (concept: Concept) => {
    setConceptId(String(concept.id))
    setConceptQuery(`${concept.name} · ${concept.grade} · ${concept.domain}`)
    setHighlightedConcept(0)
  }

  const setOption = (index: number, value: string) => {
    setOptions((previous) => previous.map((item, itemIndex) => (itemIndex === index ? value : item)))
  }

  const addOption = () => {
    if (options.length >= 8) return
    setOptions((previous) => [...previous, ''])
  }

  const removeOption = (index: number) => {
    if (options.length <= 2) return
    setOptions((previous) => previous.filter((_, itemIndex) => itemIndex !== index))
    setCorrectIndex((previous) => (index < previous ? previous - 1 : index === previous ? 0 : previous))
  }

  const submitTask = async (event: React.FormEvent) => {
    event.preventDefault()
    setFormError(null)
    if (selectedVacancyId === null) {
      setFormError('Сначала выберите вакансию')
      return
    }
    if (createMode === 'concept') {
      const parsedConceptId = Number(conceptId)
      if (!Number.isInteger(parsedConceptId) || parsedConceptId <= 0) {
        setFormError('Укажите концепт из банка')
        return
      }
      setIsSubmitting(true)
      try {
        const created = await createRegularTask({ vacancy_id: selectedVacancyId, concept_id: parsedConceptId })
        setTasks((previous) => [created, ...previous])
        setConceptId('')
        setConceptQuery('')
        setSuccessNotice('Задание сгенерировано из концепта и привязано к вакансии')
      } catch (exception) {
        if (exception instanceof ApiError) setFormError(exception.detail)
        else setFormError('Не удалось создать задание')
      } finally {
        setIsSubmitting(false)
      }
      return
    }
    if (statement.trim().length === 0) {
      setFormError('Укажите формулировку задания')
      return
    }
    if (options.some((option) => option.trim().length === 0)) {
      setFormError('Заполните все варианты ответа')
      return
    }
    const trimmedOptions = options.map((option) => option.trim())
    if (correctIndex >= trimmedOptions.length) {
      setFormError('Выберите правильный вариант')
      return
    }
    setIsSubmitting(true)
    try {
      const created = await createRegularTask({
        vacancy_id: selectedVacancyId,
        statement: statement.trim(),
        options: trimmedOptions,
        correct_index: correctIndex,
      })
      setTasks((previous) => [created, ...previous])
      setStatement('')
      setOptions(['', ''])
      setCorrectIndex(0)
      setSuccessNotice('Задание привязано к вакансии')
    } catch (exception) {
      if (exception instanceof ApiError) setFormError(exception.detail)
      else setFormError('Не удалось создать задание')
    } finally {
      setIsSubmitting(false)
    }
  }

  const confirmClose = async (taskId: number) => {
    setIsClosing(true)
    try {
      const closed = await closeRegularTask(taskId)
      setTasks((previous) => previous.map((item) => (item.id === closed.id ? closed : item)))
      setConfirmingCloseId(null)
      setSuccessNotice('Задание закрыто')
    } catch (exception) {
      if (exception instanceof ApiError) setListError(exception.detail)
      else setListError('Не удалось закрыть задание')
    } finally {
      setIsClosing(false)
    }
  }

  const selectedVacancy = vacancies.find((vacancy) => vacancy.id === selectedVacancyId) ?? null

  return (
    <div className="mx-auto flex w-full max-w-[1280px] flex-col gap-6 px-4 py-8 sm:px-6">
      <div className="flex flex-col gap-1">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="font-mono text-display font-extrabold tracking-tight text-ink">Задания к вакансии</h1>
          {!isLoading ? <span className="stat-pill bg-inset text-ink-secondary">{tasks.length} заданий</span> : null}
        </div>
        <p className="max-w-3xl font-sans text-body text-ink-secondary">
          Кандидат получает задания после отклика на вакансию. Проходит их под прокторингом, результат виден только вам.
        </p>
      </div>

      {vacancies.length === 0 && !isLoading ? (
        <div className="flex flex-col items-center gap-3 rounded-panel bg-raised p-12 text-center shadow-raised">
          <span className="material-symbols-outlined text-[40px] text-ink-muted">work</span>
          <span className="font-mono text-h2 font-bold text-ink">Сначала опубликуйте вакансию</span>
          <span className="max-w-md font-sans text-caption text-ink-secondary">
            Задания привязаны к вакансии и показываются откликнувшимся кандидатам.
          </span>
        </div>
      ) : (
        <>
          <div className="flex flex-col gap-3 rounded-panel bg-raised p-5 shadow-raised">
            <label className="label-cap" htmlFor="vacancy-picker">Вакансия</label>
            <select
              className="field"
              id="vacancy-picker"
              onChange={(event) => setSelectedVacancyId(Number(event.target.value))}
              value={selectedVacancyId ?? ''}
            >
              {vacancies.map((vacancy) => (
                <option key={vacancy.id} value={vacancy.id}>
                  {vacancy.title} · {vacancy.grade}
                </option>
              ))}
            </select>
            {selectedVacancy !== null ? (
              <span className="font-sans text-caption text-ink-secondary">
                {results.length === 0
                  ? 'Пока никто не проходил задания по этой вакансии.'
                  : `Прошли задания: ${results.length}. Результаты ниже.`}
              </span>
            ) : null}
          </div>

          <div className="flex w-full flex-col gap-5 rounded-panel bg-raised p-6 shadow-raised">
            <div className="flex flex-col gap-3">
              <h2 className="flex items-center gap-2 font-mono text-h2 font-bold tracking-tight text-ink">
                <span className="material-symbols-outlined text-[22px] text-pvn-blue">quiz</span>
                Новое задание
              </h2>
              <div className="flex w-fit items-center gap-1 rounded-2xl bg-inset p-1 shadow-inset-sm">
                {(
                  [
                    { value: 'concept', label: 'Из концепта' },
                    { value: 'manual', label: 'Вручную' },
                  ] as { value: CreateMode; label: string }[]
                ).map((item) => (
                  <button
                    className={
                      createMode === item.value
                        ? 'whitespace-nowrap rounded-xl bg-raised px-4 py-2 font-mono text-[12px] font-bold text-pvn-blue shadow-raised-sm transition-all'
                        : 'whitespace-nowrap rounded-xl px-4 py-2 font-mono text-[12px] font-medium text-ink-secondary transition-all hover:text-ink'
                    }
                    key={item.value}
                    onClick={() => {
                      setCreateMode(item.value)
                      setFormError(null)
                      setConceptId('')
                      setConceptQuery('')
                    }}
                    type="button"
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>

            <form className="flex flex-col gap-4" onSubmit={submitTask}>
              {createMode === 'concept' ? (
                <div className="relative flex flex-col gap-1.5">
                  <label className="label-cap" htmlFor="concept-id">Концепт из банка *</label>
                  <input
                    autoComplete="off"
                    className="field w-full py-2.5"
                    id="concept-id"
                    onBlur={() => {
                      if (conceptId === '') setConceptQuery('')
                    }}
                    onChange={(event) => {
                      setConceptQuery(event.target.value)
                      setConceptId('')
                      setHighlightedConcept(0)
                    }}
                    onKeyDown={(event) => {
                      if (conceptId !== '' || conceptQuery.trim() === '') return
                      const options = filteredConcepts.slice(0, 30)
                      if (options.length === 0) return
                      if (event.key === 'ArrowDown') {
                        event.preventDefault()
                        setHighlightedConcept((previous) => (previous + 1) % options.length)
                      } else if (event.key === 'ArrowUp') {
                        event.preventDefault()
                        setHighlightedConcept((previous) => (previous - 1 + options.length) % options.length)
                      } else if (event.key === 'Enter') {
                        event.preventDefault()
                        selectConcept(options[highlightedConcept] ?? options[0])
                      } else if (event.key === 'Escape') {
                        setConceptQuery('')
                      }
                    }}
                    placeholder="Начните вводить название, домен или грейд"
                    type="text"
                    value={conceptQuery}
                  />
                  {conceptId === '' && conceptQuery.trim() !== '' ? (
                    <div className="absolute inset-x-0 top-full z-30 mt-1 flex max-h-64 w-full flex-col overflow-y-auto rounded-xl border border-ink/10 bg-white p-1.5 shadow-[0_16px_40px_rgba(15,18,29,0.22)]" role="listbox">
                      {filteredConcepts.length === 0 ? (
                        <span className="px-3 py-2 font-sans text-caption text-ink-secondary">Ничего не найдено — попробуйте другое название, домен или грейд</span>
                      ) : (
                        filteredConcepts.slice(0, 30).map((concept, index) => (
                          <button
                            aria-selected={index === highlightedConcept}
                            className={`flex items-center justify-between gap-3 rounded-lg px-3 py-2 text-left transition-all ${index === highlightedConcept ? 'bg-pvn-blue/10' : 'hover:bg-inset'}`}
                            key={concept.id}
                            onMouseEnter={() => setHighlightedConcept(index)}
                            onMouseDown={(event) => {
                              event.preventDefault()
                              selectConcept(concept)
                            }}
                            role="option"
                            type="button"
                          >
                            <span className="font-sans text-caption text-ink">{concept.name}</span>
                            <span className="shrink-0 font-mono text-[11px] text-ink-muted">{concept.grade} · {concept.domain}</span>
                          </button>
                        ))
                      )}
                    </div>
                  ) : null}
                  {conceptId !== '' ? (
                    <span className="flex items-center gap-1.5 font-sans text-[12px] text-good-ink">
                      <span className="material-symbols-outlined text-[14px]">check_circle</span>
                      Концепт выбран — формулировка сгенерируется автоматически
                    </span>
                  ) : (
                    <span className="font-sans text-[12px] text-ink-secondary">Формулировка сгенерируется автоматически</span>
                  )}
                </div>
              ) : (
                <>
                  <div className="flex flex-col gap-1.5">
                    <label className="label-cap" htmlFor="task-statement">Формулировка задания *</label>
                    <textarea
                      className="field resize-none"
                      id="task-statement"
                      onChange={(event) => setStatement(event.target.value)}
                      placeholder="Выберите верное утверждение о блокировках в PostgreSQL…"
                      rows={6}
                      value={statement}
                    />
                    <span className="font-sans text-caption text-ink-secondary">
                      Enter создаёт перенос строки, пустая строка разделяет абзацы. Код оформляется в тройных обратных кавычках.
                    </span>
                  </div>
                  <div className="flex flex-col gap-2">
                    <div className="flex items-center justify-between">
                      <span className="label-cap">Варианты ответа *</span>
                      <span className="font-sans text-[12px] text-ink-muted">Отметьте правильный</span>
                    </div>
                    <div className="flex flex-col gap-2" role="radiogroup" aria-label="Правильный вариант ответа">
                      {options.map((option, index) => (
                        <div className="flex items-center gap-2" key={index}>
                          <label className="shrink-0 cursor-pointer" title="Отметить как правильный">
                            <input
                              aria-label={`Вариант ${OPTION_LETTERS[index] ?? index + 1} — правильный ответ`}
                              checked={correctIndex === index}
                              className="sr-only"
                              name="correct-answer"
                              onChange={() => setCorrectIndex(index)}
                              type="radio"
                              value={index}
                            />
                            <span
                              aria-hidden="true"
                              className={
                                correctIndex === index
                                  ? 'flex h-9 w-9 items-center justify-center rounded-xl bg-pvn-blue font-mono text-[13px] font-bold text-white shadow-blue'
                                  : 'flex h-9 w-9 items-center justify-center rounded-xl bg-inset font-mono text-[13px] font-semibold text-ink-secondary shadow-inset-sm'
                              }
                            >
                              {OPTION_LETTERS[index] ?? index + 1}
                            </span>
                          </label>
                          <input
                            className="field py-2.5"
                            onChange={(event) => setOption(index, event.target.value)}
                            placeholder={`Вариант ${OPTION_LETTERS[index] ?? index + 1}`}
                            type="text"
                            value={option}
                          />
                          {options.length > 2 ? (
                            <button
                              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-ink-muted transition-all hover:bg-inset hover:text-pvn-red-ink"
                              onClick={() => removeOption(index)}
                              title="Удалить вариант"
                              type="button"
                            >
                              <span className="material-symbols-outlined text-[18px]">close</span>
                            </button>
                          ) : null}
                        </div>
                      ))}
                    </div>
                    {options.length < 8 ? (
                      <button className="flex w-fit items-center gap-1 px-2 py-1 font-mono text-[12px] font-semibold text-pvn-blue hover:underline" onClick={addOption} type="button">
                        <span className="material-symbols-outlined text-[16px]">add</span> Добавить вариант
                      </button>
                    ) : null}
                  </div>
                </>
              )}
              {formError !== null ? (
                <div className="flex items-center gap-2 rounded-xl bg-pvn-red/10 px-4 py-3 font-sans text-caption text-pvn-red-ink">
                  <span className="material-symbols-outlined text-[18px]">error</span>
                  <span>{formError}</span>
                </div>
              ) : null}
              <div className="flex flex-col items-start gap-3">
                <button className="btn-primary min-w-[260px] justify-center whitespace-nowrap" disabled={isSubmitting} type="submit">
                  {isSubmitting ? (
                    <span aria-hidden="true" className="spinner" />
                  ) : (
                    <span className="material-symbols-outlined text-[18px]">publish</span>
                  )}
                  {isSubmitting ? (createMode === 'concept' ? 'Генерируем задание' : 'Публикуем') : 'Добавить задание к вакансии'}
                </button>
                {isSubmitting && createMode === 'concept' ? (
                  <div className="flex w-full max-w-md flex-col gap-2">
                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-sunken shadow-inset-sm">
                      <div className="generation-bar h-full rounded-full bg-pvn-blue" />
                    </div>
                    <span className="font-sans text-caption text-ink-secondary">Обычно это занимает до минуты. Не покидайте страницу.</span>
                  </div>
                ) : null}
              </div>
            </form>
          </div>

          <Toast message={successNotice} onClose={() => setSuccessNotice(null)} />
          <Modal labelledBy="task-preview-title" onClose={() => setPreviewTask(null)} open={previewTask !== null} panelClassName="relative w-full max-w-lg overflow-y-auto rounded-panel bg-raised p-6 shadow-raised-lg">
            {previewTask !== null ? (
              <div className="flex flex-col gap-5">
                <div className="flex flex-col gap-1">
                  <span className="font-mono text-[12px] uppercase tracking-wider text-ink-muted">Так видит задание кандидат</span>
                  <div className="rounded-2xl bg-inset p-5 shadow-inset-sm" id="task-preview-title">
                    <TaskStatement statement={previewTask.statement} />
                  </div>
                </div>
                <div className="flex flex-col gap-2">
                  {previewTask.options.map((option, index) => (
                    <div className="flex items-center gap-3 rounded-xl bg-inset px-4 py-3 font-sans text-body text-ink shadow-inset-sm" key={index}>
                      <span className="font-mono text-[13px] font-bold text-pvn-blue">{OPTION_LETTERS[index] ?? index + 1}</span>
                      {option}
                    </div>
                  ))}
                </div>
                <div className="flex justify-end">
                  <button className="btn-ghost" onClick={() => setPreviewTask(null)} type="button">Закрыть</button>
                </div>
              </div>
            ) : null}
          </Modal>

          {listError !== null ? (
            <div className="flex items-center gap-3 rounded-panel bg-pvn-red/10 px-5 py-4 font-sans text-caption text-pvn-red-ink shadow-raised-sm">
              <span className="material-symbols-outlined text-[18px]">error</span>
              <span>{listError}</span>
              <button className="ml-auto font-mono font-semibold underline" onClick={() => selectedVacancyId !== null && void loadVacancyData(selectedVacancyId)} type="button">Повторить</button>
            </div>
          ) : null}

          {results.length > 0 ? (
            <div className="flex w-full flex-col gap-3 rounded-panel bg-raised p-6 shadow-raised">
              <h2 className="flex items-center gap-2 font-mono text-h2 font-bold tracking-tight text-ink">
                <span className="material-symbols-outlined text-[22px] text-pvn-blue">fact_check</span>
                Результаты откликнувшихся
              </h2>
              <div className="flex flex-col divide-y divide-ink/10">
                {results.map((result) => (
                  <div className="flex flex-wrap items-center justify-between gap-3 py-3" key={result.application_id}>
                    <span className="font-mono text-[12px] font-semibold text-ink">
                      Кандидат {anonymousCandidateId(result.application_id)}
                    </span>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={result.status === 'completed' ? 'stat-pill bg-good/15 text-good-ink' : 'stat-pill bg-inset text-ink-secondary'}>
                        {result.status === 'completed' ? `${result.correct_count} из ${result.task_count} верно` : 'проходит'}
                      </span>
                      {result.result_score !== null ? (
                        <span className="font-mono text-[13px] font-bold text-pvn-blue">{result.result_score} / 100</span>
                      ) : null}
                      {result.forced_finish ? (
                        <span className="stat-pill bg-warn/15 text-warn-ink" title="Тест завершён досрочно: выход из полноэкранного режима или переключение окна">
                          досрочно
                        </span>
                      ) : null}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          <div className="flex flex-col gap-4">
            <h2 className="flex items-center gap-2 font-mono text-h2 font-bold tracking-tight text-ink">
              <span className="material-symbols-outlined text-[22px] text-pvn-blue">list_alt</span>
              Задания вакансии
            </h2>
            {isLoading ? (
              <div className="flex flex-col gap-4">
                <SkeletonTask />
                <SkeletonTask />
              </div>
            ) : tasks.length === 0 ? (
              <div className="flex flex-col items-center gap-3 rounded-panel bg-raised p-12 text-center shadow-raised">
                <span className="material-symbols-outlined text-[40px] text-ink-muted">quiz</span>
                <span className="font-mono text-h2 font-bold text-ink">Заданий пока нет</span>
                <span className="max-w-md font-sans text-caption text-ink-secondary">
                  Добавьте первое задание из концепта банка или составьте его вручную
                </span>
              </div>
            ) : (
              <div className="flex flex-col gap-4">
                {tasks.map((task) => (
                  <div className="flex w-full flex-col gap-4 rounded-panel bg-raised p-6 shadow-raised" key={task.id}>
                    <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
                      <div className="flex flex-col gap-2">
                        <div className="flex flex-wrap items-center gap-2">
                          {task.is_active ? (
                            <span className="stat-pill bg-good/15 text-good-ink">Активно</span>
                          ) : (
                            <span className="stat-pill bg-sunken text-ink-secondary">Закрыто</span>
                          )}
                          <span className="font-mono text-[12px] text-ink-muted">{formatDateTime(task.created_at)}</span>
                        </div>
                        <p className="line-clamp-2 max-w-2xl font-sans text-[14px] leading-snug text-ink">
                          {task.statement.replace(/```[a-zA-Z0-9_+-]*/g, ' ').replace(/\s+/g, ' ').trim()}
                        </p>
                        <span className="font-mono text-[12px] font-semibold text-ink-secondary">
                          {task.options.length} варианта ответа
                        </span>
                      </div>
                      <div className="flex shrink-0 flex-wrap items-center gap-2">
                        <button className="btn-ghost py-2 text-[13px]" onClick={() => setPreviewTask(task)} type="button">
                          <span className="material-symbols-outlined text-[18px]">preview</span>
                          Предпросмотр
                        </button>
                        {task.is_active ? (
                          confirmingCloseId === task.id ? (
                            <div className="flex items-center gap-2">
                              <button className="btn-primary py-2 text-[13px]" disabled={isClosing} onClick={() => void confirmClose(task.id)} type="button">
                                Да, закрыть
                              </button>
                              <button className="btn-ghost py-2 text-[13px]" onClick={() => setConfirmingCloseId(null)} type="button">Отмена</button>
                            </div>
                          ) : (
                            <button className="btn-ghost py-2 text-[13px]" onClick={() => setConfirmingCloseId(task.id)} type="button">
                              <span className="material-symbols-outlined text-[18px]">close</span>
                              Закрыть
                            </button>
                          )
                        ) : null}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
