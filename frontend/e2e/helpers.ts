import type { Page } from '@playwright/test'

const API_BASE = 'http://localhost:8000'

export async function registerAndConfirmAndLogin(page: Page, role: 'candidate' | 'employer', email: string, password: string): Promise<void> {
  await page.goto('/login')
  await page.getByRole('button', { name: 'Регистрация' }).click()
  if (role === 'employer') {
    await page.getByRole('button', { name: 'Я работодатель' }).click()
  }
  await page.locator('#user-email').fill(email)
  await page.locator('#user-password').fill(password)
  await page.locator('input[type="checkbox"]').first().check()
  await page.getByRole('button', { name: 'Создать профиль' }).click()
  const info = page.locator('div.break-all')
  await info.waitFor({ timeout: 15_000 })
  const text = await info.textContent()
  const match = text?.match(/https?:\/\/\S+/)
  if (match === null) throw new Error('confirmation_url not found in info block')
  const confirmResponse = await page.request.get(match[0])
  if (!confirmResponse.ok()) throw new Error(`email confirmation failed: ${confirmResponse.status()}`)
  await page.getByRole('button', { name: 'Вход' }).click()
  await page.locator('#user-email').fill(email)
  await page.locator('#user-password').fill(password)
  await page.getByRole('button', { name: 'Войти' }).click()
  await page.waitForURL(role === 'candidate' ? '/candidate' : '/employer')
}

export async function login(page: Page, role: 'candidate' | 'employer', email: string, password: string): Promise<void> {
  await page.goto('/login')
  if (role === 'employer') {
    await page.getByRole('button', { name: 'Я работодатель' }).click()
  }
  await page.locator('#user-email').fill(email)
  await page.locator('#user-password').fill(password)
  await page.getByRole('button', { name: 'Войти' }).click()
  await page.waitForURL(role === 'candidate' ? '/candidate' : '/employer')
}

export interface DemoCandidateInfo {
  profileId: number
  specialization: string
  grade: string
}

export async function fetchDemoCandidateInfo(): Promise<DemoCandidateInfo> {
  const loginResponse = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ username: 'demo.candidate.001@example.com', password: 'demo-password' }),
  })
  if (!loginResponse.ok) throw new Error(`demo login failed: ${loginResponse.status}`)
  const { access_token: token } = (await loginResponse.json()) as { access_token: string }
  const profileResponse = await fetch(`${API_BASE}/candidates/me`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!profileResponse.ok) throw new Error(`demo profile failed: ${profileResponse.status}`)
  const profile = (await profileResponse.json()) as { id: number; specialization: string; grade: string }
  return { profileId: profile.id, specialization: profile.specialization, grade: profile.grade }
}
