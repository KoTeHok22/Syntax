import { execFileSync } from 'node:child_process'
import { expect, test, type Page } from '@playwright/test'

const runId = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
const password = `Pass-${runId}!`
const candidateEmail = `e2e.newcore.candidate.${runId}@syntax.dev`
const employerEmail = `e2e.newcore.employer.${runId}@syntax.dev`
const companyName = `Новая команда ${runId}`
const vacancyTitle = `Semantic UX Backend ${runId}`

test.use({ actionTimeout: 20_000, video: 'on', viewport: { width: 1440, height: 1000 } })

const portfolioPdf = (() => {
  const stream = 'BT\n/F1 18 Tf\n72 720 Td\n(Conversion rate 42%, retention 31.5%, onboarding completion 88%, time to task 12 seconds, 24 participants) Tj\nET\n'
  const objects = [
    '<< /Type /Catalog /Pages 2 0 R >>',
    '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>',
    `<< /Length ${Buffer.byteLength(stream)} >>\nstream\n${stream}endstream`,
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
  ]
  let pdf = '%PDF-1.4\n'
  const offsets: number[] = []
  objects.forEach((object, index) => {
    offsets.push(Buffer.byteLength(pdf))
    pdf += `${index + 1} 0 obj\n${object}\nendobj\n`
  })
  const xref = Buffer.byteLength(pdf)
  pdf += `xref\n0 6\n0000000000 65535 f \n${offsets.map((offset) => `${String(offset).padStart(10, '0')} 00000 n \n`).join('')}trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`
  return Buffer.from(pdf)
})()

async function createAccount(page: Page, role: 'candidate' | 'employer', email: string) {
  const registered = await page.request.post('http://localhost:8000/auth/register', {
    data: { email, password, role, consent_accepted: true, ...(role === 'candidate' ? { specialization: 'backend', grade: 'junior' } : {}) },
  })
  expect(registered.status()).toBe(201)
  const account = await registered.json()
  expect(account.confirmation_url).toBeTruthy()
  const confirmed = await page.request.get(account.confirmation_url)
  expect(confirmed.ok()).toBe(true)
  await page.goto('/login')
  await page.locator('#user-email').fill(email)
  await page.locator('#user-password').fill(password)
  await page.getByRole('button', { name: /^Войти/ }).click()
  await expect(page).toHaveURL(role === 'candidate' ? /\/candidate$/ : /\/employer$/)
}

function cleanupAccounts() {
  const users = `SELECT id FROM users WHERE email IN ('${candidateEmail}', '${employerEmail}')`
  const candidates = `SELECT id FROM candidate_profiles WHERE user_id IN (${users})`
  const employers = `SELECT id FROM employer_profiles WHERE user_id IN (${users})`
  const vacancies = `SELECT id FROM vacancies WHERE employer_profile_id IN (${employers})`
  const sql = `BEGIN; DELETE FROM designer_audits WHERE candidate_profile_id IN (${candidates}); DELETE FROM applications WHERE candidate_profile_id IN (${candidates}) OR vacancy_id IN (${vacancies}); DELETE FROM invitations WHERE candidate_profile_id IN (${candidates}) OR employer_profile_id IN (${employers}); DELETE FROM vacancies WHERE employer_profile_id IN (${employers}); DELETE FROM company_offices WHERE employer_profile_id IN (${employers}); DELETE FROM candidate_profiles WHERE user_id IN (${users}); DELETE FROM employer_profiles WHERE user_id IN (${users}); DELETE FROM users WHERE email IN ('${candidateEmail}', '${employerEmail}'); COMMIT;`
  execFileSync('docker', ['exec', 'syntax-db-1', 'psql', '-U', 'syntax', '-d', 'syntax', '-v', 'ON_ERROR_STOP=1', '-c', sql], { stdio: 'pipe' })
}

async function assertNoHorizontalOverflow(page: Page) {
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
}

