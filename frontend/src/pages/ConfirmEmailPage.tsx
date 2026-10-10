import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { confirmEmail } from '../api/auth'
import { BrandMark } from '../components/Brand'

export function ConfirmEmailPage() {
  const { token } = useParams<{ token: string }>()
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [email, setEmail] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (token === undefined) return
    confirmEmail(token)
      .then((result) => {
        setEmail(result.email)
        setStatus('success')
      })
      .catch((exception) => {
        setError(exception instanceof Error ? exception.message : 'Токен не найден')
        setStatus('error')
      })
  }, [token])

  return (
    <div className="flex min-h-screen items-center justify-center bg-base p-4">
      <div className="w-full max-w-md rounded-panel bg-raised p-8 text-center shadow-raised-lg">
        <div className="mb-5 flex justify-center">
          <BrandMark size={48} />
        </div>
        {status === 'loading' ? <p className="font-mono text-caption text-ink-secondary">Проверяем подтверждение…</p> : null}
        {status === 'success' ? (
          <>
            <h1 className="font-mono text-[24px] font-extrabold tracking-tight text-ink">Email подтверждён</h1>
            <p className="mt-2 font-sans text-caption text-ink-secondary">{email} готов к входу на платформу.</p>
            <Link className="btn-primary mt-6 inline-flex" to="/login">
              Перейти ко входу
              <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
            </Link>
          </>
        ) : null}
        {status === 'error' ? (
          <>
            <h1 className="font-mono text-[24px] font-extrabold tracking-tight text-ink">Не удалось подтвердить</h1>
            <p className="mt-2 font-sans text-caption text-ink-secondary">{error}</p>
            <Link className="btn-ghost mt-6 inline-flex" to="/login">
              На страницу входа
            </Link>
          </>
        ) : null}
      </div>
    </div>
  )
}
