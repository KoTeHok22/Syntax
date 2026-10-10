import { get, post, postMultipart } from './client'

export type HeuristicId = 'nielsen_visibility' | 'nielsen_consistency' | 'nielsen_error_prevention' | 'nielsen_user_control' | 'fitts_targets' | 'contrast' | 'hierarchy'
export type CriterionId = 'evidence' | 'reasoning' | 'prioritization' | 'actionability'

export interface HeuristicChecklistItem {
  id: HeuristicId
  principle: string
  question: string
  evidence_hint: string
}

export interface SelectedViolation {
  heuristic_id: HeuristicId
  rationale: string
  evidence: string
  severity: 'low' | 'medium' | 'high'
  recommendation: string
}

export interface DesignerAuditEvaluation {
  criteria: { id: CriterionId; score: number; feedback: string }[]
  summary: string
  score: number
  source: 'llm' | 'deterministic'
  evidence_mode?: 'text_only' | 'image_and_text'
  limitation: string
  testing_score: number | null
  reference_coverage?: number | null
  missed_defects?: string[]
}

export interface DesignerAudit {
  id: number
  scenario: string
  task_key: string | null
  screenshot_data_url: string
  status: 'pending' | 'submitted'
  checklist: HeuristicChecklistItem[]
  violations: SelectedViolation[]
  evaluation: DesignerAuditEvaluation | null
  created_at: string
  submitted_at: string | null
}

export interface PortfolioMetrics {
  metrics: { metric: string; value: string; evidence: string }[]
  text_chars: number
  limitation: string
}

export function fetchAssignedDesignerAudit(): Promise<DesignerAudit> {
  return post('/designer-audits/task')
}

export function fetchDesignerAudit(id: number): Promise<DesignerAudit> {
  return get(`/designer-audits/${id}`)
}

export function submitDesignerAudit(id: number, violations: SelectedViolation[]): Promise<DesignerAudit> {
  return post(`/designer-audits/${id}/submit`, { violations })
}

export function uploadDesignerScreenshot(file: File, scenario: string): Promise<DesignerAudit> {
  const form = new FormData()
  form.append('file', file)
  form.append('scenario', scenario)
  return postMultipart('/designer-audits/upload', form)
}

export function uploadDesignerPortfolio(file: File): Promise<PortfolioMetrics> {
  const form = new FormData()
  form.append('file', file)
  return postMultipart('/designer-audits/portfolio', form)
}

export async function fetchDesignerPortfolio(): Promise<PortfolioMetrics | null> {
  const profile = await get<{ portfolio_evidence?: Partial<PortfolioMetrics> }>('/candidates/me')
  const evidence = profile.portfolio_evidence
  return evidence && Array.isArray(evidence.metrics) && typeof evidence.text_chars === 'number' && typeof evidence.limitation === 'string'
    ? evidence as PortfolioMetrics
    : null
}
