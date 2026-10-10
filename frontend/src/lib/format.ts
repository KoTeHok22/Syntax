export function pluralize(count: number, forms: [string, string, string]): string {
  const normalized = Math.abs(count)
  const isFraction = !Number.isInteger(normalized)
  const mod100 = Math.floor(normalized) % 100
  const mod10 = Math.floor(normalized) % 10
  if (isFraction) return forms[1]
  if (mod100 >= 11 && mod100 <= 14) return forms[2]
  if (mod10 === 1) return forms[0]
  if (mod10 >= 2 && mod10 <= 4) return forms[1]
  return forms[2]
}

export function formatYears(value: number): string {
  return `${value} ${pluralize(value, ['год', 'года', 'лет'])}`
}

export function formatExperience(value: number | null): string {
  if (value === null) return 'Не указан'
  return formatYears(value)
}

export function formatNumberInput(value: string): number | null {
  const trimmed = value.trim().replace(',', '.')
  if (trimmed === '') return null
  const parsed = Number(trimmed)
  return Number.isFinite(parsed) ? parsed : null
}

const TASK_FORMAT_LABELS: Record<string, string> = {
  multiple_choice: 'Один из нескольких вариантов',
  code: 'Задача с кодом',
  open: 'Открытый ответ',
}

export function taskFormatLabel(format: string): string {
  return TASK_FORMAT_LABELS[format] ?? 'Тестовое задание'
}

const SPECIALIZATION_LABELS: Record<string, string> = {
  backend: 'Backend',
  frontend: 'Frontend',
  data: 'Data',
  devops: 'DevOps',
  mobile: 'Mobile',
  qa: 'QA',
}

const GRADE_LABELS: Record<string, string> = {
  junior: 'Junior',
  middle: 'Middle',
  senior: 'Senior',
}

export function specializationLabel(value: string | null | undefined): string {
  if (!value) return ''
  return SPECIALIZATION_LABELS[value.toLowerCase()] ?? value
}

export function gradeLabel(value: string | null | undefined): string {
  if (!value) return ''
  return GRADE_LABELS[value.toLowerCase()] ?? value
}

export function truncateEmail(email: string, maxLength = 26): string {
  const atIndex = email.indexOf('@')
  if (atIndex === -1 || email.length <= maxLength) return email
  const domain = email.slice(atIndex)
  const localBudget = maxLength - domain.length - 1
  if (localBudget <= 1) return email
  return `${email.slice(0, localBudget)}…${domain}`
}

export function formatIsoDate(value: string | null | undefined): string {
  if (!value) return '—'
  const [datePart] = value.split('T')
  const [year, month, day] = datePart.split('-')
  if (!year || !month || !day) return value
  return `${day}.${month}.${year}`
}
