import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError } from '../../api/client'
import { downloadProfilePdf, uploadResume, anonymousCandidateId } from '../../api/platform'
import { fetchCandidateProfile, updateCandidateProfile, updateGrade, updateVisibility } from '../../api/auth'
import type { CandidateProfile } from '../../api/auth'
import { useAuth } from '../../auth/AuthContext'
import { fetchTestSessions } from '../../api/testing'
import type { TestSession } from '../../api/testing'
import { formatExperience, formatIsoDate, formatNumberInput, gradeLabel } from '../../lib/format'
import { LogoAvatar } from '../../components/LogoAvatar'
import { LogoCropEditor } from '../../components/LogoCropEditor'
import { Toast } from '../../components/Toast'
import { DEFAULT_LOGO_CROP } from '../../lib/logoCrop'
import type { LogoCrop } from '../../lib/logoCrop'

const AVATAR_ALLOWED_MIME = ['image/png', 'image/jpeg', 'image/webp']
const AVATAR_MAX_BYTES = 512 * 1024

function readAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(file)
  })
}

const specializations = ['backend', 'frontend', 'data', 'devops', 'mobile', 'qa', 'design']
const grades = ['junior', 'middle', 'senior']
const gradeRank: Record<string, number> = { junior: 0, middle: 1, senior: 2 }

const specializationLabels: Record<string, string> = {
  backend: 'Backend',
  frontend: 'Frontend',
  data: 'Data',
  devops: 'DevOps',
  mobile: 'Mobile',
  qa: 'QA',
  design: 'Дизайн',
}

interface ProfileForm {
  full_name: string
  specialization: string
  stack: string
  years_of_experience: string
  soft_skills: string
  email: string
  phone: string
  pvn_id: string
}

function formFromProfile(profile: CandidateProfile, fallbackEmail = ''): ProfileForm {
  return {
    full_name: profile.full_name ?? '',
    specialization: profile.specialization ?? '',
    stack: profile.stack.join(', '),
    years_of_experience: profile.years_of_experience === null ? '' : String(profile.years_of_experience),
    soft_skills: profile.soft_skills.join(', '),
    email: profile.contacts?.email ?? fallbackEmail,
    phone: profile.contacts?.phone ?? '',
    pvn_id: profile.pvn_id ?? '',
  }
}

function anonymousId(profileId: number): string {
  return anonymousCandidateId(profileId)
}

