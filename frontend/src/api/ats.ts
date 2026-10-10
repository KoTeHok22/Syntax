import { get, post, put } from './client'

export type ATSDeliveryStatus = 'pending' | 'failed' | 'delivered' | 'not_configured'

export interface ATSConfiguration {
  webhook_url: string | null
  available_webhook_urls?: string[]
  available?: boolean
  configured?: boolean
}

export interface ATSDeliveryResult {
  application_id: number
  status: ATSDeliveryStatus
  attempts: number
  error: string | null
  delivered_at?: string | null
}

export function fetchATSConfiguration(): Promise<ATSConfiguration> {
  return get('/ats/config')
}

export function updateATSConfiguration(webhookUrl: string | null): Promise<ATSConfiguration> {
  return put('/ats/config', { webhook_url: webhookUrl })
}

export function retryATSDelivery(applicationId: number): Promise<ATSDeliveryResult> {
  return post('/ats/webhook', { application_id: applicationId })
}
