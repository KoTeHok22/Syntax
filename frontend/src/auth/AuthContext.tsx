import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { clearSession, getStoredUser, getToken, setSession, type AuthUser } from '../api/client'
import {
  fetchMe,
  login as apiLogin,
  register as apiRegister,
  confirmEmail as apiConfirmEmail,
  type CandidateCategory,
  type RegisterResult,
} from '../api/auth'

interface AuthContextValue {
  user: AuthUser | null
  isReady: boolean
  login: (email: string, password: string) => Promise<AuthUser>
  register: (email: string, password: string, role: AuthUser['role'], pvnId: string, category?: CandidateCategory) => Promise<RegisterResult>
  confirmEmail: (token: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [isReady, setIsReady] = useState(false)

  useEffect(() => {
    const stored = getStoredUser()
    if (stored === null || getToken() === null) {
      setIsReady(true)
      return
    }
    fetchMe()
      .then((fresh) => {
        setUser(fresh)
        setSession(getToken() as string, fresh)
      })
      .catch(() => {
        clearSession()
        setUser(null)
      })
      .finally(() => setIsReady(true))
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const tokenResponse = await apiLogin(email, password)
    const me = await fetchMe(tokenResponse.access_token)
    setSession(tokenResponse.access_token, me)
    setUser(me)
    return me
  }, [])

  const register = useCallback(
    async (email: string, password: string, role: AuthUser['role'], pvnId: string, category?: CandidateCategory) => {
      const created = await apiRegister({
        email,
        password,
        role,
        consent_accepted: true,
        pvn_id: pvnId === '' ? undefined : pvnId,
        specialization: role === 'candidate' ? category?.specialization : undefined,
        grade: role === 'candidate' ? category?.grade : undefined,
      })
      return created
    },
    [],
  )

  const confirmEmail = useCallback(async (token: string) => {
    await apiConfirmEmail(token)
  }, [])

  const logout = useCallback(() => {
    clearSession()
    setUser(null)
  }, [])

  const value = useMemo(
    () => ({ user, isReady, login, register, confirmEmail, logout }),
    [user, isReady, login, register, confirmEmail, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (context === null) throw new Error('useAuth must be used within AuthProvider')
  return context
}