export function CandidateProfilePage() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const [profile, setProfile] = useState<CandidateProfile | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isEditing, setIsEditing] = useState(false)
  const [form, setForm] = useState<ProfileForm | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [experienceError, setExperienceError] = useState<string | null>(null)
  const [gradeValue, setGradeValue] = useState('')
  const [gradeError, setGradeError] = useState<string | null>(null)
  const [isGradeBusy, setIsGradeBusy] = useState(false)
  const [isVisibilityBusy, setIsVisibilityBusy] = useState(false)
  const [appliedFields, setAppliedFields] = useState<string[]>([])
  const [resumeError, setResumeError] = useState<string | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [isDownloading, setIsDownloading] = useState(false)
  const [pdfPreviewUrl, setPdfPreviewUrl] = useState<string | null>(null)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [isPreviewLoading, setIsPreviewLoading] = useState(false)
  const [skillInput, setSkillInput] = useState('')
  const [isSkillBusy, setIsSkillBusy] = useState(false)
  const [skillError, setSkillError] = useState<string | null>(null)
  const [avatarDataUrl, setAvatarDataUrl] = useState<string | null>(null)
  const [avatarCrop, setAvatarCrop] = useState<LogoCrop>(DEFAULT_LOGO_CROP)
  const [avatarError, setAvatarError] = useState<string | null>(null)
  const [sessions, setSessions] = useState<TestSession[]>([])
  const [saveNotice, setSaveNotice] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const closePreview = useCallback(() => {
    setPdfPreviewUrl((previous) => {
      if (previous !== null) URL.revokeObjectURL(previous)
      return null
    })
  }, [])

  useEffect(() => {
    if (pdfPreviewUrl === null) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closePreview()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [pdfPreviewUrl, closePreview])

  const load = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const loaded = await fetchCandidateProfile()
      setProfile(loaded)
      setGradeValue(loaded.grade ?? '')
      setAvatarDataUrl(loaded.avatar_data_url)
      setAvatarCrop({
        zoom: loaded.avatar_zoom ?? DEFAULT_LOGO_CROP.zoom,
        offsetX: loaded.avatar_offset_x ?? DEFAULT_LOGO_CROP.offsetX,
        offsetY: loaded.avatar_offset_y ?? DEFAULT_LOGO_CROP.offsetY,
      })
      try {
        setSessions(await fetchTestSessions())
      } catch {
        setSessions([])
      }
    } catch (exception) {
      if (exception instanceof ApiError) setError(exception.detail)
      else setError('Не удалось связаться с сервером')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const saveProfile = async () => {
    if (form === null) return
    setFormError(null)
    setExperienceError(null)
    const years = formatNumberInput(form.years_of_experience)
    if (form.years_of_experience.trim() !== '') {
      if (years === null) {
        setExperienceError('Укажите число, например 5 или 6.5')
        return
      }
      if (years < 0) {
        setExperienceError('Опыт не может быть отрицательным')
        return
      }
      if (years > 60) {
        setExperienceError('Укажите реальный стаж — до 60 лет')
        return
      }
    }
    const contacts: Record<string, string> = {}
    if (form.email.trim() !== '') contacts.email = form.email.trim()
    if (form.phone.trim() !== '') contacts.phone = form.phone.trim()
    setIsSaving(true)
    try {
      const updated = await updateCandidateProfile({
        full_name: form.full_name.trim() === '' ? null : form.full_name.trim(),
        specialization: form.specialization,
        stack: form.stack.split(',').map((item) => item.trim()).filter((item) => item !== ''),
        years_of_experience: years,
        soft_skills: form.soft_skills.split(',').map((item) => item.trim()).filter((item) => item !== ''),
        contacts: Object.keys(contacts).length > 0 ? contacts : null,
        pvn_id: form.pvn_id.trim(),
        avatar_data_url: avatarDataUrl ?? '',
        avatar_zoom: avatarCrop.zoom,
        avatar_offset_x: avatarCrop.offsetX,
        avatar_offset_y: avatarCrop.offsetY,
      })
      setProfile(updated)
      setGradeValue(updated.grade ?? '')
      setIsEditing(false)
      setSaveNotice('Профиль сохранён')
      window.dispatchEvent(new Event('syntax:profile-updated'))
    } catch (exception) {
      if (exception instanceof ApiError) setFormError(exception.detail)
      else setFormError('Не удалось связаться с сервером')
    } finally {
      setIsSaving(false)
    }
  }

  const handleAvatarChange = async (event: { target: HTMLInputElement }) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (file === undefined) return
    setAvatarError(null)
    if (!AVATAR_ALLOWED_MIME.includes(file.type)) {
      setAvatarError('Допустимы только PNG, JPEG и WebP')
      return
    }
    if (file.size > AVATAR_MAX_BYTES) {
      setAvatarError('Файл больше 512 КБ')
      return
    }
    try {
      setAvatarDataUrl(await readAsDataUrl(file))
      setAvatarCrop(DEFAULT_LOGO_CROP)
    } catch {
      setAvatarError('Не удалось прочитать файл')
    }
  }

  const changeGrade = async () => {
    if (gradeValue === '' || gradeValue === profile?.grade) return
    setGradeError(null)
    setIsGradeBusy(true)
    try {
      const updated = await updateGrade(gradeValue)
      setProfile(updated)
    } catch (exception) {
      if (exception instanceof ApiError) setGradeError(exception.detail)
      else setGradeError('Не удалось связаться с сервером')
    } finally {
      setIsGradeBusy(false)
    }
  }

  const toggleVisibility = async () => {
    if (profile === null) return
    setIsVisibilityBusy(true)
    setError(null)
    try {
      const updated = await updateVisibility(!profile.is_visible)
      setProfile(updated)
    } catch (exception) {
      if (exception instanceof ApiError) setError(exception.detail)
      else setError('Не удалось связаться с сервером')
    } finally {
      setIsVisibilityBusy(false)
    }
  }

  const uploadFile = async (file: File) => {
    setResumeError(null)
    setIsUploading(true)
    try {
      const result = await uploadResume(file)
      setAppliedFields(result.applied)
      await load()
    } catch (exception) {
      if (exception instanceof ApiError) setResumeError(exception.detail)
      else setResumeError('Не удалось связаться с сервером')
    } finally {
      setIsUploading(false)
      if (fileInputRef.current !== null) fileInputRef.current.value = ''
    }
  }

  const downloadPdf = async () => {
    setIsDownloading(true)
    setResumeError(null)
    try {
      const blob = await downloadProfilePdf()
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = 'profile.pdf'
      anchor.click()
      URL.revokeObjectURL(url)
    } catch (exception) {
      if (exception instanceof ApiError) setResumeError(exception.detail)
      else setResumeError('Не удалось скачать PDF-профиль')
    } finally {
      setIsDownloading(false)
    }
  }

  const previewPdf = async () => {
    setIsPreviewLoading(true)
    setPreviewError(null)
    try {
      const blob = await downloadProfilePdf()
      setPdfPreviewUrl((previous) => {
        if (previous !== null) URL.revokeObjectURL(previous)
        return URL.createObjectURL(blob)
      })
    } catch (exception) {
      if (exception instanceof ApiError) setPreviewError(exception.detail)
      else setPreviewError('Не удалось открыть предпросмотр профиля')
    } finally {
      setIsPreviewLoading(false)
    }
  }

  const addSkill = async () => {
    const value = skillInput.trim()
    if (value === '' || profile === null) return
    if (profile.stack.some((item) => item.toLowerCase() === value.toLowerCase())) {
      setSkillError('Такой навык уже есть в профиле')
      return
    }
    setSkillError(null)
    setIsSkillBusy(true)
    try {
      const updated = await updateCandidateProfile({
        full_name: profile.full_name,
        specialization: profile.specialization ?? '',
        stack: [...profile.stack, value],
        years_of_experience: profile.years_of_experience,
        soft_skills: profile.soft_skills,
        contacts: profile.contacts,
      })
      setProfile(updated)
      setSkillInput('')
    } catch (exception) {
      if (exception instanceof ApiError) setSkillError(exception.detail)
      else setSkillError('Не удалось добавить навык')
    } finally {
      setIsSkillBusy(false)
    }
  }

  if (isLoading) {
    return (
      <div className="mx-auto flex w-full max-w-[1280px] flex-col gap-6 px-4 py-8 sm:px-6">
        <div className="h-9 w-1/3 animate-pulse rounded-lg bg-inset" />
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-12">
          <div className="h-96 animate-pulse rounded-panel bg-raised shadow-raised xl:col-span-8" />
          <div className="h-96 animate-pulse rounded-panel bg-raised shadow-raised xl:col-span-4" />
        </div>
      </div>
    )
  }

  if (profile === null) {
    return (
      <div className="mx-auto flex w-full max-w-[1280px] flex-col gap-4 px-4 py-8 sm:px-6">
        {error !== null ? (
          <div className="flex items-center gap-3 rounded-panel bg-pvn-red/10 px-5 py-4 font-sans text-caption text-pvn-red-ink shadow-raised-sm">
            <span className="material-symbols-outlined text-[18px]">error</span>
            <span>{error}</span>
          </div>
        ) : null}
        <button className="btn-blue self-start" onClick={() => void load()} type="button">Повторить загрузку</button>
      </div>
    )
  }

  const filled = Math.min(
    100,
    20 + profile.stack.length * 6 + (profile.full_name !== null ? 15 : 0) + (profile.years_of_experience !== null ? 15 : 0) + (profile.contacts !== null ? 10 : 0),
  )

  return (
    <div className="mx-auto flex w-full max-w-[1280px] flex-col gap-6 px-4 py-8 sm:px-6">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="font-mono text-display font-extrabold tracking-tight text-ink">Профиль кандидата</h1>
        <span className="stat-pill bg-pvn-blue text-white">Профиль заполнен на {filled}%</span>
      </div>

      <Toast message={saveNotice} onClose={() => setSaveNotice(null)} />

      {error !== null ? (
        <div className="flex items-center gap-3 rounded-panel bg-pvn-red/10 px-5 py-4 font-sans text-caption text-pvn-red-ink shadow-raised-sm">
          <span className="material-symbols-outlined text-[18px]">error</span>
          <span>{error}</span>
        </div>
      ) : null}

      <div className="grid grid-cols-1 items-start gap-6 xl:grid-cols-12">
        <section className="flex flex-col gap-5 xl:col-span-8">
          <div className="flex flex-col gap-5 rounded-panel bg-raised p-6 shadow-raised sm:flex-row sm:items-center">
            <div className="flex min-w-0 flex-1 items-center gap-5">
              <span className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-full bg-inset shadow-inset-sm">
                {profile.avatar_data_url !== null ? (
                  <LogoAvatar
                    alt="Аватар кандидата"
                    crop={isEditing ? avatarCrop : {
                      zoom: profile.avatar_zoom ?? 1,
                      offsetX: profile.avatar_offset_x ?? 0,
                      offsetY: profile.avatar_offset_y ?? 0,
                    }}
                    size={64}
                    src={profile.avatar_data_url}
                  />
                ) : (
                  <span className="material-symbols-outlined text-[32px] text-ink-muted">person</span>
                )}
              </span>
              <div className="min-w-0 flex-1">
                <h2 className="font-mono text-[22px] font-extrabold tracking-tight text-ink">
                  {profile.full_name ?? 'Без имени'}
                </h2>
                <p className="font-mono text-[13px] text-ink-secondary">
                  Кандидат{profile.specialization !== null ? ` · ${specializationLabels[profile.specialization] ?? profile.specialization}` : ''}
                </p>
                {profile.is_pvn_verified ? (
                  <span className="mt-1 flex w-fit items-center gap-1 rounded-lg bg-good/15 px-2 py-0.5 font-mono text-[11px] font-semibold text-good-ink">
                    <span className="material-symbols-outlined text-[13px] leading-none">verified</span>
                    ПВН ID подтверждён{profile.pvn_id ? `: ${profile.pvn_id}` : ''}
                  </span>
                ) : null}
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-2 sm:flex-col sm:items-stretch">
              <button
                className="btn-blue py-2 text-[13px]"
                onClick={() => {
                  setForm(formFromProfile(profile, user?.email ?? ''))
                  setFormError(null)
                  setIsEditing(true)
                }}
                type="button"
              >
                <span className="material-symbols-outlined text-[16px]">edit</span>
                Редактировать
              </button>
            </div>
          </div>

          <div className="rounded-panel bg-raised p-6 shadow-raised">
            {isEditing && form !== null ? (
              <form
                className="flex flex-col gap-4"
                noValidate
                onSubmit={(event) => {
                  event.preventDefault()
                  void saveProfile()
                }}
              >
                <span className="label-cap">Полные данные</span>
                <div className="flex flex-col gap-3 rounded-2xl bg-inset p-4 shadow-inset-sm">
                  <span className="font-mono text-[13px] font-bold text-ink">Аватар</span>
                  <div className="flex flex-wrap items-center gap-4">
                    <span className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-full bg-raised shadow-raised-sm">
                      {avatarDataUrl !== null ? (
                        <LogoAvatar alt="Аватар кандидата" crop={avatarCrop} size={64} src={avatarDataUrl} />
                      ) : (
                        <span className="material-symbols-outlined text-[28px] text-ink-muted">person</span>
                      )}
                    </span>
                    <div className="flex flex-wrap items-center gap-2">
                      <label className="btn-ghost cursor-pointer py-2 text-[13px]">
                        <span className="material-symbols-outlined text-[18px]">upload</span>
                        {avatarDataUrl !== null ? 'Заменить' : 'Загрузить'}
                        <input accept="image/png,image/jpeg,image/webp" className="sr-only" onChange={(event) => void handleAvatarChange(event)} type="file" />
                      </label>
                      {avatarDataUrl !== null ? (
                        <button className="btn-ghost py-2 text-[13px]" onClick={() => { setAvatarDataUrl(null); setAvatarCrop(DEFAULT_LOGO_CROP) }} type="button">Удалить</button>
                      ) : null}
                    </div>
                  </div>
                  <span className="font-sans text-caption text-ink-secondary">PNG, JPEG или WebP, до 512 КБ.</span>
                  {avatarDataUrl !== null ? (
                    <div className="rounded-xl bg-raised p-4 shadow-raised-sm">
                      <LogoCropEditor crop={avatarCrop} onChange={setAvatarCrop} src={avatarDataUrl} />
                    </div>
                  ) : null}
                  {avatarError !== null ? <span className="font-sans text-caption text-pvn-red-ink">{avatarError}</span> : null}
                </div>
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <div className="flex flex-col gap-1.5">
                    <label className="label-cap" htmlFor="profile-full-name">ФИО</label>
                    <input className="field" id="profile-full-name" onChange={(event) => setForm({ ...form, full_name: event.target.value })} placeholder="Иванов Иван" type="text" value={form.full_name} />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <label className="label-cap" htmlFor="profile-specialization">Специализация</label>
                    <select className="field cursor-pointer" id="profile-specialization" onChange={(event) => setForm({ ...form, specialization: event.target.value })} value={form.specialization}>
                      {specializations.map((item) => (<option key={item} value={item}>{specializationLabels[item]}</option>))}
                    </select>
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <label className="label-cap" htmlFor="profile-stack">Стек (через запятую)</label>
                    <input className="field" id="profile-stack" onChange={(event) => setForm({ ...form, stack: event.target.value })} placeholder="Python, PostgreSQL, Kafka" type="text" value={form.stack} />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <label className="label-cap" htmlFor="profile-years">Опыт (лет)</label>
                    <input
                      className={`field ${experienceError !== null ? 'border-pvn-red/50 ring-1 ring-pvn-red/30' : ''}`}
                      id="profile-years"
                      inputMode="decimal"
                      onChange={(event) => setForm({ ...form, years_of_experience: event.target.value })}
                      placeholder="5"
                      type="text"
                      value={form.years_of_experience}
                    />
                    <span className="font-sans text-[12px] text-ink-secondary">Можно указать дробные значения, например 6.5</span>
                    {experienceError !== null ? (
                      <span className="font-sans text-[12px] font-semibold text-pvn-red-ink">{experienceError}</span>
                    ) : null}
                  </div>
                  <div className="flex flex-col gap-1.5 md:col-span-2">
                    <label className="label-cap" htmlFor="profile-soft-skills">Soft skills (через запятую)</label>
                    <input className="field" id="profile-soft-skills" onChange={(event) => setForm({ ...form, soft_skills: event.target.value })} placeholder="Коммуникация, ответственность" type="text" value={form.soft_skills} />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <label className="label-cap" htmlFor="profile-email">Email</label>
                    <input className="field" id="profile-email" onChange={(event) => setForm({ ...form, email: event.target.value })} placeholder="name@mail.ru" type="email" value={form.email} />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <label className="label-cap" htmlFor="profile-phone">Телефон</label>
                    <input className="field" id="profile-phone" onChange={(event) => setForm({ ...form, phone: event.target.value })} placeholder="+7 900 000-00-00" type="tel" value={form.phone} />
                  </div>
                  <div className="flex flex-col gap-1.5 md:col-span-2">
                    <label className="label-cap" htmlFor="profile-pvn-id">ПВН ID (необязательно)</label>
                    <input
                      autoComplete="off"
                      className="field"
                      id="profile-pvn-id"
                      onChange={(event) => setForm({ ...form, pvn_id: event.target.value })}
                      placeholder="PVN-100001"
                      type="text"
                      value={form.pvn_id}
                    />
                    <span className="font-sans text-[12px] text-ink-secondary">
                      {profile.is_pvn_verified
                        ? 'ПВН ID указан — работодатели видят отметку о подтверждении.'
                        : 'Укажите ID из личного кабинета ПВН, чтобы работодатели видели отметку о подтверждении. Поле необязательное.'}
                    </span>
                  </div>
                </div>
                {formError !== null ? (
                  <div className="flex items-center gap-2 rounded-xl bg-pvn-red/10 px-4 py-3 font-sans text-caption text-pvn-red-ink">
                    <span className="material-symbols-outlined text-[18px]">error</span>
                    <span>{formError}</span>
                  </div>
                ) : null}
                <div className="flex items-center gap-3">
                  <button className="btn-primary" disabled={isSaving} type="submit">{isSaving ? 'Сохранение…' : 'Сохранить профиль'}</button>
                  <button className="btn-ghost" onClick={() => setIsEditing(false)} type="button">Отмена</button>
                </div>
              </form>
            ) : (
              <div className="flex flex-col gap-5">
                <span className="label-cap">Навыки и стек</span>
                <div className="flex flex-wrap gap-2">
                  {profile.stack.length === 0 ? (
                    <span className="font-sans text-caption text-ink-secondary">Стек не указан</span>
                  ) : (
                    profile.stack.map((item) => (<span className="chip-blue" key={item}>{item}</span>))
                  )}
                </div>
                {profile.stack.length > 0 ? (
                  <span className="font-sans text-caption text-ink-secondary">Заявлено кандидатом. Подтверждается результатами тестирования.</span>
                ) : null}
                <div className="grid grid-cols-1 gap-x-8 gap-y-2 md:grid-cols-2">
                  <div className="flex items-center justify-between gap-3 border-b border-ink/10 py-2.5">
                    <span className="label-cap">Опыт</span>
                    <span className="font-mono text-[13px] font-semibold text-ink">{formatExperience(profile.years_of_experience)}</span>
                  </div>
                  <div className="flex items-center justify-between gap-3 border-b border-ink/10 py-2.5">
                    <span className="label-cap">Формат</span>
                    <span className="font-mono text-[13px] font-semibold text-ink">Гибрид / удалённо</span>
                  </div>
                  <div className="flex items-center justify-between gap-3 border-b border-ink/10 py-2.5">
                    <span className="label-cap">Email</span>
                    <span className="font-mono text-[13px] font-semibold text-ink">{profile.contacts?.email ?? '—'}</span>
                  </div>
                  <div className="flex items-center justify-between gap-3 border-b border-ink/10 py-2.5">
                    <span className="label-cap">Телефон</span>
                    <span className="font-mono text-[13px] font-semibold text-ink">{profile.contacts?.phone ?? '—'}</span>
                  </div>
                </div>
                {profile.soft_skills.length > 0 ? (
                  <div className="flex flex-col gap-2">
                    <span className="label-cap">Soft skills</span>
                    <div className="flex flex-wrap gap-2">
                      {profile.soft_skills.map((item) => (<span className="chip" key={item}>{item}</span>))}
                    </div>
                  </div>
                ) : null}
                <div className="flex flex-col gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <input
                      className="field w-full max-w-xs py-2.5"
                      onChange={(event) => setSkillInput(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter') {
                          event.preventDefault()
                          void addSkill()
                        }
                      }}
                      placeholder="Новый навык и Enter"
                      type="text"
                      value={skillInput}
                    />
                    <button
                      className="btn-blue py-2.5 text-[13px]"
                      disabled={isSkillBusy || skillInput.trim() === ''}
                      onClick={() => void addSkill()}
                      type="button"
                    >
                      <span className="material-symbols-outlined text-[18px]">add</span>
                      {isSkillBusy ? 'Добавление…' : 'Добавить'}
                    </button>
                  </div>
                  {skillError !== null ? (
                    <span className="font-sans text-caption text-pvn-red-ink">{skillError}</span>
                  ) : null}
                </div>
              </div>
            )}
          </div>

          <div className="flex flex-col gap-4 rounded-panel bg-raised p-6 shadow-raised">
            <h2 className="flex items-center gap-2 font-mono text-label uppercase tracking-wider text-ink">
              <span className="material-symbols-outlined text-[20px] text-pvn-blue">workspace_premium</span>
              Смена грейда
            </h2>
            {(() => {
              const currentRank = gradeRank[profile.grade ?? ''] ?? -1
              const selectedRank = gradeRank[gradeValue] ?? -1
              const isPromotion = gradeValue !== '' && selectedRank > currentRank
              return (
                <>
                  <div className="flex flex-col items-stretch gap-4 sm:flex-row sm:items-end">
                    <div className="flex flex-1 flex-col gap-1.5">
                      <label className="label-cap" htmlFor="grade-select">Целевой грейд</label>
                      <select className="field cursor-pointer" id="grade-select" onChange={(event) => setGradeValue(event.target.value)} value={gradeValue}>
                        {grades.map((item) => (<option key={item} value={item}>{gradeLabel(item)}</option>))}
                      </select>
                    </div>
                    <button
                      className={isPromotion ? 'btn-blue' : 'btn-ghost'}
                      disabled={isGradeBusy || gradeValue === '' || gradeValue === profile.grade}
                      onClick={() => {
                        if (isPromotion) navigate(`/candidate/testing?grade=${gradeValue}`)
                        else void changeGrade()
                      }}
                      type="button"
                    >
                      {isPromotion ? (
                        <>
                          <span className="material-symbols-outlined text-[18px]">quiz</span>
                          {isGradeBusy ? 'Отправка…' : 'Пройти тест на грейд'}
                        </>
                      ) : isGradeBusy ? 'Отправка…' : 'Понизить грейд'}
                    </button>
                  </div>
                  <p className="font-sans text-caption text-ink-secondary">
                    {gradeValue === profile.grade
                      ? 'Выберите другой грейд.'
                      : isPromotion
                        ? `Повышение до ${gradeValue} подтверждается тестом: при успехе грейд обновится автоматически.`
                        : `Понижение до ${gradeValue} применяется сразу. Дальше смена грейда будет доступна через 3 месяца.`}
                  </p>
                  {gradeError !== null ? (
                    <div className="flex items-center gap-2 rounded-xl bg-pvn-red/10 px-4 py-3 font-sans text-caption text-pvn-red-ink">
                      <span className="material-symbols-outlined text-[16px]">schedule</span>
                      <span>{gradeError}</span>
                    </div>
                  ) : null}
                </>
              )
            })()}
          </div>

          <div className="flex flex-col gap-4 rounded-panel bg-raised p-6 shadow-raised">
            <h2 className="flex items-center gap-2 font-mono text-label uppercase tracking-wider text-ink">
              <span className="material-symbols-outlined text-[20px] text-pvn-blue">quiz</span>
              Тестирование
            </h2>
            {(() => {
              const completed = sessions.filter((item) => item.status === 'completed')
              const best = completed.reduce<number | null>((acc, item) => {
                if (typeof item.result_score !== 'number') return acc
                return acc === null ? item.result_score : Math.max(acc, item.result_score)
              }, null)
              if (completed.length === 0) {
                return (
                  <div className="flex flex-col gap-3 rounded-xl bg-inset p-4 shadow-inset-sm sm:flex-row sm:items-center sm:justify-between">
                    <span className="font-sans text-caption text-ink-secondary">Вы ещё не проходили тестирование. Результат появится здесь и попадёт в балл ПВН.</span>
                    <button className="btn-blue shrink-0 py-2 text-[13px]" onClick={() => navigate('/candidate/testing')} type="button">
                      <span className="material-symbols-outlined text-[18px]">play_arrow</span>
                      Пройти тест
                    </button>
                  </div>
                )
              }
              return (
                <>
                  <div className="flex flex-wrap items-center gap-3">
                    <span className={`stat-pill ${profile.grade_confirmed ? 'bg-good/15 text-good-ink' : 'bg-warn/15 text-warn-ink'}`}>
                      {profile.grade_confirmed ? 'Грейд подтверждён тестом' : 'Грейд не подтверждён тестом'}
                    </span>
                    {best !== null ? (
                      <span className="stat-pill bg-pvn-blue/10 text-pvn-blue">Лучший результат: {best} / 100</span>
                    ) : null}
                    <span className="stat-pill bg-sunken text-ink-secondary">Сессий завершено: {completed.length}</span>
                  </div>
                  <div className="flex flex-col divide-y divide-ink/10">
                    {sessions.map((item) => {
                      const passed = typeof item.result_score === 'number' && item.verdict !== 'suggest_lower'
                      return (
                        <div className="flex items-center justify-between gap-4 py-3 first:pt-0 last:pb-0" key={item.id}>
                          <div className="flex flex-col">
                            <span className="font-mono text-[13px] font-semibold uppercase tracking-wider text-ink">{gradeLabel(item.grade)}</span>
                            <span className="font-sans text-caption text-ink-secondary">
                              {item.status === 'completed'
                                ? `${item.correct_count ?? 0} из ${item.task_count} верно${item.completed_at ? ` · ${formatIsoDate(item.completed_at)}` : ''}`
                                : 'В процессе · незавершённый тест'}
                            </span>
                          </div>
                          <div className="flex items-center gap-4">
                            {typeof item.result_score === 'number' ? (
                              <span className={`font-mono text-[15px] font-bold ${passed ? 'text-good-ink' : 'text-pvn-red-ink'}`}>{item.result_score} / 100</span>
                            ) : null}
                            <span className={`stat-pill ${item.status === 'completed' ? 'bg-good/15 text-good-ink' : 'bg-pvn-blue/10 text-pvn-blue'}`}>
                              {item.status === 'completed' ? 'Завершена' : 'В процессе'}
                            </span>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                  <button className="btn-ghost self-start py-2 text-[13px]" onClick={() => navigate('/candidate/testing')} type="button">
                    <span className="material-symbols-outlined text-[18px]">history</span>
                    Открыть тестирование
                  </button>
                </>
              )
            })()}
          </div>

          <div className="flex flex-col gap-4 rounded-panel bg-raised p-6 shadow-raised">
            <h2 className="flex items-center gap-2 font-mono text-label uppercase tracking-wider text-ink">
              <span className="material-symbols-outlined text-[20px] text-pvn-blue">description</span>
              Резюме и PDF-профиль
            </h2>
            <div className="flex flex-col items-stretch gap-3 sm:flex-row sm:items-center">
              <input
                accept="application/pdf"
                className="sr-only"
                id="resume-input"
                onChange={(event) => {
                  const file = event.target.files?.[0]
                  if (file !== undefined) void uploadFile(file)
                }}
                ref={fileInputRef}
                type="file"
              />
              <button className="btn-ghost flex-1" disabled={isUploading} onClick={() => fileInputRef.current?.click()} type="button">
                <span className="material-symbols-outlined text-[18px]">upload_file</span>
                {isUploading ? 'Загрузка…' : 'Загрузить резюме PDF'}
              </button>
              <button className="btn-ghost flex-1" disabled={isDownloading} onClick={() => void downloadPdf()} type="button">
                <span className="material-symbols-outlined text-[18px]">download</span>
                {isDownloading ? 'Подготовка…' : 'Скачать PDF-профиль'}
              </button>
            </div>
            {appliedFields.length > 0 ? (
              <div className="flex flex-col gap-2 rounded-xl bg-good/10 p-4">
                <span className="font-mono text-[11px] font-bold uppercase tracking-wider text-good-ink">Из резюме применены поля</span>
                <div className="flex flex-wrap gap-2">
                  {appliedFields.map((field) => (<span className="chip bg-raised" key={field}>{field}</span>))}
                </div>
              </div>
            ) : null}
            {resumeError !== null ? (
              <div className="flex items-center gap-2 rounded-xl bg-pvn-red/10 px-4 py-3 font-sans text-caption text-pvn-red-ink">
                <span className="material-symbols-outlined text-[16px]">error</span>
                <span>{resumeError}</span>
              </div>
            ) : null}
          </div>
        </section>

        <aside className="flex flex-col gap-5 xl:col-span-4">
          <div className="flex flex-col gap-4 overflow-hidden rounded-panel shadow-raised">
            <div className="relative flex items-center justify-between bg-pvn-blue px-5 py-4">
              <div className="flex flex-col">
                <span className="font-mono text-[18px] font-extrabold text-white">Кандидат {anonymousId(profile.id)}</span>
                <span className="font-mono text-[12px] text-white/75">
                  {profile.specialization !== null ? specializationLabels[profile.specialization] ?? profile.specialization : '—'} · {profile.grade ?? '—'}
                </span>
                {profile.grade !== null ? (
                  <span className="mt-1 inline-flex w-fit items-center gap-1 rounded-full bg-white/15 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-white">
                    <span className="material-symbols-outlined text-[12px]">{profile.grade_confirmed ? 'verified' : 'pending'}</span>
                    {profile.grade_confirmed && profile.grade_valid_until !== null
                      ? `Подтверждён до ${new Date(profile.grade_valid_until).toLocaleDateString('ru-RU')}`
                      : 'Не подтверждён тестом'}
                  </span>
                ) : null}
              </div>
              <div
                className="flex flex-col items-end"
                title="Балл ПВН — сводная оценка по тестам, достижениям и полноте профиля"
              >
                <div className="flex items-baseline gap-1">
                  <span className="font-mono text-[22px] font-extrabold text-white">{Math.round(profile.score)}</span>
                  <span className="font-mono text-[11px] text-white/70">/ 100</span>
                </div>
                <span className="font-mono text-[10px] uppercase tracking-wider text-white/60">Балл ПВН</span>
              </div>
            </div>
            <div className="flex items-center justify-between border-b border-ink/10 bg-raised px-5 py-2">
              <span className="font-mono text-[10px] uppercase tracking-wider text-ink-muted">
                {isEditing ? 'Сохранённый профиль' : 'Живой просмотр'}
              </span>
              <span className="stat-pill bg-pvn-blue/10 text-pvn-blue">Видно работодателям</span>
            </div>
            <div className="flex flex-col gap-4 bg-raised p-5">
              {isEditing ? (
                <span className="rounded-xl bg-inset px-3 py-2 font-sans text-[12px] text-ink-secondary shadow-inset-sm">
                  Показаны сохранённые данные. Изменения появятся здесь после «Сохранить профиль».
                </span>
              ) : null}
              <div className="flex flex-col gap-2">
                <span className="label-cap">Навыки</span>
                <div className="flex flex-wrap gap-2">
                  {profile.stack.length === 0 ? (
                    <span className="font-sans text-caption text-ink-secondary">Не указаны</span>
                  ) : (
                    profile.stack.map((item) => (<span className="chip" key={item}>{item}</span>))
                  )}
                </div>
              </div>
              <div className="flex flex-col gap-2">
                <span className="label-cap">Опыт</span>
                <span className="font-mono text-[13px] font-semibold text-ink">{formatExperience(profile.years_of_experience)}</span>
                <span className="font-mono text-[13px] font-semibold text-ink">Гибрид / удалённо</span>
              </div>
              <div className="flex flex-col gap-2.5 rounded-xl bg-inset p-3 shadow-inset-sm">
                <span className="flex items-center gap-2 font-mono text-[12px] font-bold text-ink">
                  <span className="material-symbols-outlined text-[18px] text-pvn-blue">chevron_right</span>
                  Что влияет на балл
                </span>
                <div className="flex flex-col gap-1.5">
                  {Object.entries(profile.score_breakdown).map(([key, component]) => (
                    <div className="flex flex-col gap-1" key={key}>
                      <div className="flex items-baseline justify-between font-mono text-[11px]">
                        <span className="text-ink-secondary">{component.label}</span>
                        <span className="font-bold text-pvn-blue">{Math.round(component.value)}</span>
                      </div>
                      <div className="h-2 w-full overflow-hidden rounded-full bg-sunken shadow-inset-sm">
                        <div className="h-full rounded-full bg-pvn-blue" style={{ width: `${Math.max(0, Math.min(component.value, 100))}%` }} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              <div className="flex items-center gap-2 rounded-xl bg-inset px-3 py-2 shadow-inset-sm">
                <span className="material-symbols-outlined text-[16px] text-ink-secondary">visibility</span>
                <span className="font-sans text-[12px] text-ink-secondary">Работодатели видят профиль без имени и контактов</span>
              </div>
              <button
                className="w-full text-center font-mono text-[13px] font-semibold text-pvn-blue hover:underline disabled:text-ink-muted"
                disabled={isPreviewLoading}
                onClick={() => void previewPdf()}
                type="button"
              >
                {isPreviewLoading ? 'Подготовка…' : 'Предпросмотр профиля'}
              </button>
              {previewError !== null ? (
                <span className="text-center font-sans text-caption text-pvn-red-ink">{previewError}</span>
              ) : null}
            </div>
          </div>

          <div className="flex flex-col gap-4 rounded-panel bg-raised p-5 shadow-raised">
            <div className="flex items-center justify-between gap-3">
              <div className="flex flex-col">
                <span className="label-cap">Видимость в поиске</span>
                <span className="font-mono text-[13px] font-semibold text-ink">
                  {profile.is_visible ? 'Профиль доступен работодателям' : 'Профиль скрыт'}
                </span>
              </div>
              <button
                aria-checked={profile.is_visible}
                aria-label="Видимость профиля в поиске"
                className={`relative h-7 w-12 shrink-0 rounded-full transition-colors ${profile.is_visible ? 'bg-good' : 'bg-sunken shadow-inset-sm'}`}
                disabled={isVisibilityBusy}
                onClick={() => void toggleVisibility()}
                role="switch"
                type="button"
              >
                <span aria-hidden="true" className={`absolute top-1 h-5 w-5 rounded-full transition-all ${profile.is_visible ? 'left-6 bg-white shadow-raised-sm' : 'left-1 bg-white shadow-raised-sm'}`} />
              </button>
            </div>
          </div>
        </aside>
      </div>

      {pdfPreviewUrl !== null ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-pvn-dark/60 p-4 backdrop-blur-sm" onClick={closePreview}>
          <div
            className="flex h-full max-h-[90vh] w-full max-w-4xl flex-col overflow-hidden rounded-panel bg-raised shadow-raised-lg"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-ink/10 px-6 py-4">
              <span className="font-mono text-h3 font-bold text-ink">Предпросмотр PDF-профиля</span>
              <div className="flex items-center gap-2">
                <button className="btn-blue py-2 text-[13px]" onClick={() => void downloadPdf()} type="button">
                  <span className="material-symbols-outlined text-[18px]">download</span>
                  Скачать
                </button>
                <button className="flex h-9 w-9 items-center justify-center rounded-xl text-ink-muted transition-all hover:bg-inset hover:text-ink" onClick={closePreview} title="Закрыть" type="button">
                  <span className="material-symbols-outlined text-[20px]">close</span>
                </button>
              </div>
            </div>
            <iframe className="h-full w-full flex-1 bg-inset" src={pdfPreviewUrl} title="Предпросмотр профиля" />
          </div>
        </div>
      ) : null}
    </div>
  )
}
