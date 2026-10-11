import { get, postForm, put, post, type AuthUser } from './client'

export interface RegisterPayload {
  email: string
  password: string
  role: 'candidate' | 'employer'
  consent_accepted: boolean
  pvn_id?: string
  specialization?: string
  grade?: 'junior' | 'middle' | 'senior'
}

export interface CandidateCategory {
  specialization: string
  grade: 'junior' | 'middle' | 'senior'
}

export interface RegisterResult extends AuthUser {
  confirmation_url: string | null
  category_id: number | null
}

export interface LoginResponse {
  access_token: string
  token_type: 'bearer'
  role: 'candidate' | 'employer'
}

export function register(payload: RegisterPayload): Promise<RegisterResult> {
  return post('/auth/register', payload)
}

export function confirmEmail(token: string): Promise<{ email: string; is_email_confirmed: boolean }> {
  return get(`/auth/confirm/${token}`)
}

export function login(email: string, password: string): Promise<LoginResponse> {
  return postForm('/auth/login', { username: email, password })
}

export function fetchMe(token?: string): Promise<AuthUser> {
  return get('/auth/me', token === undefined ? {} : { token })
}

export interface CandidateProfile {
  id: number
  full_name: string | null
  specialization: string | null
  grade: string | null
  stack: string[]
  years_of_experience: number | null
  soft_skills: string[]
  city: string
  work_format: string
  contacts: Record<string, string> | null
  is_visible: boolean
  pvn_id: string | null
  is_pvn_verified: boolean
  grade_changed_at: string | null
  grade_confirmed_at: string | null
  grade_confirmed: boolean
  grade_valid_until: string | null
  score: number
  score_breakdown: Record<string, { label: string; value: number; weight: number }>
  avatar_data_url: string | null
  avatar_zoom: number
  avatar_offset_x: number
  avatar_offset_y: number
}

export function fetchCandidateProfile(): Promise<CandidateProfile> {
  return get('/candidates/me')
}

export function updateCandidateProfile(payload: Partial<CandidateProfile>): Promise<CandidateProfile> {
  return put('/candidates/me', payload)
}

export function updateVisibility(isVisible: boolean): Promise<CandidateProfile> {
  return put('/candidates/me/visibility', { is_visible: isVisible })
}

export function updateGrade(grade: string): Promise<CandidateProfile> {
  return put('/candidates/me/grade', { grade })
}
