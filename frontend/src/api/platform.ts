import { get, patch, post, put, postMultipart } from './client'

export function anonymousCandidateId(profileId: number): string {
  return `#${profileId.toString(16).toUpperCase().padStart(4, '0')}`
}

export interface ScoreComponent {
  label: string
  value: number
  weight: number
}

export interface PvnAchievement {
  type: string
  level: string
  date: string
  score: number
}

export type WorkFormat = '' | 'remote' | 'office' | 'hybrid'

export type City = string

export interface StackProofItem {
  stack: string
  domain: string | null
  proof: 'verified' | 'claimed'
}

export interface CandidateCard {
  candidate_profile_id: number
  grade: string
  specialization: string
  city: string
  work_format: string
  stack: string[]
  score: number
  score_breakdown: Record<string, ScoreComponent>
  has_pvn_history: boolean
  is_pvn_verified: boolean
  pvn_achievements: PvnAchievement[]
  match_relevance: number
  final_score: number
  proof_tier: string
  is_verified: boolean
  stack_proof?: StackProofItem[]
  match_breakdown?: {
    stack: number
    semantic: number | null
    mode: 'semantic' | 'lexical'
    stack_weight: number
    semantic_weight: number
    relevance: number
    overlap?: {
      required_total: number
      matched_total: number
      matched: string[]
      missing: string[]
    }
  }
}

export interface Category {
  id: number
  specialization: string
  grade: string
  candidate_count: number
}

export interface CategoryPage {
  total: number
  items: Category[]
}

export interface Domain {
  id: number
  slug: string
  title: string
  aliases: string[]
  candidate_count: number
  score: number
}

export interface DomainPage {
  total: number
  items: Domain[]
}

export function fetchDomains(
  params: { q?: string; skip?: number; limit?: number } = {},
): Promise<DomainPage> {
  const query = new URLSearchParams()
  if (params.q) query.set('q', params.q)
  if (params.skip !== undefined) query.set('skip', String(params.skip))
  if (params.limit !== undefined) query.set('limit', String(params.limit))
  const suffix = query.toString().length > 0 ? `?${query.toString()}` : ''
  return get(`/employer/domains${suffix}`)
}

export function createDomain(payload: { title: string; aliases?: string[] }): Promise<Domain> {
  return post('/employer/domains', payload)
}

export function fetchCategories(
  params: { q?: string; specialization?: string; grade?: string; skip?: number; limit?: number } = {},
): Promise<CategoryPage> {
  const query = new URLSearchParams()
  if (params.q) query.set('q', params.q)
  if (params.specialization) query.set('specialization', params.specialization)
  if (params.grade) query.set('grade', params.grade)
  if (params.skip !== undefined) query.set('skip', String(params.skip))
  if (params.limit !== undefined) query.set('limit', String(params.limit))
  const suffix = query.toString().length > 0 ? `?${query.toString()}` : ''
  return get(`/employer/categories${suffix}`)
}

export interface CardFilters {
  stack?: string[]
  has_pvn?: boolean
  verified_only?: boolean
  min_score?: number
  city?: City
  work_format?: WorkFormat
  skip?: number
  limit?: number
  q?: string
}

function buildFiltersQuery(filters: CardFilters): URLSearchParams {
  const query = new URLSearchParams()
  filters.stack?.forEach((item) => query.append('stack', item))
  if (filters.has_pvn !== undefined) query.set('has_pvn', String(filters.has_pvn))
  if (filters.verified_only !== undefined) query.set('verified_only', String(filters.verified_only))
  if (filters.min_score !== undefined) query.set('min_score', String(filters.min_score))
  if (filters.city) query.set('city', filters.city)
  if (filters.work_format) query.set('work_format', filters.work_format)
  if (filters.q) query.set('q', filters.q)
  if (filters.skip !== undefined) query.set('skip', String(filters.skip))
  if (filters.limit !== undefined) query.set('limit', String(filters.limit))
  return query
}

