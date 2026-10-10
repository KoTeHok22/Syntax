import { get, post } from './client'

export interface TestTask {
  id: number
  statement: string
  options: string[]
}

export type TestSessionStatus = 'active' | 'completed'

export interface TestSessionApiPayload {
  id: number
  grade: string
  status: string
  tasks: TestTask[]
  task_count: number
  correct_count?: number
  result_score?: number
  verdict?: string
  suggested_grade?: string
  expires_at?: string | null
}

export interface TestSession {
  id: number
  grade: string
  status: TestSessionStatus
  tasks: TestTask[]
  task_count: number
  correct_count?: number
  result_score?: number
  verdict?: string
  suggested_grade?: string
  expires_at?: string | null
}

function normalizeTestSession(raw: TestSessionApiPayload): TestSession {
  const status: TestSessionStatus = raw.status === 'completed' ? 'completed' : 'active'
  return { ...raw, status }
}

export function startTestSession(grade: string): Promise<TestSession> {
  return post<TestSessionApiPayload>('/test-sessions', { grade }).then(normalizeTestSession)
}

export function fetchTestSessions(): Promise<TestSession[]> {
  return get<TestSessionApiPayload[]>('/test-sessions').then((list) => list.map(normalizeTestSession))
}

export function fetchTestSession(id: number): Promise<TestSession> {
  return get<TestSessionApiPayload>(`/test-sessions/${id}`).then(normalizeTestSession)
}

export interface AnswerPayload {
  task_id: number
  option_index: number
}

export interface AnswerReview {
  task_id: number
  statement: string
  options: string[]
  selected_index: number | null
  reference_answer: number | null
  is_correct: boolean
}

export interface TestSessionResult {
  id: number
  grade: string
  task_count: number
  correct_count: number
  result_score: number
  verdict: string
  suggested_grade: string | null
  grade_applied: boolean
  review: AnswerReview[]
}

export function submitAnswers(id: number, answers: AnswerPayload[]): Promise<TestSessionResult> {
  return post(`/test-sessions/${id}/answers`, answers)
}
