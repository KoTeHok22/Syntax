import { useCallback, useEffect, useState } from 'react'
import { ApiError } from '../../api/client'
import { fetchEmployerProfile, updateEmployerProfile } from '../../api/platform'
import type { CompanyOfficePayload, EmployerProfile } from '../../api/platform'
import { Toast } from '../../components/Toast'
import { LogoAvatar } from '../../components/LogoAvatar'
import { DEFAULT_LOGO_CROP } from '../../lib/logoCrop'
import type { LogoCrop } from '../../lib/logoCrop'
import { LogoCropEditor } from '../../components/LogoCropEditor'
import { fetchATSConfiguration, updateATSConfiguration } from '../../api/ats'
import type { ATSConfiguration } from '../../api/ats'

interface ProfileFormState {
  companyName: string
  description: string
  contactEmail: string
  contactPhone: string
}

interface OfficeDraft {
  key: string
  title: string
  city: string
  address: string
  isDefault: boolean
}

const emptyForm: ProfileFormState = {
  companyName: '',
  description: '',
  contactEmail: '',
  contactPhone: '',
}

const LOGO_ALLOWED_MIME = ['image/png', 'image/jpeg', 'image/webp']
const LOGO_MAX_BYTES = 512 * 1024

function readAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(file)
  })
}

function newOfficeKey(): string {
  return `office-${Math.random().toString(36).slice(2, 10)}`
}

function SkeletonForm() {
  return (
    <div className="flex w-full animate-pulse flex-col gap-4 rounded-panel bg-raised p-6 shadow-raised">
      <div className="h-5 w-48 rounded-lg bg-inset" />
      <div className="h-12 w-full rounded-xl bg-inset" />
      <div className="h-28 w-full rounded-xl bg-inset" />
      <div className="h-12 w-full rounded-xl bg-inset" />
    </div>
  )
}