export function fetchCategoryCards(categoryId: number, filters: CardFilters = {}): Promise<CandidateCard[]> {
  const query = buildFiltersQuery(filters)
  const suffix = query.size > 0 ? `?${query.toString()}` : ''
  return get(`/employer/categories/${categoryId}/cards${suffix}`)
}

export function searchCandidates(
  filters: CardFilters & { specialization?: string; grade?: string; vacancy_id?: number },
  signal?: AbortSignal,
): Promise<CandidateCard[]> {
  const query = buildFiltersQuery(filters)
  if (filters.specialization) query.set('specialization', filters.specialization)
  if (filters.grade) query.set('grade', filters.grade)
  if (filters.vacancy_id !== undefined) query.set('vacancy_id', String(filters.vacancy_id))
  const suffix = query.size > 0 ? `?${query.toString()}` : ''
  return get(`/employer/search${suffix}`, signal === undefined ? {} : { signal })
}

export interface CandidatePublicProfileAchievement {
  type: string
  level: string
  date?: string
}

export interface CandidatePublicProfile {
  candidate_profile_id: number
  grade: string | null
  specialization: string
  stack_proof: StackProofItem[]
  years_of_experience: number
  soft_skills: string[]
  city: string
  work_format: string
  proof_tier: string
  is_verified: boolean
  score: number
  score_breakdown: Record<string, ScoreComponent>
  match_relevance: number | null
  pvn_achievements: CandidatePublicProfileAchievement[]
}

export const candidatePublicProfilePath = (
  candidateProfileId: number,
  vacancyId?: number,
): string => {
  const query = vacancyId === undefined ? '' : `?vacancy_id=${vacancyId}`
  return `/employer/candidates/${candidateProfileId}${query}`
}

export function fetchCandidatePublicProfile(
  candidateProfileId: number,
  vacancyId?: number,
  signal?: AbortSignal,
): Promise<CandidatePublicProfile> {
  return get(candidatePublicProfilePath(candidateProfileId, vacancyId), signal === undefined ? {} : { signal })
}

export interface Invitation {
  id: number
  candidate_profile_id: number
  candidate_grade: string | null
  candidate_specialization: string | null
  candidate_stack: string[]
  message: string | null
  salary_from: number
  salary_to: number
  company_name: string | null
  contact_method: string | null
  status: 'sent' | 'viewed' | 'accepted' | 'rejected' | 'withdrawn'
  candidate_contacts: Record<string, string> | null
  created_at: string
  viewed_at: string | null
  responded_at: string | null
}

export interface CreateInvitationPayload {
  candidate_profile_id: number
  message: string
  salary_from: number
  salary_to: number
  company_name: string
  contact_method: string
}

export type UpdateInvitationPayload = Omit<CreateInvitationPayload, 'candidate_profile_id'>

export function createInvitation(payload: CreateInvitationPayload): Promise<Invitation> {
  return post('/invitations', payload)
}

export function updateInvitation(id: number, payload: UpdateInvitationPayload): Promise<Invitation> {
  return patch(`/invitations/${id}`, payload)
}

export function withdrawInvitation(id: number): Promise<Invitation> {
  return post(`/invitations/${id}/withdraw`)
}

export function fetchIncomingInvitations(): Promise<Invitation[]> {
  return get('/invitations/incoming')
}

export function fetchSentInvitations(): Promise<Invitation[]> {
  return get('/invitations/sent')
}

export function viewInvitation(id: number): Promise<Invitation> {
  return post(`/invitations/${id}/view`)
}

export function acceptInvitation(id: number): Promise<Invitation> {
  return post(`/invitations/${id}/accept`)
}

export function rejectInvitation(id: number): Promise<Invitation> {
  return post(`/invitations/${id}/reject`)
}

