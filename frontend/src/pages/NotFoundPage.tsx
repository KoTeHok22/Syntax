import { Link } from 'react-router-dom'
import { BrandLockup } from '../components/Brand'

export function NotFoundPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-base p-6">
      <div className="flex w-full max-w-md flex-col items-center gap-5 rounded-panel bg-raised p-10 text-center shadow-raised-lg">
        <BrandLockup size={36} tone="dark" />
        <span className="font-mono text-[64px] font-extrabold leading-none tracking-tight text-pvn-blue">404</span>
        <h1 className="font-mono text-h2 font-extrabold tracking-tight text-ink">Страница не найдена</h1>
        <p className="font-sans text-body text-ink-secondary">
          Возможно, ссылка устарела или в адресе опечатка. Вернитесь на главную — там вход и регистрация.
        </p>
        <Link className="btn-primary" to="/">
          <span className="material-symbols-outlined text-[18px]">home</span>
          На главную
        </Link>
      </div>
    </div>
  )
}
