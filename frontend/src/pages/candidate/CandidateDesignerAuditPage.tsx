import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { ApiError } from '../../api/client'
import { fetchAssignedDesignerAudit, fetchDesignerAudit, fetchDesignerPortfolio, submitDesignerAudit, uploadDesignerPortfolio, uploadDesignerScreenshot } from '../../api/designerAudit'
import type { CriterionId, DesignerAudit, HeuristicId, PortfolioMetrics, SelectedViolation } from '../../api/designerAudit'

const heuristicCopy: Record<HeuristicId, { title: string; question: string; hint: string }> = {
  nielsen_visibility: { title: 'Видимость состояния системы', question: 'Понятно ли, что произошло и что будет дальше?', hint: 'Назовите действие и недостающую индикацию, подтверждение или обратную связь.' },
  nielsen_consistency: { title: 'Последовательность и стандарты', question: 'Одинаково ли ведут себя похожие элементы?', hint: 'Сравните конкретные подписи или элементы управления.' },
  nielsen_error_prevention: { title: 'Предотвращение ошибок', question: 'Может ли пользователь избежать серьёзной ошибки?', hint: 'Укажите опасное действие, недостающую проверку или подтверждение.' },
  nielsen_user_control: { title: 'Контроль и свобода пользователя', question: 'Можно ли отменить действие, вернуться или восстановить данные?', hint: 'Опишите потерю контроля и предложите путь восстановления.' },
  fitts_targets: { title: 'Закон Фиттса: размер и доступность целей', question: 'Легко ли дотянуться до нужного элемента и нажать на него?', hint: 'Назовите элемент, его расположение, примерный размер и отступы. Не выдавайте оценку на глаз за измерение.' },
  contrast: { title: 'Контраст и читаемость', question: 'Различимы ли текст, кнопки и их состояния?', hint: 'Укажите текст и фон. Численный контраст приводите только после измерения: ориентиры 4,5:1 для обычного текста и 3:1 для крупного.' },
  hierarchy: { title: 'Визуальная иерархия', question: 'Ясно ли следующее действие, не конкурируют ли акценты?', hint: 'Назовите конкурирующие элементы и объясните, как они мешают этому сценарию.' },
}

const criterionLabels: Record<CriterionId, string> = {
  evidence: 'Конкретность доказательств',
  reasoning: 'Связь со сценарием',
  prioritization: 'Обоснование критичности',
  actionability: 'Практичность рекомендации',
}

const severityLabels = { low: 'Низкая', medium: 'Средняя', high: 'Высокая' }
const inputClass = 'w-full rounded-xl border border-ink/20 bg-white px-3 py-2.5 text-body text-ink focus:border-pvn-blue focus:outline-none focus:ring-2 focus:ring-pvn-blue/20 disabled:opacity-60'
const buttonClass = 'rounded-full bg-pvn-blue px-5 py-3 font-mono text-[14px] font-bold text-white transition-colors hover:bg-pvn-blue/90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-pvn-blue disabled:cursor-not-allowed disabled:opacity-50'

function auditError(exception: unknown, fallback: string): string {
  if (!(exception instanceof ApiError)) return fallback
  if (exception.status === 413) return 'Файл слишком большой. Проверьте ограничение размера и выберите другой файл.'
  if (exception.status === 422) return 'Проверьте обязательные поля и длину ответов. У каждого нарушения должны быть доказательство, обоснование и рекомендация.'
  if (exception.status === 400) return 'Файл не удалось обработать. Проверьте формат, размер и содержимое; PDF должен содержать выделяемый текст.'
  if (exception.status === 403) return 'Этот раздел доступен только кандидатам с профилем.'
  return fallback
}