export interface Vacancy {
  id: number
  title: string
  description: string | null
  stack: string[]
  specialization: string | null
  grade: string | null
  salary_from: number
  salary_to: number
  is_open: boolean
}

type VacancyApiPayload = Omit<Vacancy, 'is_open'> & { status?: string; is_open?: boolean }

function normalizeVacancy(raw: VacancyApiPayload): Vacancy {
  return { ...raw, is_open: raw.is_open ?? raw.status === 'open' }
}

export interface CreateVacancyPayload {
  title: string
  description: string
  stack: string[]
  specialization: string
  grade: string
  salary_from: number
  salary_to: number
}

export function createVacancy(payload: CreateVacancyPayload): Promise<Vacancy> {
  return post<VacancyApiPayload>('/vacancies', payload).then(normalizeVacancy)
}

export function fetchVacancies(params: { grade?: string; specialization?: string; skip?: number; limit?: number } = {}): Promise<Vacancy[]> {
  const query = new URLSearchParams()
  if (params.grade) query.set('grade', params.grade)
  if (params.specialization) query.set('specialization', params.specialization)
  if (params.skip !== undefined) query.set('skip', String(params.skip))
  if (params.limit !== undefined) query.set('limit', String(params.limit))
  const suffix = query.size > 0 ? `?${query.toString()}` : ''
  return get<VacancyApiPayload[]>(`/vacancies${suffix}`).then((list) => list.map(normalizeVacancy))
}

export function closeVacancy(id: number): Promise<Vacancy> {
  return post<VacancyApiPayload>(`/vacancies/${id}/close`).then(normalizeVacancy)
}

export interface Application {
  id: number
  vacancy_id: number
  vacancy_title?: string | null
  candidate_profile_id: number
  message: string | null
  status: 'new' | 'viewed' | 'accepted' | 'rejected'
  ats_delivery_status?: 'pending' | 'failed' | 'delivered'
  ats_delivery_attempts?: number
  ats_delivery_error?: string | null
  ats_delivered_at?: string | null
  interview_at?: string | null
  interview_duration?: number | null
  interview_format?: 'video' | 'onsite' | 'phone' | null
  interview_link?: string | null
  interview_address?: string | null
}

export interface InterviewSchedulePayload {
  scheduled_at: string
  duration_minutes: number
  format: 'video' | 'onsite' | 'phone'
  link?: string | null
  address?: string | null
}

export function scheduleInterview(id: number, payload: InterviewSchedulePayload): Promise<Application> {
  return put(`/applications/${id}/interview`, payload)
}

export function createApplication(vacancyId: number, message: string): Promise<Application> {
  return post('/applications', { vacancy_id: vacancyId, message })
}

export function fetchMyApplications(): Promise<Application[]> {
  return get('/applications/my')
}

export function fetchIncomingApplications(): Promise<Application[]> {
  return get('/applications/incoming')
}

export function updateApplicationStatus(id: number, status: Application['status']): Promise<Application> {
  return put(`/applications/${id}/status`, { status })
}

export function uploadResume(file: File): Promise<{ applied: Record<string, unknown>; skipped: Record<string, string> }> {
  const form = new FormData()
  form.append('file', file)
  return postMultipart('/candidates/me/resume', form)
}

export function downloadProfilePdf(): Promise<Blob> {
  return get<Blob>('/candidates/me/profile.pdf')
}

export function fetchMyVacancies(params: { skip?: number; limit?: number } = {}, signal?: AbortSignal): Promise<Vacancy[]> {
  const query = new URLSearchParams()
  if (params.skip !== undefined) query.set('skip', String(params.skip))
  if (params.limit !== undefined) query.set('limit', String(params.limit))
  const suffix = query.size > 0 ? `?${query.toString()}` : ''
  return get<VacancyApiPayload[]>(`/vacancies/my${suffix}`, signal === undefined ? {} : { signal }).then((list) => list.map(normalizeVacancy))
}

