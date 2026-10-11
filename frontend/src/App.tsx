import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth/AuthContext'
import { RequireRole, Layout } from './components/Layout'
import { LoginPage } from './pages/LoginPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { ConfirmEmailPage } from './pages/ConfirmEmailPage'
import { MatchPage } from './pages/employer/MatchPage'
import { EmployerSearchPage } from './pages/employer/EmployerSearchPage'
import { EmployerInvitationsPage } from './pages/employer/EmployerInvitationsPage'
import { EmployerVacanciesPage } from './pages/employer/EmployerVacanciesPage'
import { EmployerApplicationsPage } from './pages/employer/EmployerApplicationsPage'
import { EmployerRegularTasksPage } from './pages/employer/EmployerRegularTasksPage'
import { EmployerProfilePage } from './pages/employer/EmployerProfilePage'
import { CandidateProfilePage } from './pages/candidate/CandidateProfilePage'
import { CandidateTestingPage } from './pages/candidate/CandidateTestingPage'
import { CandidateInvitationsPage } from './pages/candidate/CandidateInvitationsPage'
import { CandidateVacanciesPage } from './pages/candidate/CandidateVacanciesPage'
import { CandidateRegularTasksPage } from './pages/candidate/CandidateRegularTasksPage'

function RootRedirect() {
  const { user, isReady } = useAuth()
  if (!isReady) {
    return (
      <Layout>
        <div className="min-h-screen flex items-center justify-center">
          <span className="font-label-md text-label-md text-on-surface-variant">Загрузка…</span>
        </div>
      </Layout>
    )
  }
  if (user === null) return <Navigate to="/login" replace />
  return <Navigate to={user.role === 'employer' ? '/employer' : '/candidate'} replace />
}

export function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<RootRedirect />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<Navigate to="/login?tab=register" replace />} />
          <Route path="/confirm-email/:token" element={<ConfirmEmailPage />} />
          <Route path="/auth/confirm/:token" element={<ConfirmEmailPage />} />
          <Route
            path="/employer"
            element={
              <RequireRole role="employer">
                <MatchPage />
              </RequireRole>
            }
          />
          <Route
            path="/employer/search"
            element={
              <RequireRole role="employer">
                <EmployerSearchPage />
              </RequireRole>
            }
          />
          <Route
            path="/employer/invitations"
            element={
              <RequireRole role="employer">
                <EmployerInvitationsPage />
              </RequireRole>
            }
          />
          <Route
            path="/employer/vacancies"
            element={
              <RequireRole role="employer">
                <EmployerVacanciesPage />
              </RequireRole>
            }
          />
          <Route
            path="/employer/applications"
            element={
              <RequireRole role="employer">
                <EmployerApplicationsPage />
              </RequireRole>
            }
          />
          <Route
            path="/employer/regular-tasks"
            element={
              <RequireRole role="employer">
                <EmployerRegularTasksPage />
              </RequireRole>
            }
          />
          <Route
            path="/employer/company"
            element={
              <RequireRole role="employer">
                <EmployerProfilePage />
              </RequireRole>
            }
          />
          <Route
            path="/candidate"
            element={
              <RequireRole role="candidate">
                <CandidateProfilePage />
              </RequireRole>
            }
          />
          <Route
            path="/candidate/testing"
            element={
              <RequireRole role="candidate">
                <CandidateTestingPage />
              </RequireRole>
            }
          />
          <Route
            path="/candidate/invitations"
            element={
              <RequireRole role="candidate">
                <CandidateInvitationsPage />
              </RequireRole>
            }
          />
          <Route
            path="/candidate/vacancies"
            element={
              <RequireRole role="candidate">
                <CandidateVacanciesPage />
              </RequireRole>
            }
          />
          <Route
            path="/candidate/regular-tasks"
            element={
              <RequireRole role="candidate">
                <CandidateRegularTasksPage />
              </RequireRole>
            }
          />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
