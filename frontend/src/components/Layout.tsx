import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { Header } from './Header'
import { ErrorBoundary } from './ErrorBoundary'

export function RequireRole({ role, children }: { role: 'candidate' | 'employer'; children: ReactNode }) {
  const { user, isReady } = useAuth()
  if (!isReady) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-base">
        <span className="font-mono text-caption text-ink-secondary">Загрузка…</span>
      </div>
    )
  }
  if (user === null) return <Navigate to="/" replace />
  if (user.role !== role) return <Navigate to={user.role === 'employer' ? '/employer' : '/candidate'} replace />
  return (
    <div className="min-h-screen bg-base font-sans text-body text-ink">
      <Header />
      <main className="min-h-[calc(100vh-80px)] w-full pb-12">
        <ErrorBoundary>{children}</ErrorBoundary>
      </main>
    </div>
  )
}

export function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-base font-sans text-body text-ink">
      <main className="w-full">{children}</main>
    </div>
  )
}