export function updateVacancy(id: number, payload: CreateVacancyPayload): Promise<Vacancy> {
  return put<VacancyApiPayload>(`/vacancies/${id}`, payload).then(normalizeVacancy)
}

export interface CompanyOffice {
  id: number
  title: string
  city: string
  address: string
  is_default: boolean
}

export interface CompanyOfficePayload {
  title: string
  city: string
  address: string
  is_default: boolean
}

export interface EmployerProfile {
  id: number
  company_name: string
  description: string
  contacts: Record<string, string>
  offices: CompanyOffice[]
  logo_data_url: string | null
  logo_zoom: number
  logo_offset_x: number
  logo_offset_y: number
}

export interface EmployerProfilePayload {
  company_name: string
  description: string
  contacts: Record<string, string>
  offices?: CompanyOfficePayload[]
  logo_data_url?: string | null
  logo_zoom?: number
  logo_offset_x?: number
  logo_offset_y?: number
}

export function fetchEmployerProfile(): Promise<EmployerProfile> {
  return get('/employers/me')
}

export function updateEmployerProfile(payload: EmployerProfilePayload): Promise<EmployerProfile> {
  return put('/employers/me', payload)
}

export interface RegularTask {
  id: number
  vacancy_id: number
  statement: string
  task_format: string
  options: string[]
  is_active: boolean
  created_at: string
}

export type CreateRegularTaskPayload =
  | { vacancy_id: number; concept_id: number }
  | { vacancy_id: number; statement: string; options: string[]; correct_index: number }

export interface RegularTaskSummary {
  application_id: number
  vacancy_id: number
  task_count: number
  status: string
  result_score: number | null
  correct_count: number
  forced_finish: boolean
}

export interface RegularTaskSessionTask {
  id: number
  statement: string
  task_format: string
  options: string[]
}

export interface RegularTaskSession {
  id: number
  application_id: number
  vacancy_id: number
  status: string
  task_count: number
  correct_count: number
  result_score: number | null
  forced_finish: boolean
  expires_at: string | null
  completed_at: string | null
  tasks: RegularTaskSessionTask[]
}

export interface RegularTaskSessionResult {
  id: number
  status: string
  task_count: number
  correct_count: number
  result_score: number
  forced_finish: boolean
}

export interface ApplicationTaskResult {
  application_id: number
  vacancy_id: number
  status: string
  task_count: number
  correct_count: number
  result_score: number | null
  forced_finish: boolean
  completed_at: string | null
}

export interface Concept {
  id: number
  name: string
  domain: string
  grade: string
}

export function fetchConcepts(): Promise<Concept[]> {
  return get('/concepts')
}

export function createRegularTask(payload: CreateRegularTaskPayload): Promise<RegularTask> {
  return post('/regular-tasks', payload)
}

export function fetchVacancyTaskSummary(vacancyId: number): Promise<RegularTaskSummary> {
  return get(`/regular-tasks/vacancy/${vacancyId}`)
}

export function startRegularTaskSession(vacancyId: number): Promise<RegularTaskSession> {
  return post(`/regular-tasks/vacancy/${vacancyId}/session`)
}

export function submitRegularTaskAnswers(
  sessionId: number,
  answers: { regular_task_id: number; option_index: number }[],
): Promise<RegularTaskSessionResult> {
  return post(`/regular-tasks/sessions/${sessionId}/answers`, answers)
}

export function fetchEmployerRegularTasks(vacancyId?: number): Promise<RegularTask[]> {
  const query = vacancyId === undefined ? '' : `?vacancy_id=${vacancyId}`
  return get(`/employer/regular-tasks${query}`)
}

export function fetchVacancyTaskResults(vacancyId: number): Promise<ApplicationTaskResult[]> {
  return get(`/employer/regular-tasks/results?vacancy_id=${vacancyId}`)
}

export function closeRegularTask(id: number): Promise<RegularTask> {
  return post(`/employer/regular-tasks/${id}/close`)
}
