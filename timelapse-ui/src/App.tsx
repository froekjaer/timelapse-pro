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
import TimelapseVideoPage from './pages/TimelapseVideoPage'
import NewCustomerPage from './pages/NewCustomerPage'
import LoginPage from './pages/LoginPage'
import UsersPage from './pages/UsersPage'
import KeyManagementPage from './pages/KeyManagementPage'
import { SshTunnelPage } from './pages/SshTunnelPage'
import { AuthProvider, useAuth } from './context/AuthContext'

function RequireAuth({ children }: { children: ReactElement }) {
  const { isAuthenticated } = useAuth()
  const location = useLocation()
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
                <Route path="/devices/:id/timelapse" element={<TimelapseVideoPage />} />
                <Route path="/users" element={<UsersPage />} />
                <Route path="/key-management" element={<KeyManagementPage />} />
                <Route path="/ssh-tunnel" element={<SshTunnelPage />} />
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
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  )
}
