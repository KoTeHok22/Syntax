import { execFileSync } from 'node:child_process'
import { expect, test, type Page } from '@playwright/test'

const runId = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
const password = `Pass-${runId}!`
const candidateEmail = `e2e.newcore.candidate.${runId}@syntax.dev`
const employerEmail = `e2e.newcore.employer.${runId}@syntax.dev`
const companyName = `Новая команда ${runId}`
const vacancyTitle = `Semantic UX Backend ${runId}`

test.use({ actionTimeout: 20_000, video: 'on', viewport: { width: 1440, height: 1000 } })

async function createAccount(page: Page, role: 'candidate' | 'employer', email: string) {
  const registered = await page.request.post('http://localhost:8000/auth/register', {
    data: { email, password, role, consent_accepted: true, ...(role === 'candidate' ? { specialization: 'design', grade: 'junior' } : {}) },
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
  const sql = `BEGIN; DELETE FROM applications WHERE candidate_profile_id IN (${candidates}) OR vacancy_id IN (${vacancies}); DELETE FROM invitations WHERE candidate_profile_id IN (${candidates}) OR employer_profile_id IN (${employers}); DELETE FROM vacancies WHERE employer_profile_id IN (${employers}); DELETE FROM company_offices WHERE employer_profile_id IN (${employers}); DELETE FROM candidate_profiles WHERE user_id IN (${users}); DELETE FROM employer_profiles WHERE user_id IN (${users}); DELETE FROM users WHERE email IN ('${candidateEmail}', '${employerEmail}'); COMMIT;`
  execFileSync('docker', ['exec', 'syntax-db-1', 'psql', '-U', 'syntax', '-d', 'syntax', '-v', 'ON_ERROR_STOP=1', '-c', sql], { stdio: 'pipe' })
}

async function assertNoHorizontalOverflow(page: Page) {
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
}

test.describe('новые ключевые UI-потоки', () => {
  test.afterAll(cleanupAccounts)
  test('кандидат-дизайнер редактирует профиль и проходит тестирование на desktop и mobile', async ({ page }) => {
    test.setTimeout(240_000)
    await createAccount(page, 'candidate', candidateEmail)

    await page.goto('/candidate')
    await page.getByRole('button', { name: 'Редактировать' }).click()
    await page.locator('#profile-full-name').fill('Новый дизайнер')
    await expect(page.locator('#profile-specialization option', { hasText: 'Дизайн' })).toHaveCount(1)
    await page.locator('#profile-specialization').selectOption('design')
    await page.locator('#profile-stack').fill('Figma, Design Systems, Accessibility')
    await page.locator('#profile-years').fill('4')
    await page.locator('#profile-email').fill(`candidate-${runId}@syntax.dev`)
    await page.locator('#profile-phone').fill('+7 900 123-45-67')
    await page.getByRole('button', { name: 'Сохранить профиль' }).click()
    await expect(page.getByText('Новый дизайнер')).toBeVisible()

    await page.goto('/candidate/testing')
    await expect(page.getByRole('heading', { name: 'Тестирование и подтверждение грейда' })).toBeVisible()
    await page.getByRole('button', { name: /Junior/ }).click()
    await page.getByRole('button', { name: 'Начать тестирование' }).click()
    await page.getByRole('checkbox', { name: /ознакомлен/ }).check()
    const startedSession = page.waitForResponse((response) => response.url().endsWith('/test-sessions') && response.request().method() === 'POST', { timeout: 120_000 })
    await page.getByRole('button', { name: 'Согласен, начать тест' }).click()
    const sessionResponse = await startedSession
    expect(sessionResponse.ok()).toBe(true)
    const session = await sessionResponse.json()
    expect(session.tasks.length).toBeGreaterThan(0)
    await expect(page.getByText('ВОПРОС 1')).toBeVisible({ timeout: 30_000 })
    await assertNoHorizontalOverflow(page)

    await page.setViewportSize({ width: 380, height: 844 })
    await page.goto('/candidate')
    await assertNoHorizontalOverflow(page)
    await page.getByRole('button', { name: 'Меню', exact: true }).click()
    await expect(page.getByRole('link', { name: 'UX-аудит', exact: true })).toHaveCount(0)
    await page.getByRole('link', { name: 'Тестирование', exact: true }).click()
    await expect(page).toHaveURL(/\/candidate\/testing$/)
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