export function EmployerProfilePage() {
  const [form, setForm] = useState<ProfileFormState>(emptyForm)
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [successNotice, setSuccessNotice] = useState<string | null>(null)
  const [savedProfile, setSavedProfile] = useState<EmployerProfile | null>(null)
  const [offices, setOffices] = useState<OfficeDraft[]>([])
  const [logoDataUrl, setLogoDataUrl] = useState<string | null>(null)
  const [logoCrop, setLogoCrop] = useState<LogoCrop>(DEFAULT_LOGO_CROP)
  const [logoError, setLogoError] = useState<string | null>(null)
  const [atsConfiguration, setATSConfiguration] = useState<ATSConfiguration | null>(null)
  const [atsWebhookUrl, setATSWebhookUrl] = useState('')
  const [atsLoading, setATSLoading] = useState(true)
  const [atsSubmitting, setATSSubmitting] = useState(false)
  const [atsError, setATSError] = useState<string | null>(null)
  const [atsNotice, setATSNotice] = useState<string | null>(null)

  const applyProfile = (profile: EmployerProfile) => {
    setForm({
      companyName: profile.company_name,
      description: profile.description,
      contactEmail: profile.contacts.email ?? '',
      contactPhone: profile.contacts.phone ?? '',
    })
    setOffices(
      profile.offices.map((office) => ({
        key: `saved-${office.id}`,
        title: office.title,
        city: office.city,
        address: office.address,
        isDefault: office.is_default,
      })),
    )
    setLogoDataUrl(profile.logo_data_url)
    setLogoCrop({ zoom: profile.logo_zoom, offsetX: profile.logo_offset_x, offsetY: profile.logo_offset_y })
    setSavedProfile(profile)
  }

  const updateOffice = (key: string, patch: Partial<OfficeDraft>) => {
    setOffices((previous) => previous.map((office) => (office.key === key ? { ...office, ...patch } : office)))
  }

  const addOffice = () => {
    setOffices((previous) => [
      ...previous,
      { key: newOfficeKey(), title: '', city: '', address: '', isDefault: previous.length === 0 },
    ])
  }

  const removeOffice = (key: string) => {
    setOffices((previous) => {
      const remaining = previous.filter((office) => office.key !== key)
      if (remaining.length > 0 && !remaining.some((office) => office.isDefault)) {
        remaining[0] = { ...remaining[0], isDefault: true }
      }
      return remaining
    })
  }

  const setDefaultOffice = (key: string) => {
    setOffices((previous) => previous.map((office) => ({ ...office, isDefault: office.key === key })))
  }

  const handleLogoChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (file === undefined) return
    setLogoError(null)
    if (!LOGO_ALLOWED_MIME.includes(file.type)) {
      setLogoError('Допустимы только PNG, JPEG и WebP')
      return
    }
    if (file.size > LOGO_MAX_BYTES) {
      setLogoError('Логотип больше 512 КБ')
      return
    }
    try {
      setLogoDataUrl(await readAsDataUrl(file))
      setLogoCrop(DEFAULT_LOGO_CROP)
    } catch {
      setLogoError('Не удалось прочитать файл')
    }
  }

  const loadProfile = useCallback(async () => {
    try {
      applyProfile(await fetchEmployerProfile())
      setLoadError(null)
    } catch (exception) {
      if (exception instanceof ApiError) setLoadError(exception.detail)
      else setLoadError('Не удалось загрузить профиль компании')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void Promise.resolve().then(loadProfile)
  }, [loadProfile])

  const loadATSConfiguration = useCallback(async () => {
    setATSLoading(true)
    setATSError(null)
    try {
      const configuration = await fetchATSConfiguration()
      const allowedURLs = configuration.available_webhook_urls ?? (configuration.webhook_url !== null ? [configuration.webhook_url] : [])
      setATSConfiguration({ ...configuration, available_webhook_urls: allowedURLs })
      setATSWebhookUrl(configuration.webhook_url !== null && allowedURLs.includes(configuration.webhook_url) ? configuration.webhook_url : '')
    } catch (exception) {
      if (exception instanceof ApiError) setATSError(exception.detail)
      else setATSError('Не удалось загрузить настройки ATS')
    } finally {
      setATSLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadATSConfiguration()
  }, [loadATSConfiguration])

  const submitATSConfiguration = async (event: React.FormEvent) => {
    event.preventDefault()
    setATSError(null)
    setATSNotice(null)
    setATSSubmitting(true)
    try {
      const saved = await updateATSConfiguration(atsWebhookUrl || null)
      const allowedURLs = saved.available_webhook_urls ?? (saved.webhook_url !== null ? [saved.webhook_url] : [])
      setATSConfiguration({ ...saved, available_webhook_urls: allowedURLs })
      setATSWebhookUrl(saved.webhook_url ?? '')
      setATSNotice('Подключение ATS сохранено')
    } catch (exception) {
      if (exception instanceof ApiError) setATSError(exception.detail)
      else setATSError('Не удалось сохранить подключение ATS')
    } finally {
      setATSSubmitting(false)
    }
  }

  const submitProfile = async (event: React.FormEvent) => {
    event.preventDefault()
    setFormError(null)
    setSuccessNotice(null)
    if (form.companyName.trim().length === 0) {
      setFormError('Укажите название компании')
      return
    }
    if (offices.some((office) => office.city.trim().length === 0 || office.address.trim().length === 0)) {
      setFormError('У каждого офиса укажите город и адрес')
      return
    }
    setIsSubmitting(true)
    try {
      const contacts: Record<string, string> = { ...(savedProfile?.contacts ?? {}) }
      if (form.contactEmail.trim().length > 0) contacts.email = form.contactEmail.trim()
      else delete contacts.email
      if (form.contactPhone.trim().length > 0) contacts.phone = form.contactPhone.trim()
      else delete contacts.phone
      const officePayload: CompanyOfficePayload[] = offices.map((office) => ({
        title: office.title.trim(),
        city: office.city.trim(),
        address: office.address.trim(),
        is_default: office.isDefault,
      }))
      const saved = await updateEmployerProfile({
        company_name: form.companyName.trim(),
        description: form.description.trim(),
        contacts,
        offices: officePayload,
        logo_data_url: logoDataUrl ?? '',
        logo_zoom: logoCrop.zoom,
        logo_offset_x: logoCrop.offsetX,
        logo_offset_y: logoCrop.offsetY,
      })
      setSavedProfile(saved)
      setSuccessNotice('Профиль компании сохранён')
    } catch (exception) {
      if (exception instanceof ApiError) setFormError(exception.detail)
      else setFormError('Не удалось сохранить профиль')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-[1280px] flex-col gap-6 px-4 py-8 sm:px-6">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-1">
        <h1 className="font-mono text-display font-extrabold tracking-tight text-ink">Профиль компании</h1>
        <p className="font-sans text-body text-ink-secondary">
          Название подставляется в приглашения. Описание и контакты видны после взаимного подтверждения.
        </p>
      </div>

      <Toast message={successNotice} onClose={() => setSuccessNotice(null)} />
      {loadError !== null ? (
        <div className="flex items-center gap-3 rounded-panel bg-pvn-red/10 px-5 py-4 font-sans text-caption text-pvn-red-ink shadow-raised-sm">
          <span className="material-symbols-outlined text-[18px]">error</span>
          <span>{loadError}</span>
          <button className="ml-auto font-mono font-semibold underline" onClick={() => void loadProfile()} type="button">Повторить</button>
        </div>
      ) : null}

      {isLoading ? (
        <SkeletonForm />
      ) : loadError === null ? (
        <>
        <form className="mx-auto flex w-full max-w-3xl flex-col gap-5 rounded-panel bg-raised p-6 shadow-raised" onSubmit={submitProfile}>
          <div className="flex flex-col gap-1.5">
            <label className="label-cap" htmlFor="company-name">Название компании *</label>
            <input
              className="field text-[16px] font-medium"
              id="company-name"
              onChange={(event) => setForm({ ...form, companyName: event.target.value })}
              placeholder="ООО «ТехноСфера»"
              required
              type="text"
              value={form.companyName}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="font-sans text-[12px] font-semibold uppercase tracking-wider text-ink-muted" htmlFor="company-description">О компании</label>
            <textarea
              className="field resize-none"
              id="company-description"
              onChange={(event) => setForm({ ...form, description: event.target.value })}
              placeholder="Продуктовая компания из финтех-сегмента, 40 инженеров, стек Python и Kotlin…"
              rows={4}
              value={form.description}
            />
          </div>
          <div className="flex flex-col gap-3 rounded-2xl bg-inset p-4 shadow-inset-sm">
            <span className="font-mono text-[13px] font-bold text-ink">Логотип</span>
            <div className="flex flex-wrap items-center gap-4">
              <span className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-xl bg-raised shadow-raised-sm">
                {logoDataUrl !== null ? (
                  <LogoAvatar alt="Логотип компании" crop={logoCrop} size={64} src={logoDataUrl} />
                ) : (
                  <span className="material-symbols-outlined text-[28px] text-ink-muted">apartment</span>
                )}
              </span>
              <div className="flex flex-wrap items-center gap-2">
                <label className="btn-ghost cursor-pointer py-2 text-[13px]">
                  <span className="material-symbols-outlined text-[18px]">upload</span>
                  {logoDataUrl !== null ? 'Заменить' : 'Загрузить'}
                  <input accept="image/png,image/jpeg,image/webp" className="sr-only" onChange={(event) => void handleLogoChange(event)} type="file" />
                </label>
                {logoDataUrl !== null ? (
                  <button className="btn-ghost py-2 text-[13px]" onClick={() => { setLogoDataUrl(null); setLogoCrop(DEFAULT_LOGO_CROP) }} type="button">Удалить</button>
                ) : null}
              </div>
            </div>
            <span className="font-sans text-caption text-ink-secondary">PNG, JPEG или WebP, до 512 КБ.</span>
            {logoDataUrl !== null ? (
              <div className="rounded-xl bg-raised p-4 shadow-raised-sm">
                <LogoCropEditor crop={logoCrop} onChange={setLogoCrop} src={logoDataUrl} />
              </div>
            ) : null}
            {logoError !== null ? <span className="font-sans text-caption text-pvn-red-ink">{logoError}</span> : null}
          </div>
          <div className="flex flex-col gap-3 rounded-2xl bg-inset p-4 shadow-inset-sm">
            <div className="flex items-center justify-between gap-3">
              <span className="font-mono text-[13px] font-bold text-ink">Офисы</span>
              <button className="btn-ghost py-2 text-[13px]" onClick={addOffice} type="button">
                <span className="material-symbols-outlined text-[18px]">add</span>
                Добавить офис
              </button>
            </div>
            {offices.length === 0 ? (
              <span className="font-sans text-caption text-ink-secondary">Офисы не добавлены. Адрес для очных интервью можно будет указать вручную.</span>
            ) : null}
            {offices.map((office) => (
              <div className="flex flex-col gap-3 rounded-xl bg-raised p-4 shadow-raised-sm" key={office.key}>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <input
                    aria-label="Название офиса"
                    className="field"
                    onChange={(event) => updateOffice(office.key, { title: event.target.value })}
                    placeholder="Название, например «Головной»"
                    type="text"
                    value={office.title}
                  />
                  <input
                    aria-label="Город офиса"
                    className="field"
                    onChange={(event) => updateOffice(office.key, { city: event.target.value })}
                    placeholder="Город"
                    type="text"
                    value={office.city}
                  />
                </div>
                <input
                  aria-label="Адрес офиса"
                  className="field"
                  onChange={(event) => updateOffice(office.key, { address: event.target.value })}
                  placeholder="Улица, дом, офис"
                  type="text"
                  value={office.address}
                />
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <label className="flex cursor-pointer items-center gap-2 font-sans text-caption text-ink-secondary">
                    <input
                      checked={office.isDefault}
                      className="h-4 w-4 accent-pvn-blue"
                      name="default-office"
                      onChange={() => setDefaultOffice(office.key)}
                      type="radio"
                    />
                    Офис по умолчанию
                  </label>
                  <button className="font-mono text-[12px] font-semibold text-pvn-red-ink hover:underline" onClick={() => removeOffice(office.key)} type="button">
                    Удалить офис
                  </button>
                </div>
              </div>
            ))}
          </div>
          <div className="flex flex-col gap-3 rounded-2xl bg-inset p-4 shadow-inset-sm">
            <span className="flex items-center gap-2 font-mono text-[13px] font-bold text-ink">
              <span className="material-symbols-outlined text-[20px] text-pvn-blue">contact_page</span>
              Контакты
            </span>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="flex flex-col gap-1.5">
                <span className="label-cap">Email</span>
                <input
                  className="field"
                  onChange={(event) => setForm({ ...form, contactEmail: event.target.value })}
                  placeholder="hr@company.ru"
                  type="email"
                  value={form.contactEmail}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <span className="label-cap">Телефон</span>
                <input
                  className="field"
                  onChange={(event) => setForm({ ...form, contactPhone: event.target.value })}
                  placeholder="+7 900 000-00-00"
                  type="tel"
                  value={form.contactPhone}
                />
              </div>
            </div>
          </div>
          {formError !== null ? (
            <div className="flex items-center gap-2 rounded-xl bg-pvn-red/10 px-4 py-3 font-sans text-caption text-pvn-red-ink">
              <span className="material-symbols-outlined text-[18px]">error</span>
              <span>{formError}</span>
            </div>
          ) : null}
          <div className="flex items-center justify-end">
            <button className="btn-primary" disabled={isSubmitting} type="submit">
              <span className="material-symbols-outlined text-[18px]">save</span>
              {isSubmitting ? 'Сохранение…' : 'Сохранить'}
            </button>
          </div>
        </form>
        <section className="mx-auto flex w-full max-w-3xl flex-col gap-4 rounded-panel bg-raised p-6 shadow-raised" aria-labelledby="ats-connection-title">
          <div className="flex flex-col gap-1">
            <h2 className="font-mono text-h2 font-bold text-ink" id="ats-connection-title">Подключение ATS</h2>
            <p className="font-sans text-caption text-ink-secondary">Выберите адрес, одобренный администратором. Секреты и произвольные адреса здесь не вводятся.</p>
          </div>
          {atsLoading ? <div className="h-12 animate-pulse rounded-xl bg-inset" /> : atsConfiguration !== null ? (
            <form className="flex flex-col gap-4" onSubmit={submitATSConfiguration}>
              <div className="flex flex-col gap-1.5">
                <label className="label-cap" htmlFor="ats-webhook-url">Система ATS</label>
                <select className="field cursor-pointer" id="ats-webhook-url" onChange={(event) => setATSWebhookUrl(event.target.value)} value={atsWebhookUrl}>
                  <option value="">Не подключать</option>
                  {(atsConfiguration.available_webhook_urls ?? []).map((url) => <option key={url} value={url}>{url}</option>)}
                </select>
                {(atsConfiguration.available_webhook_urls ?? []).length === 0 ? <span className="font-sans text-caption text-ink-secondary">Доступных подключений пока нет. Обратитесь к администратору.</span> : null}
              </div>
              {atsError !== null ? <div className="rounded-xl bg-pvn-red/10 px-4 py-3 font-sans text-caption text-pvn-red-ink">{atsError}</div> : null}
              {atsNotice !== null ? <div className="rounded-xl bg-good/10 px-4 py-3 font-sans text-caption text-good-ink">{atsNotice}</div> : null}
              <div className="flex justify-end">
                <button className="btn-primary" disabled={atsSubmitting || (atsConfiguration.available_webhook_urls ?? []).length === 0 && atsWebhookUrl.length > 0} type="submit">
                  <span className="material-symbols-outlined text-[18px]">link</span>
                  {atsSubmitting ? 'Сохранение…' : 'Сохранить подключение'}
                </button>
              </div>
            </form>
          ) : <div className="rounded-xl bg-pvn-red/10 px-4 py-3 font-sans text-caption text-pvn-red-ink">{atsError ?? 'Настройки ATS недоступны'}</div>}
        </section>
        </>
      ) : null}
    </div>
  )
}
