// ───────────────────────────────────────────────────────────────────
// App.tsx — TimeLapse Pro med RBAC auth guard
// ───────────────────────────────────────────────────────────────────
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import type { ReactElement, ReactNode } from 'react'
import { Shield } from 'lucide-react'
import { Navbar } from './components/Navbar'
import { Dashboard } from './pages/Dashboard'
import { DevicePage } from './pages/DevicePage'
import { SettingsPage } from './pages/SettingsPage'
import { BackupPage } from './pages/BackupPage'
import { SitePage } from './pages/SitePage'
import { CustomerPage } from './pages/CustomerPage'
import { CameraPage } from './pages/CameraPage'
import { GlobalConfigPage } from './pages/GlobalConfigPage'
import LabPage from './pages/LabPage'
import { SystemAdminPage } from './pages/SystemAdminPage'
import { LocalAccessOverviewPage } from './pages/LocalAccessOverviewPage'
import { TagSearchPage } from './pages/TagSearchPage'
import { NotificationsPage } from './pages/NotificationsPage'
import TimelapseVideoPage from './pages/TimelapseVideoPage'
import NewCustomerPage from './pages/NewCustomerPage'
import LoginPage from './pages/LoginPage'
import UsersPage from './pages/UsersPage'
import KeyManagementPage from './pages/KeyManagementPage'
import { SshTunnelPage } from './pages/SshTunnelPage'
import { UpdatesPage } from './pages/UpdatesPage'
import { ChangeTicketsPage } from './pages/ChangeTicketsPage'
import { CompliancePage } from './pages/CompliancePage'
import { RetentionPage } from './pages/RetentionPage'
import RedactionPage from './pages/RedactionPage'
import { AuthProvider, useAuth } from './context/AuthContext'
import { CMDBPage, CMDBDetailPage } from './pages/CMDBPage'
import { SIEMPage } from './pages/SIEMPage'
import { ImportPage } from './pages/ImportPage'
import AIPage from './pages/AIPage'
import OpenWebUIPage from './pages/OpenWebUIPage'
import PostProcessingPage from './pages/PostProcessingPage'
import DriftPage from './pages/DriftPage'
import { HelpPage } from './pages/HelpPage'
import { ErrorBoundary } from './components/ErrorBoundary'


function RequireAuth({ children }: { children: ReactElement }) {
  const { isAuthenticated, loading } = useAuth()
  const location = useLocation()
  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center text-sm text-gray-500">
        Indlæser TimeLapse Pro...
      </div>
    )
  }
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }
  return children
}

type AppRole = 'super_admin' | 'admin' | 'operator' | 'viewer'
const ROLE_LEVEL: Record<AppRole, number> = {
  viewer: 0,
  operator: 1,
  admin: 2,
  super_admin: 3,
}

function RequireRole({ minimum, children }: { minimum: AppRole; children: ReactNode }) {
  const { user } = useAuth()
  if (!user || ROLE_LEVEL[user.role] < ROLE_LEVEL[minimum]) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-16 text-center">
        <Shield className="mx-auto mb-3 h-8 w-8 text-slate-300" />
        <h1 className="text-lg font-semibold text-slate-800">Ingen adgang</h1>
        <p className="mt-1 text-sm text-slate-500">Din rolle har ikke adgang til denne funktion.</p>
      </div>
    )
  }
  return <>{children}</>
}

function AppRoutes() {
  return (
    <Routes>
      {/* Public */}
      <Route path="/login" element={<LoginPage />} />

      {/* Protected */}
      <Route path="/*" element={
        <RequireAuth>
          <div className="min-h-screen bg-gray-50">
            <Navbar />
            <main>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/devices/:id" element={<DevicePage />} />
                <Route path="/settings" element={<SettingsPage />} />
                <Route path="/backup" element={<RequireRole minimum="admin"><BackupPage /></RequireRole>} />
                <Route path="/sites/:siteId" element={<SitePage />} />
                <Route path="/customers/new" element={<RequireRole minimum="super_admin"><NewCustomerPage /></RequireRole>} />
                <Route path="/customers/:customerId" element={<CustomerPage />} />
                <Route path="/cameras/:deviceId" element={<RequireRole minimum="admin"><CameraPage /></RequireRole>} />
                <Route path="/global-config" element={<RequireRole minimum="admin"><GlobalConfigPage /></RequireRole>} />
                <Route path="/lab/:deviceId" element={<RequireRole minimum="admin"><LabPage /></RequireRole>} />
                <Route path="/devices/:deviceId/lab" element={<RequireRole minimum="admin"><LabPage /></RequireRole>} />
                <Route path="/system-admin" element={<RequireRole minimum="admin"><SystemAdminPage /></RequireRole>} />
                <Route path="/local-access" element={<RequireRole minimum="admin"><LocalAccessOverviewPage /></RequireRole>} />
            <Route path="/tags" element={<TagSearchPage />} />
            <Route path="/notifications" element={<NotificationsPage />} />
                <Route path="/devices/:id/timelapse" element={<RequireRole minimum="admin"><TimelapseVideoPage /></RequireRole>} />
                <Route path="/users" element={<RequireRole minimum="super_admin"><UsersPage /></RequireRole>} />
                <Route path="/key-management" element={<RequireRole minimum="admin"><KeyManagementPage /></RequireRole>} />
                <Route path="/ssh-tunnel" element={<RequireRole minimum="admin"><SshTunnelPage /></RequireRole>} />
                <Route path="/updates" element={<RequireRole minimum="admin"><UpdatesPage /></RequireRole>} />
                <Route path="/change-tickets" element={<RequireRole minimum="admin"><ChangeTicketsPage /></RequireRole>} />
                <Route path="/compliance" element={<CompliancePage />} />
                <Route path="/retention" element={<RequireRole minimum="admin"><RetentionPage /></RequireRole>} />
                <Route path="/redaction" element={<RequireRole minimum="admin"><RedactionPage /></RequireRole>} />
        <Route path="/cmdb" element={<CMDBPage />} />
        <Route path="/siem" element={<SIEMPage />} />
        <Route path="/import" element={<RequireRole minimum="admin"><ImportPage /></RequireRole>} />
        <Route path="/cmdb/:deviceId" element={<CMDBDetailPage />} />
	        <Route path="/ai" element={<RequireRole minimum="admin"><AIPage /></RequireRole>} />
	        <Route path="/openwebui" element={<RequireRole minimum="admin"><OpenWebUIPage /></RequireRole>} />
	        <Route path="/post-processing" element={<RequireRole minimum="admin"><PostProcessingPage /></RequireRole>} />
	        <Route path="/observability" element={<DriftPage />} />
	        <Route path="/help" element={<HelpPage />} />
	              </Routes>
            </main>
          </div>
        </RequireAuth>
      } />
    </Routes>
  )
}

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </BrowserRouter>
    </ErrorBoundary>
  )
}