function AuditWorkspace({ audit, onUpdated }: { audit: DesignerAudit; onUpdated: (audit: DesignerAudit) => void }) {
  const [violations, setViolations] = useState<SelectedViolation[]>(audit.violations)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const assigned = audit.task_key !== null
  const completed = audit.status === 'submitted'
  const evaluation = audit.evaluation
  const retryable = assigned && completed && evaluation?.testing_score === null
  const shownViolations = completed ? audit.violations : violations
  const prefix = `audit-${audit.id}`

  function updateViolation(id: HeuristicId, change: Partial<SelectedViolation>) {
    setViolations((previous) => previous.map((item) => item.heuristic_id === id ? { ...item, ...change } : item))
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busy) return
    if (violations.length === 0) {
      setError('Отметьте хотя бы одно нарушение и опишите его.')
      return
    }
    const payload = violations.map((item) => ({ ...item, evidence: item.evidence.trim(), rationale: item.rationale.trim(), recommendation: item.recommendation.trim() }))
    if (payload.some((item) => item.evidence.length < 5 || item.rationale.length < 10 || item.recommendation.length < 10)) {
      setError('Для каждого нарушения укажите доказательство от 5 символов, обоснование и рекомендацию от 10 символов. Пробелы не учитываются.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      onUpdated(await submitDesignerAudit(audit.id, payload))
    } catch (exception) {
      try {
        const saved = await fetchDesignerAudit(audit.id)
        if (saved.status === 'submitted') onUpdated(saved)
        else setError(auditError(exception, 'Не удалось отправить аудит. Ответы остались в форме; попробуйте ещё раз.'))
      } catch {
        setError('Не удалось проверить отправку. Ответы остались в форме; попробуйте ещё раз, когда появится связь.')
      }
    } finally {
      setBusy(false)
    }
  }

  async function retryEvaluation() {
    if (busy || !retryable) return
    setBusy(true)
    setError(null)
    try {
      onUpdated(await submitDesignerAudit(audit.id, audit.violations))
    } catch (exception) {
      setError(auditError(exception, 'Не удалось повторить проверку. Ваши ответы сохранены; попробуйте позже.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="grid min-w-0 gap-6 lg:grid-cols-[minmax(260px,360px)_minmax(0,1fr)]">
        <section aria-labelledby={`${prefix}-scenario`} className="min-w-0 space-y-4">
          <h2 id={`${prefix}-scenario`} className="text-xl font-bold">{assigned ? 'Назначенное задание' : 'Ваш скриншот: только обратная связь'}</h2>
          <p className="whitespace-pre-wrap text-ink-secondary">{audit.scenario}</p>
          <figure className="rounded-xl border border-ink/15 bg-white p-3">
            <img alt={assigned ? 'Скриншот интерфейса назначенного задания для UX-аудита' : 'Загруженный вами интерфейс для обратной связи'} className="mx-auto h-auto max-h-[650px] max-w-full object-contain" src={audit.screenshot_data_url} />
            <figcaption className="mt-3 text-caption text-ink-secondary">Опирайтесь на то, что видно на макете.</figcaption>
          </figure>
        </section>
        <form onSubmit={(event) => { void submit(event) }} className="min-w-0 space-y-4">
          <fieldset disabled={busy || completed} className="min-w-0 space-y-3">
            <legend className="mb-2 text-xl font-bold">{completed ? 'Ваши ответы' : 'Отметьте найденные нарушения'}</legend>
            {!completed && <p className="mb-4 text-ink-secondary">Выбирайте только те принципы, нарушение которых можете обосновать. Для каждого ответа заполните все поля.</p>}
            {audit.checklist.map((item) => {
              const copy = heuristicCopy[item.id]
              const violation = shownViolations.find((entry) => entry.heuristic_id === item.id)
              const id = `${prefix}-${item.id}`
              return (
                <div key={item.id} className="rounded-xl border border-ink/15 bg-white p-4 sm:p-5">
                  <label className="flex cursor-pointer items-start gap-3" htmlFor={id}>
                    <input id={id} type="checkbox" className="mt-1 h-5 w-5 shrink-0 accent-pvn-blue" checked={violation !== undefined} onChange={(event) => {
                      setError(null)
                      setViolations((previous) => event.target.checked
                        ? [...previous, { heuristic_id: item.id, evidence: '', rationale: '', severity: 'medium', recommendation: '' }]
                        : previous.filter((entry) => entry.heuristic_id !== item.id))
                    }} />
                    <span><span className="block font-semibold">{copy.title}</span><span className="mt-1 block text-caption text-ink-secondary">{copy.question}</span></span>
                  </label>
                  {violation && (
                    <div className="mt-4 space-y-4">
                      <div>
                        <label htmlFor={`${id}-evidence`} className="mb-1 block font-semibold">Доказательство на скриншоте</label>
                        <p id={`${id}-hint`} className="mb-2 text-caption text-ink-secondary">{copy.hint}</p>
                        <textarea id={`${id}-evidence`} aria-describedby={`${id}-hint`} className={inputClass} rows={3} required minLength={5} maxLength={1000} value={violation.evidence} onChange={(event) => updateViolation(item.id, { evidence: event.target.value })} />
                      </div>
                      <div>
                        <label htmlFor={`${id}-rationale`} className="mb-1 block font-semibold">Почему это мешает пользователю</label>
                        <textarea id={`${id}-rationale`} className={inputClass} rows={3} required minLength={10} maxLength={2000} placeholder="Свяжите проблему со сценарием и объясните выбранную критичность." value={violation.rationale} onChange={(event) => updateViolation(item.id, { rationale: event.target.value })} />
                      </div>
                      <div>
                        <label htmlFor={`${id}-severity`} className="mb-1 block font-semibold">Критичность</label>
                        <select id={`${id}-severity`} className={inputClass} value={violation.severity} onChange={(event) => updateViolation(item.id, { severity: event.target.value as SelectedViolation['severity'] })}>
                          {Object.entries(severityLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                        </select>
                      </div>
                      <div>
                        <label htmlFor={`${id}-recommendation`} className="mb-1 block font-semibold">Что изменить и как проверить</label>
                        <textarea id={`${id}-recommendation`} className={inputClass} rows={3} required minLength={10} maxLength={1000} value={violation.recommendation} onChange={(event) => updateViolation(item.id, { recommendation: event.target.value })} />
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </fieldset>
          {error && <p role="alert" className="text-pvn-red-ink">{error}</p>}
          {!completed && (
            <div className="space-y-3">
              <p className="text-caption text-ink-secondary">После отправки ответы нельзя изменить. Черновик не сохраняется при уходе со страницы.</p>
              <button className={buttonClass} type="submit" disabled={busy}>{busy ? 'Проверяем аргументацию...' : assigned ? 'Отправить аудит задания' : 'Получить обратную связь'}</button>
              {busy && <p role="status" className="text-caption text-ink-secondary">Проверка может занять до 20 секунд. Дождитесь результата.</p>}
            </div>
          )}
        </form>
      </div>
      {completed && (
        <section aria-labelledby={`${prefix}-result`} aria-live="polite" className="space-y-4 border-t border-ink/15 pt-6">
          <h2 id={`${prefix}-result`} className="text-xl font-bold">Результат аудита</h2>
          {evaluation ? (
            <>
              <p className="font-semibold">Аргументация по рубрике: {evaluation.score.toLocaleString('ru-RU')} / 100</p>
              <p className="text-ink-secondary">{evaluation.summary}</p>
              <dl className="divide-y divide-ink/10">
                {evaluation.criteria.map((criterion) => (
                  <div key={criterion.id} className="py-3">
                    <dt className="font-semibold">{criterionLabels[criterion.id]}: {criterion.score} / 4</dt>
                    <dd className="mt-1 whitespace-pre-wrap text-ink-secondary">{criterion.feedback}</dd>
                  </div>
                ))}
              </dl>
              <div className="space-y-2 rounded-xl bg-inset p-4">
                <p className="font-semibold">{assigned && evaluation.testing_score !== null
                  ? `Результат по эталону дефектов: ${(evaluation.testing_score * 100).toLocaleString('ru-RU', { maximumFractionDigits: 2 })} / 100`
                  : assigned ? 'Результат задания не засчитан' : 'Личная загрузка не учитывается в тестировании'}</p>
                {assigned && evaluation.reference_coverage !== null && evaluation.reference_coverage !== undefined && (
                  <p className="text-caption text-ink-secondary">Найдено нарушений из эталона: {(evaluation.reference_coverage * 100).toLocaleString('ru-RU', { maximumFractionDigits: 0 })}%.</p>
                )}
                <p className="text-caption text-ink-secondary">{assigned && evaluation.testing_score !== null ? 'Балл — за находки из списка и их обоснование.' : assigned ? 'Доступна только обратная связь по заполненности ответов. Для этой проверки не получен результат, который можно учитывать в тестировании.' : 'Это обратная связь по вашему сценарию, а не оценка назначенного задания.'}</p>
                {assigned && evaluation.missed_defects && evaluation.missed_defects.length > 0 && (
                  <div className="text-caption text-ink-secondary">
                    <p className="font-semibold">Что осталось без внимания:</p>
                    <ul className="mt-1 list-disc space-y-1 pl-5">
                      {evaluation.missed_defects.map((item) => <li key={item}>{item}</li>)}
                    </ul>
                  </div>
                )}
                <p className="text-caption text-ink-secondary">{evaluation.evidence_mode === 'image_and_text'
                  ? 'Проверка сделана по скриншоту и тексту. Размеры и контраст не измерены. Грейд не меняется.'
                  : 'Проверка сделана по тексту ответа. Размеры и контраст не измерены. Грейд не меняется.'}</p>
                {evaluation.source === 'deterministic' && <p className="text-caption text-ink-secondary">Резервная проверка зависит от длины текста и не подтверждает правильность найденных нарушений.</p>}
                {retryable && <div className="space-y-2">
                  <p className="text-caption text-ink-secondary">Повторная проверка использует те же сохранённые ответы. Изменить их после отправки нельзя.</p>
                  <button type="button" className={buttonClass} disabled={busy} onClick={() => { void retryEvaluation() }}>{busy ? 'Повторно проверяем...' : 'Повторить проверку ответов'}</button>
                  {error && <p role="alert" className="text-pvn-red-ink">{error}</p>}
                </div>}
                <details className="text-caption text-ink-secondary"><summary className="cursor-pointer font-semibold">Ограничения проверки</summary><p className="mt-2 whitespace-pre-wrap">{evaluation.limitation}</p></details>
              </div>
            </>
          ) : <p role="status">Аудит отправлен, но результат пока недоступен. Обновите страницу, чтобы проверить сохранённый результат.</p>}
        </section>
      )}
    </div>
  )
}

export function CandidateDesignerAuditPage() {
  const [assigned, setAssigned] = useState<DesignerAudit | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [retry, setRetry] = useState(0)
  const [ownAudit, setOwnAudit] = useState<DesignerAudit | null>(null)
  const [screenshot, setScreenshot] = useState<File | null>(null)
  const [scenario, setScenario] = useState('')
  const [uploadBusy, setUploadBusy] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [portfolioFile, setPortfolioFile] = useState<File | null>(null)
  const [portfolio, setPortfolio] = useState<PortfolioMetrics | null>(null)
  const [portfolioBusy, setPortfolioBusy] = useState(false)
  const [portfolioError, setPortfolioError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    fetchAssignedDesignerAudit().then((audit) => { if (active) setAssigned(audit) }).catch((exception) => {
      if (active) setLoadError(auditError(exception, 'Не удалось загрузить назначенное задание. Попробуйте ещё раз.'))
    }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [retry])

  useEffect(() => {
    let active = true
    fetchDesignerPortfolio().then((result) => { if (active) setPortfolio(result) }).catch(() => {
      if (active) setPortfolioError('Не удалось загрузить сохранённые данные портфолио. Новая загрузка PDF остаётся доступной.')
    })
    return () => { active = false }
  }, [])

  async function uploadScreenshot(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (uploadBusy) return
    if (!screenshot || !['image/png', 'image/jpeg', 'image/webp'].includes(screenshot.type) || screenshot.size > 2 * 1024 * 1024 || screenshot.size === 0) {
      setUploadError('Выберите непустой PNG, JPEG или WebP размером до 2 МБ.')
      return
    }
    if (scenario.trim().length < 10) {
      setUploadError('Опишите сценарий минимум в 10 символах без учёта пробелов по краям.')
      return
    }
    setUploadBusy(true)
    setUploadError(null)
    try { setOwnAudit(await uploadDesignerScreenshot(screenshot, scenario.trim())) }
    catch (exception) { setUploadError(auditError(exception, 'Не удалось загрузить скриншот. Проверьте соединение и попробуйте ещё раз.')) }
    finally { setUploadBusy(false) }
  }

  async function uploadPortfolio(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (portfolioBusy) return
    if (!portfolioFile || !/\.pdf$/i.test(portfolioFile.name) || portfolioFile.size > 5 * 1024 * 1024 || portfolioFile.size === 0) {
      setPortfolioError('Выберите непустой PDF размером до 5 МБ с выделяемым текстом.')
      return
    }
    setPortfolioBusy(true)
    setPortfolioError(null)
    try { setPortfolio(await uploadDesignerPortfolio(portfolioFile)) }
    catch (exception) { setPortfolioError(auditError(exception, 'Не удалось извлечь метрики. Проверьте соединение и попробуйте ещё раз.')) }
    finally { setPortfolioBusy(false) }
  }

  return (
    <div className="mx-auto max-w-[1120px] space-y-8 px-4 py-8 sm:px-6">
      <header className="space-y-2">
        <h1 className="text-3xl font-bold">UX-аудит</h1>
        <p className="max-w-3xl text-ink-secondary">Найдите проблемы в интерфейсе и объясните, как их исправить.</p>
      </header>
      {loading && <p role="status">Загружаем ваше задание и сохранённый результат...</p>}
      {loadError && <div className="space-y-3"><p role="alert" className="text-pvn-red-ink">{loadError}</p><button type="button" className={buttonClass} disabled={loading} onClick={() => { setLoadError(null); setLoading(true); setRetry((value) => value + 1) }}>Загрузить задание снова</button></div>}
      {assigned && <AuditWorkspace key={assigned.id} audit={assigned} onUpdated={setAssigned} />}
      <details className="border-t border-ink/15 pt-6">
        <summary className="cursor-pointer text-xl font-bold">Дополнительно: свой скриншот</summary>
        <div className="mt-4 space-y-5">
          <p className="text-ink-secondary">Загрузите свой макет и разберите его тем же чек-листом. На результат тестирования это не влияет.</p>
          {ownAudit ? <AuditWorkspace key={ownAudit.id} audit={ownAudit} onUpdated={setOwnAudit} /> : (
            <form className="max-w-2xl space-y-4" onSubmit={(event) => { void uploadScreenshot(event) }}>
              <div><label className="mb-2 block font-semibold" htmlFor="own-screenshot">Скриншот интерфейса</label><input id="own-screenshot" className={inputClass} type="file" accept="image/png,image/jpeg,image/webp" required disabled={uploadBusy} onChange={(event) => setScreenshot(event.target.files?.[0] ?? null)} /><p className="mt-2 text-caption text-ink-secondary">PNG, JPEG или WebP, до 2 МБ и 16 млн пикселей.</p></div>
              <div><label className="mb-2 block font-semibold" htmlFor="own-scenario">Сценарий пользователя</label><textarea id="own-scenario" className={inputClass} rows={3} required minLength={10} maxLength={4000} disabled={uploadBusy} value={scenario} onChange={(event) => setScenario(event.target.value)} placeholder="Кто пользуется интерфейсом и какую задачу решает?" /></div>
              {uploadError && <p role="alert" className="text-pvn-red-ink">{uploadError}</p>}
              <button className={buttonClass} type="submit" disabled={uploadBusy}>{uploadBusy ? 'Загружаем скриншот...' : 'Загрузить для обратной связи'}</button>
            </form>
          )}
        </div>
      </details>
      <details className="border-t border-ink/15 pt-6">
        <summary className="cursor-pointer text-xl font-bold">PDF-портфолио: заявленные метрики</summary>
        <div className="mt-4 space-y-4">
          <p className="max-w-3xl text-ink-secondary">Из PDF соберём заявленные метрики в профиль. Это ваши данные, другие их не проверяют.</p>
          <form className="max-w-2xl space-y-3" onSubmit={(event) => { void uploadPortfolio(event) }}>
            <label className="block font-semibold" htmlFor="portfolio-pdf">PDF-портфолио</label>
            <input id="portfolio-pdf" className={inputClass} type="file" accept="application/pdf,.pdf" required disabled={portfolioBusy} onChange={(event) => setPortfolioFile(event.target.files?.[0] ?? null)} />
            <p className="text-caption text-ink-secondary">До 5 МБ. Сканированные страницы без текстового слоя не поддерживаются. Новая загрузка заменит ранее извлечённые данные.</p>
            {portfolioError && <p role="alert" className="text-pvn-red-ink">{portfolioError}</p>}
            <button type="submit" className={buttonClass} disabled={portfolioBusy}>{portfolioBusy ? 'Извлекаем метрики...' : 'Извлечь метрики из PDF'}</button>
          </form>
          {portfolio && <section aria-live="polite" className="space-y-3">
            <h2 className="text-lg font-bold">Заявления автора, не проверены</h2>
            {portfolio.metrics.length === 0 ? <p>Численные метрики не найдены. Это не означает, что в портфолио нет результатов: распознавание ограничено текстовым слоем и поддерживаемыми названиями метрик.</p> : (
              <ul className="divide-y divide-ink/10">{portfolio.metrics.map((metric, index) => <li key={`${metric.metric}-${index}`} className="py-3"><p className="font-semibold">{metric.metric}: {metric.value}</p><blockquote className="mt-1 whitespace-pre-wrap break-words text-ink-secondary">{metric.evidence}</blockquote></li>)}</ul>
            )}
            <p className="text-caption text-ink-secondary">Рассматриваются только первые 20 000 символов выделяемого текста; поддерживаются английские названия метрик. Достоверность и связь цифр с работой автора требуют проверки.</p>
            <details className="text-caption text-ink-secondary"><summary className="cursor-pointer font-semibold">Ограничения извлечения</summary><p className="mt-2">{portfolio.limitation}</p></details>
          </section>}
        </div>
      </details>
    </div>
  )
}