test.describe('новые ключевые UI-потоки', () => {
  test.afterAll(cleanupAccounts)
  test('кандидат проходит назначенный аудит, загрузку скриншота и PDF на desktop и mobile', async ({ page }) => {
    test.setTimeout(420_000)
    await createAccount(page, 'candidate', candidateEmail)

    await page.goto('/candidate')
    await page.getByRole('button', { name: 'Редактировать' }).click()
    await page.locator('#profile-full-name').fill('Новый кандидат')
    await page.locator('#profile-specialization').selectOption('backend')
    await page.locator('#profile-stack').fill('Python, FastAPI, PostgreSQL')
    await page.locator('#profile-years').fill('4')
    await page.locator('#profile-email').fill(`candidate-${runId}@syntax.dev`)
    await page.locator('#profile-phone').fill('+7 900 123-45-67')
    await page.getByRole('button', { name: 'Сохранить профиль' }).click()
    await expect(page.getByText('Новый кандидат')).toBeVisible()

    await page.goto('/candidate/designer-audit')
    await expect(page.getByRole('heading', { name: 'UX-аудит' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Назначенное задание' })).toBeVisible({ timeout: 30_000 })
    await page.locator('input[type="checkbox"]').first().check()
    const evidence = page.locator('textarea').nth(0)
    const rationale = page.locator('textarea').nth(1)
    const recommendation = page.locator('textarea').nth(2)
    await evidence.fill('Красный баннер занимает экран и скрывает итоговую сумму заказа.')
    await rationale.fill('Пользователь не может быстро проверить стоимость перед оплатой в сценарии покупки.')
    await recommendation.fill('Уменьшить баннер и показать итог рядом с кнопкой оплаты, затем проверить на телефоне.')
    const submittedAudit = page.waitForResponse((response) => /\/designer-audits\/\d+\/submit$/.test(response.url()) && response.request().method() === 'POST', { timeout: 90_000 })
    await page.getByRole('button', { name: 'Отправить аудит задания' }).click()
    const auditResponse = await submittedAudit
    expect(auditResponse.ok()).toBe(true)
    const audit = await auditResponse.json()
    expect(audit.status).toBe('submitted')
    expect(audit.checklist).toHaveLength(7)
    test.info().annotations.push({ type: 'live-audit-source', description: audit.evaluation?.source ?? 'unavailable' })
    console.log(`Live assigned audit: ${audit.evaluation.source}`)
    await expect(page.getByRole('heading', { name: 'Результат аудита' })).toBeVisible({ timeout: 300_000 })
    await expect(page.getByText(/Аргументация по рубрике|Аудит отправлен, но результат пока недоступен/)).toBeVisible({ timeout: 30_000 })
    const retryAudit = page.getByRole('button', { name: 'Повторить проверку ответов' })
    if (await retryAudit.isVisible()) {
      expect(audit.evaluation.testing_score).toBeNull()
      await expect(page.getByText('Результат задания не засчитан', { exact: true })).toBeVisible()
      const retriedAudit = page.waitForResponse((response) => /\/designer-audits\/\d+\/submit$/.test(response.url()) && response.request().method() === 'POST', { timeout: 90_000 })
      await retryAudit.click()
      const retryResponse = await retriedAudit
      expect(retryResponse.ok()).toBe(true)
      const retryResult = await retryResponse.json()
      expect(retryResult.violations).toEqual(audit.violations)
      await expect(page.getByRole('button', { name: 'Проверяем аргументацию...' })).not.toBeVisible({ timeout: 30_000 })
      test.info().annotations.push({ type: 'live-audit-retry', description: retryResult.evaluation.source })
      console.log(`Live saved-answer retry: ${retryResult.evaluation.source}`)
      const changedAnswers = await page.request.post(retryResponse.url(), {
        headers: { Authorization: retryResponse.request().headers().authorization },
        data: { violations: retryResult.violations.map((violation: { rationale: string }) => ({ ...violation, rationale: 'Изменённые ответы после обратной связи не должны быть приняты.' })) },
      })
      expect(changedAnswers.status()).toBe(409)
    }

    const screenshotPng = await page.getByRole('img', { name: 'Скриншот интерфейса назначенного задания для UX-аудита' }).screenshot()
    await page.getByText('Свой скриншот: необязательная обратная связь').click()
    await page.locator('#own-screenshot').setInputFiles({ name: 'own-screen.png', mimeType: 'image/png', buffer: screenshotPng })
    await page.locator('#own-scenario').fill('Клиент выбирает товар и оформляет заказ на телефоне.')
    await page.getByRole('button', { name: 'Загрузить для обратной связи' }).click()
    await expect(page.getByRole('heading', { name: 'Ваш скриншот: только обратная связь' })).toBeVisible({ timeout: 30_000 })
    await expect(page.getByRole('region', { name: 'Ваш скриншот: только обратная связь' }).getByText('Оценивайте видимые элементы в контексте сценария')).toBeVisible()
    const ownDetails = page.locator('details').filter({ has: page.locator('summary', { hasText: 'Свой скриншот: необязательная обратная связь' }) })
    await ownDetails.getByRole('checkbox').first().check()
    await ownDetails.getByLabel('Доказательство на скриншоте', { exact: true }).fill('На скриншоте недостаточно информации для уверенного вывода.')
    await ownDetails.getByLabel('Почему это мешает пользователю', { exact: true }).fill('Пользователь не видит состояние заказа и не может подтвердить действие.')
    await ownDetails.getByLabel('Что изменить и как проверить', { exact: true }).fill('Показать содержимое заказа и проверить понятность состояния с пользователями.')
    const ownSubmitted = page.waitForResponse((response) => /\/designer-audits\/\d+\/submit$/.test(response.url()) && response.request().method() === 'POST', { timeout: 90_000 })
    await ownDetails.getByRole('button', { name: 'Получить обратную связь' }).click()
    const ownResponse = await ownSubmitted
    expect(ownResponse.ok()).toBe(true)
    expect((await ownResponse.json()).evaluation.testing_score).toBeNull()
    await expect(ownDetails.getByText('Личная загрузка не учитывается в тестировании', { exact: true })).toBeVisible()
    await assertNoHorizontalOverflow(page)

    await page.getByText('PDF-портфолио: заявленные метрики').click()
    await page.locator('#portfolio-pdf').setInputFiles({ name: 'portfolio.pdf', mimeType: 'application/pdf', buffer: portfolioPdf })
    const extractedPortfolio = page.waitForResponse((response) => response.url().endsWith('/designer-audits/portfolio') && response.request().method() === 'POST')
    await page.getByRole('button', { name: 'Извлечь метрики из PDF' }).click()
    const portfolioResponse = await extractedPortfolio
    expect(portfolioResponse.ok()).toBe(true)
    const portfolio = await portfolioResponse.json()
    expect(portfolio.metrics.length).toBeGreaterThan(0)
    await expect(page.getByRole('heading', { name: 'Заявления автора, не проверены' })).toBeVisible({ timeout: 30_000 })
    await expect(page.getByText(/conversion|retention|onboarding|time|participants/i).first()).toBeVisible()
    await expect(page.getByText('Достоверность и связь цифр с работой автора требуют проверки.', { exact: false })).toBeVisible()

    await page.setViewportSize({ width: 380, height: 844 })
    await page.goto('/candidate')
    await assertNoHorizontalOverflow(page)
    await page.getByRole('button', { name: 'Меню', exact: true }).click()
    await expect(page.getByRole('link', { name: 'UX-аудит', exact: true })).toBeVisible()
    await page.getByRole('link', { name: 'UX-аудит', exact: true }).click()
    await expect(page).toHaveURL(/\/candidate\/designer-audit$/)
    await expect(page.getByRole('heading', { name: 'Результат аудита' })).toBeVisible({ timeout: 30_000 })
    await page.getByText('PDF-портфолио: заявленные метрики').click()
    await expect(page.getByRole('heading', { name: 'Заявления автора, не проверены' })).toBeVisible()
    await assertNoHorizontalOverflow(page)
  })

  test('работодатель использует semantic search, видит недоступный ATS и получает antifraud rejection', async ({ page }) => {
    test.setTimeout(420_000)
    await createAccount(page, 'employer', employerEmail)

    const atsConfigurationResponse = page.waitForResponse((response) => response.url().endsWith('/ats/config') && response.request().method() === 'GET')
    await page.goto('/employer/company')
    const atsResponse = await atsConfigurationResponse
    expect(atsResponse.ok()).toBe(true)
    const ats = await atsResponse.json()
    expect(ats.available).toBe(false)
    expect(ats.configured).toBe(false)
    expect(ats.available_webhook_urls).toEqual([])
    await page.getByPlaceholder('ООО «ТехноСфера»').fill(companyName)
    await page.getByPlaceholder(/Продуктовая компания/).fill(`Продуктовая команда ${runId}`)
    await page.getByPlaceholder('hr@company.ru').fill(`hr-${runId}@e2e.corp`)
    await page.getByPlaceholder('+7 900 000-00-00').fill('+7 900 123-45-67')
    await page.getByRole('button', { name: /Сохранить$/ }).click()
    await expect(page.getByText('Профиль компании сохранён')).toBeVisible({ timeout: 30_000 })
    await expect(page.getByRole('heading', { name: 'Подключение ATS' })).toBeVisible()
    await expect(page.getByText('Доступных подключений пока нет. Обратитесь к администратору.')).toBeVisible({ timeout: 30_000 })
    await expect(page.locator('#ats-webhook-url option')).toHaveCount(1)
    await expect(page.locator('#ats-webhook-url')).toHaveValue('')
    await assertNoHorizontalOverflow(page)

    await page.goto('/employer/vacancies')
    await page.getByRole('button', { name: 'Опубликовать вакансию' }).click()
    const modal = page.locator('div.fixed')
    await modal.locator('#vacancy-title').fill(vacancyTitle)
    await modal.locator('#vacancy-spec').selectOption('backend')
    await modal.locator('#vacancy-grade').selectOption('middle')
    await modal.locator('#vacancy-stack').fill('Python, FastAPI, PostgreSQL')
    await modal.locator('input[placeholder="220 000"]').fill('180000')
    await modal.locator('input[placeholder="290 000"]').fill('260000')
    await modal.locator('#vacancy-description').fill('Разработка API для продукта, работа с данными и устойчивыми сервисами.')
    await modal.getByRole('button', { name: 'Опубликовать вакансию' }).click()
    await expect(page.getByText(`Вакансия «${vacancyTitle}» опубликована`)).toBeVisible({ timeout: 30_000 })

    await page.goto('/employer/search')
    await expect(page.locator('#search-vacancy')).toContainText(vacancyTitle, { timeout: 30_000 })
    const searchResponse = page.waitForResponse((response) => response.url().includes('/employer/search?') && new URL(response.url()).searchParams.has('vacancy_id'), { timeout: 180_000 })
    await page.locator('#search-vacancy').selectOption({ label: vacancyTitle })
    const selectedSearch = await searchResponse
    expect(selectedSearch.ok()).toBe(true)
    const searchCards = await selectedSearch.json()
    expect(searchCards.length).toBeGreaterThan(0)
    test.info().annotations.push({ type: 'live-matching-mode', description: searchCards[0].match_breakdown.mode })
    console.log(`Live vacancy matching: ${searchCards[0].match_breakdown.mode}`)
    await expect(page.getByText('Совпадение с вакансией').first()).toBeVisible({ timeout: 60_000 })
    await page.getByText('Как рассчитано совпадение').first().click()
    await expect(page.getByText(/Сравнение по смыслу|Сравниваем технологии/).first()).toBeVisible()
    await expect(page.locator('article').first().getByText(`${Math.round(searchCards[0].match_relevance * 100)}%`, { exact: true })).toBeVisible()
    await expect(page.locator('article').first().getByText(`Итог для сортировки: оценка ПВН × совпадение = ${searchCards[0].final_score} / 100.`, { exact: false })).toBeVisible()
    await assertNoHorizontalOverflow(page)

    await page.goto('/employer/vacancies')
    await page.getByRole('button', { name: 'Опубликовать вакансию' }).click()
    const rejectedModal = page.locator('div.fixed')
    await rejectedModal.locator('#vacancy-title').fill(`Blocked offer ${runId}`)
    await rejectedModal.locator('#vacancy-spec').selectOption('backend')
    await rejectedModal.locator('#vacancy-grade').selectOption('middle')
    await rejectedModal.locator('#vacancy-stack').fill('Python')
    await rejectedModal.locator('input[placeholder="220 000"]').fill('100000')
    await rejectedModal.locator('input[placeholder="290 000"]').fill('120000')
    await rejectedModal.locator('#vacancy-description').fill('Оплатите регистрацию и обучение до трудоустройства. Переведите деньги на карту для получения вакансии.')
    const rejection = page.waitForResponse((response) => response.url().endsWith('/vacancies') && response.request().method() === 'POST', { timeout: 90_000 })
    await rejectedModal.getByRole('button', { name: 'Опубликовать вакансию' }).click()
    const rejectedResponse = await rejection
    expect(rejectedResponse.status()).toBe(422)
    const rejected = await rejectedResponse.json()
    await expect(rejectedModal.getByText(rejected.detail, { exact: true })).toBeVisible({ timeout: 60_000 })

    await page.setViewportSize({ width: 380, height: 844 })
    await page.goto('/employer/search')
    await assertNoHorizontalOverflow(page)
    await page.getByRole('button', { name: 'Меню', exact: true }).click()
    await expect(page.getByRole('link', { name: 'Вакансии', exact: true })).toBeVisible()
    await page.getByRole('link', { name: 'Вакансии', exact: true }).click()
    await expect(page).toHaveURL(/\/employer\/vacancies$/)
    await assertNoHorizontalOverflow(page)
  })
})
