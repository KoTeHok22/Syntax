import { expect, test } from '@playwright/test'
import { fetchDemoCandidateInfo, login, registerAndConfirmAndLogin } from './helpers'

test.describe.serial('полный сценарий ПВН', () => {
  test('кандидат и работодатель от регистрации до оффера', async ({ page }) => {
    test.setTimeout(420_000)
    const runId = Number(process.env.E2E_RUN_ID ?? Date.now())
    const candidateEmail = `e2e.candidate.${runId}@syntax.dev`
    const employerEmail = `e2e.employer.${runId}@syntax.dev`
    const password = `Pass-${runId}!`
    const companyName = `Атлас Кадр ${runId}`
    const vacancyTitle = `Backend Developer ${runId}`
    const vacancyTitleEdited = `${vacancyTitle} v2`
    const taskStatement = `Проверочное задание ${runId}: выберите вариант А`
    const demo = await fetchDemoCandidateInfo()
    const demoAnonId = `#${demo.profileId.toString(16).toUpperCase().padStart(4, '0')}`

    await registerAndConfirmAndLogin(page, 'candidate', candidateEmail, password)
    await expect(page.getByRole('heading', { name: 'Профиль кандидата' })).toBeVisible()

    await page.getByRole('button', { name: 'Редактировать' }).click()
    await page.locator('#profile-full-name').fill('Иванов Иван')
    await page.locator('#profile-specialization').selectOption('backend')
    await page.locator('#profile-stack').fill('Python, FastAPI, PostgreSQL')
    await page.locator('#profile-years').fill('3')
    await page.locator('#profile-email').fill(`candidate-${runId}@syntax.dev`)
    await page.locator('#profile-phone').fill('+7 900 555-66-77')
    await page.getByRole('button', { name: 'Сохранить профиль' }).click()
    await expect(page.getByText('Иванов Иван')).toBeVisible()
    await expect(page.getByText(/Кандидат · Backend/)).toBeVisible()
    await expect(page.getByText('Python', { exact: true }).first()).toBeVisible()
    await expect(page.getByText('3 года').first()).toBeVisible()

    await page.goto('/candidate/testing')
    await page.getByRole('button', { name: 'Junior' }).click()
    await page.getByRole('button', { name: 'Начать тестирование' }).click()
    await page.locator('h2').first().waitFor({ timeout: 120_000 })
    for (let index = 0; index < 10; index += 1) {
      await page.locator('main label').first().click()
      if (await page.getByRole('button', { name: 'Завершить тест' }).isVisible()) break
      await page.getByRole('button', { name: 'Следующий вопрос' }).click()
    }
    await page.getByRole('button', { name: 'Завершить тест' }).click()
    await expect(page.getByText('Верных ответов:')).toBeVisible({ timeout: 20_000 })
    await expect(page.getByText('/ 100')).toBeVisible()

    await page.goto('/candidate/vacancies')
    const applyButton = page.getByRole('button', { name: 'Откликнуться' }).and(page.locator('button:enabled')).first()
    await applyButton.waitFor({ timeout: 15_000 })
    await applyButton.click()
    await page.locator('#application-message').fill(`Отклик e2e ${runId}`)
    await page.getByRole('button', { name: 'Отправить отклик' }).click()
    await expect(page.getByText('отправлен').first()).toBeVisible({ timeout: 15_000 })

    await page.goto('/candidate/applications')
    await expect(page.getByRole('heading', { name: 'Мои отклики' })).toBeVisible()
    await expect(page.getByText(`Отклик e2e ${runId}`).first()).toBeVisible()
    await expect(page.getByText('Новый').first()).toBeVisible()

    await page.getByRole('button', { name: 'Выйти' }).click()
    await registerAndConfirmAndLogin(page, 'employer', employerEmail, password)
    await expect(page.getByText('Подбор кандидатов', { exact: true })).toBeVisible()

    await page.goto('/employer/company')
    await page.getByPlaceholder('ООО «ТехноСфера»').fill(companyName)
    await page.getByPlaceholder(/Продуктовая компания/).fill(`Продуктовая команда ${runId}`)
    await page.getByPlaceholder('hr@company.ru').fill(`hr-${runId}@e2e.corp`)
    await page.getByPlaceholder('+7 900 000-00-00').fill('+7 900 111-22-33')
    await page.getByRole('button', { name: 'Сохранить' }).click()
    await expect(page.getByText('Профиль компании сохранён')).toBeVisible()

    await page.goto('/employer')
    await page.getByText('Кандидат #').first().waitFor({ timeout: 15_000 })
    await page.getByPlaceholder('Поиск по навыкам').fill('python')
    await page.getByRole('button', { name: 'Добавить' }).click()
    await expect(page.getByText('python').first()).toBeVisible()
    await expect(page.getByText('Ничего не найдено')).toBeVisible({ timeout: 15_000 })
    await page.locator('span.chip', { hasText: 'python' }).getByRole('button').click()

    const categoryLabel = `${demo.specialization.charAt(0).toUpperCase()}${demo.specialization.slice(1)} · ${demo.grade.charAt(0).toUpperCase()}${demo.grade.slice(1)}`
    const categoryHeading = page.locator('h2').filter({ hasText: categoryLabel })
    if ((await categoryHeading.count()) === 0) {
      await page
        .getByRole('button')
        .filter({ hasText: categoryLabel })
        .first()
        .click()
    }
    const demoCard = page
      .getByText(`Кандидат ${demoAnonId}`, { exact: true })
      .locator('xpath=ancestor::article[1]')
    await demoCard.waitFor({ timeout: 15_000 })
    await demoCard.getByRole('button', { name: 'Отправить приглашение' }).click()
    await page.getByPlaceholder('Проект, команда, задачи…').fill(`Приглашение e2e ${runId}`)
    await page.getByPlaceholder('180 000').fill('150000')
    await page.getByPlaceholder('240 000').fill('200000')
    await page.getByPlaceholder('tg: @hr_techno').fill(`tg: @e2e_${runId}`)
    await page.locator('div.fixed').getByRole('button', { name: 'Отправить' }).click()
    await expect(page.getByText('Приглашение кандидату отправлено')).toBeVisible({ timeout: 15_000 })

    await page.goto('/employer/vacancies')
    await page.getByRole('button', { name: 'Опубликовать вакансию' }).first().click()
    const vacancyModal = page.locator('div.fixed')
    await vacancyModal.getByPlaceholder('Senior Python / Highload Developer').fill(vacancyTitle)
    await vacancyModal.locator('select').nth(0).selectOption('backend')
    await vacancyModal.locator('select').nth(1).selectOption('junior')
    await vacancyModal.getByPlaceholder('Python, FastAPI, PostgreSQL, Kafka, Docker').fill('Python, FastAPI')
    await vacancyModal.getByPlaceholder('220 000').fill('150000')
    await vacancyModal.getByPlaceholder('290 000').fill('250000')
    await vacancyModal.getByPlaceholder(/Разработка отказоустойчивых/).fill(`Проектная разработка ${runId}`)
    await vacancyModal.locator('button[type="submit"]').click()
    await expect(page.getByText(`Вакансия «${vacancyTitle}» опубликована`)).toBeVisible({ timeout: 15_000 })
    await expect(page.getByRole('heading', { name: vacancyTitle })).toBeVisible()

    await page.getByRole('button', { name: 'Редактировать' }).first().click()
    await vacancyModal.getByPlaceholder('Senior Python / Highload Developer').fill(vacancyTitleEdited)
    await vacancyModal.locator('button[type="submit"]').click()
    await expect(page.getByText(`Вакансия «${vacancyTitleEdited}» обновлена`)).toBeVisible({ timeout: 15_000 })
    await expect(page.getByRole('heading', { name: vacancyTitleEdited })).toBeVisible()

    await page.goto('/employer/regular-tasks')
    await page.getByLabel('Вакансия').selectOption({ label: new RegExp(vacancyTitleEdited) })
    await page.getByRole('button', { name: 'Вручную' }).click()
    await page.getByPlaceholder(/Выберите верное утверждение/).fill(taskStatement)
    await page.getByPlaceholder('Вариант А').fill('Вариант А')
    await page.getByPlaceholder('Вариант Б').fill('Вариант Б')
    await page.getByRole('button', { name: 'Добавить задание к вакансии' }).click()
    await expect(page.getByText('Задание привязано к вакансии')).toBeVisible({ timeout: 15_000 })
    await expect(page.getByRole('heading', { name: taskStatement })).toBeVisible()

    await page.getByRole('button', { name: 'Выйти' }).click()
    await login(page, 'candidate', 'demo.candidate.001@example.com', 'demo-password')
    await page.goto('/candidate/invitations')
    const invitationCard = page
      .locator('div.rounded-panel')
      .filter({ has: page.getByText(companyName, { exact: true }) })
      .first()
    await invitationCard.waitFor({ timeout: 15_000 })
    await invitationCard.getByRole('button', { name: 'Принять приглашение' }).click()
    await expect(invitationCard.getByText('Принято')).toBeVisible({ timeout: 15_000 })
    await expect(invitationCard.getByText('Контакты переданы компании')).toBeVisible()

    await page.goto('/candidate/vacancies')
    const vacancyCard = page
      .locator('div.rounded-panel')
      .filter({ has: page.getByRole('heading', { name: vacancyTitleEdited }) })
      .first()
    await vacancyCard.waitFor({ timeout: 15_000 })
    await vacancyCard.getByRole('button', { name: 'Откликнуться' }).click()
    await page.getByPlaceholder(/Кратко о релевантном опыте/).fill('Готов к заданиям работодателя')
    await page.getByRole('button', { name: 'Отправить отклик' }).click()
    await expect(page.getByText('Усилить отклик заданиями?')).toBeVisible({ timeout: 15_000 })
    await page.getByRole('button', { name: 'Пройти задания' }).click()

    await page.getByRole('button', { name: 'Начать задания' }).click()
    const taskCard = page
      .locator('div.rounded-panel')
      .filter({ has: page.getByText('Вариант А') })
      .first()
    await taskCard.waitFor({ timeout: 15_000 })
    await taskCard.locator('button', { hasText: 'Вариант А' }).click()
    await page.getByRole('button', { name: 'Завершить' }).click()
    await page.getByRole('button', { name: 'Да, завершить' }).click()
    await expect(page.getByText(/из 2 верно/)).toBeVisible({ timeout: 15_000 })

    await page.goto('/candidate')
    await expect(page.getByRole('heading', { name: 'Профиль кандидата' })).toBeVisible()

    await page.getByRole('button', { name: 'Выйти' }).click()
    await login(page, 'employer', employerEmail, password)
    await page.goto('/employer/invitations')
    const acceptedInvitation = page
      .locator('article')
      .filter({ has: page.getByText(`Кандидат ${demoAnonId}`) })
      .first()
    await acceptedInvitation.waitFor({ timeout: 15_000 })
    await expect(acceptedInvitation.getByText('Принято', { exact: true })).toBeVisible()
    await expect(acceptedInvitation.getByText(/@example\.com/)).toBeVisible()

    await page.goto('/employer/applications')
    await expect(page.getByRole('heading', { name: 'Входящие отклики' })).toBeVisible()
    await expect(page.getByText(/На ваши вакансии пока нет откликов|Ничего не найдено|Новый/).first()).toBeVisible()
  })
})
