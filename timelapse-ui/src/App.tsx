// ───────────────────────────────────────────────────────────────────
// App.tsx — TimeLapse Pro med RBAC auth guard
// ───────────────────────────────────────────────────────────────────
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import type { ReactElement } from 'react'
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
                <Route path="/backup" element={<BackupPage />} />
                <Route path="/sites/:siteId" element={<SitePage />} />
                <Route path="/customers/new" element={<NewCustomerPage />} />
                <Route path="/customers/:customerId" element={<CustomerPage />} />
                <Route path="/cameras/:deviceId" element={<CameraPage />} />
                <Route path="/global-config" element={<GlobalConfigPage />} />
                <Route path="/lab/:deviceId" element={<LabPage />} />
                <Route path="/devices/:deviceId/lab" element={<LabPage />} />
                <Route path="/system-admin" element={<SystemAdminPage />} />
            <Route path="/tags" element={<TagSearchPage />} />
            <Route path="/notifications" element={<NotificationsPage />} />
                <Route path="/devices/:id/timelapse" element={<TimelapseVideoPage />} />
                <Route path="/users" element={<UsersPage />} />
                <Route path="/key-management" element={<KeyManagementPage />} />
                <Route path="/ssh-tunnel" element={<SshTunnelPage />} />
                <Route path="/updates" element={<UpdatesPage />} />
                <Route path="/change-tickets" element={<ChangeTicketsPage />} />
                <Route path="/compliance" element={<CompliancePage />} />
                <Route path="/retention" element={<RetentionPage />} />
                <Route path="/redaction" element={<RedactionPage />} />
        <Route path="/cmdb" element={<CMDBPage />} />
        <Route path="/siem" element={<SIEMPage />} />
        <Route path="/import" element={<ImportPage />} />
        <Route path="/cmdb/:deviceId" element={<CMDBDetailPage />} />
	        <Route path="/ai" element={<AIPage />} />
	        <Route path="/openwebui" element={<OpenWebUIPage />} />
	        <Route path="/post-processing" element={<PostProcessingPage />} />
	        <Route path="/observability" element={<DriftPage />} />
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
