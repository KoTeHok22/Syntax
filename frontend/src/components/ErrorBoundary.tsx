import { Component } from 'react'
import type { ErrorInfo, ReactNode } from 'react'

interface ErrorBoundaryProps {
  children: ReactNode
}

interface ErrorBoundaryState {
  hasError: boolean
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false }

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('Необработанная ошибка интерфейса', error, info.componentStack)
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div className="mx-auto flex w-full max-w-[1280px] flex-col items-center gap-4 px-4 py-16 text-center sm:px-6">
          <span className="material-symbols-outlined text-[48px] text-ink-muted">report</span>
          <h1 className="font-mono text-h2 font-bold text-ink">Что-то пошло не так</h1>
          <p className="max-w-md font-sans text-body text-ink-secondary">
            Раздел не загрузился. Обновите страницу — данные не потеряны.
          </p>
          <button className="btn-blue" onClick={() => window.location.reload()} type="button">
            Обновить страницу
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
