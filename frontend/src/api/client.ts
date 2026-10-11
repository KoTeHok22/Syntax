const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

const TOKEN_KEY = 'syntax_access_token'
const USER_KEY = 'syntax_user'

export interface AuthUser {
  id: number
  email: string
  role: 'candidate' | 'employer'
  pvn_id: string | null
  is_email_confirmed: boolean
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setSession(token: string, user: AuthUser): void {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function clearSession(): void {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

export function getStoredUser(): AuthUser | null {
  const raw = localStorage.getItem(USER_KEY)
  if (raw === null) return null
  try {
    return JSON.parse(raw) as AuthUser
  } catch {
    return null
  }
}

export class ApiError extends Error {
  status: number
  detail: string

  constructor(status: number, detail: string) {
    super(detail)
    this.status = status
    this.detail = detail
  }
}

const VALIDATION_MESSAGES: Record<string, string> = {
  'Input should be a valid string': 'Проверьте заполнение полей: ожидается текст',
  'Field required': 'Заполните обязательное поле',
  'String should have at most 255 characters': 'Слишком длинное значение (максимум 255 символов)',
  'Input should be a valid number': 'Ожидается число',
  'Input should be greater than or equal to 0': 'Значение не может быть отрицательным',
}

function humanizeValidation(message: string): string {
  const exact = VALIDATION_MESSAGES[message]
  if (exact !== undefined) return exact
  if (/should be a valid/.test(message)) return 'Проверьте заполнение полей'
  if (/^String should have at least/.test(message)) return 'Значение слишком короткое'
  return 'Проверьте заполнение полей'
}

async function parseError(response: Response): Promise<ApiError> {
  let detail = `Ошибка ${response.status}`
  try {
    const body = await response.json()
    if (typeof body.detail === 'string') detail = body.detail
    else if (Array.isArray(body.detail)) {
      detail = body.detail
        .map((item: { msg?: string }) => (typeof item?.msg === 'string' ? humanizeValidation(item.msg) : 'Проверьте заполнение полей'))
        .join('; ')
    }
  } catch {
    if (response.status === 401) detail = 'Требуется вход'
  }
  return new ApiError(response.status, detail)
}

interface RequestOptions {
  token?: string
  signal?: AbortSignal
}

async function request<T>(path: string, init: RequestInit = {}, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (typeof init.body === 'string') {
    headers.set('Content-Type', 'application/json')
  }
  const token = options.token ?? getToken()
  if (token !== null) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers, signal: options.signal })
  if (!response.ok) {
    if (response.status === 401 && token !== null && !path.startsWith('/auth/login')) {
      clearSession()
      if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
        window.location.assign('/login?expired=1')
      }
    }
    throw await parseError(response)
  }
  if (response.status === 204) return undefined as T
  const contentType = response.headers.get('content-type') ?? ''
  if (contentType.includes('application/pdf') || contentType.includes('application/octet-stream')) {
    return (await response.blob()) as unknown as T
  }
  return (await response.json()) as T
}

export function get<T>(path: string, options: RequestOptions = {}): Promise<T> {
  return request<T>(path, { method: 'GET' }, options)
}

export function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })
}

export function patch<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, { method: 'PATCH', body: body === undefined ? undefined : JSON.stringify(body) })
}

export function put<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, { method: 'PUT', body: body === undefined ? undefined : JSON.stringify(body) })
}

export function postForm<T>(path: string, form: Record<string, string>): Promise<T> {
  const body = new URLSearchParams(form)
  return request<T>(path, { method: 'POST', body, headers: { 'Content-Type': 'application/x-www-form-urlencoded' } })
}

export function postMultipart<T>(path: string, form: FormData): Promise<T> {
  return request<T>(path, { method: 'POST', body: form })
}

export const apiBase = API_BASE
