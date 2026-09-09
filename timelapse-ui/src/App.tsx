// ───────────────────────────────────────────────────────────────────
// App.tsx — TimeLapse Pro med RBAC auth guard
// ───────────────────────────────────────────────────────────────────
import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import type { ReactElement, ReactNode } from 'react'
import { Shield } from 'lucide-react'
import { Navbar } from './components/Navbar'
import { AuthProvider, useAuth } from './context/AuthContext'
import { ErrorBoundary } from './components/ErrorBoundary'

// 2026-09-09 (Claude, Peter: 15+ sek. sidevisning over VPN/mobilnet, se
// Safari Web Inspector-optagelse): ALLE sider blev tidligere statisk
// importeret, så hele appen (Lab/WebRTC-tuning, Backup, AI, Timelapse-
// rendering osv. — 33 sider i alt) endte i ÉN JS-bundle (2 MB rå / 540 kB
// gzippet). En besøgende der bare vil se enhedslisten måtte alligevel
// downloade kode til alle 33 sider først. På en god forbindelse er det
// usynligt (<1s); på en langsom/tabsramt forbindelse blev hele appen
// blokeret bag ÉT enkelt 15+ sekunders netværkskald, bekræftet direkte i
// Web Inspector (CPU idle hele tiden — appen ventede rent netværksmæssigt,
// ikke JS-udførsel). React.lazy() pr. rute betyder at kun den aktuelt
// besøgte sides kode skal hentes før første visning.
const Dashboard                 = lazy(() => import('./pages/Dashboard').then(m => ({ default: m.Dashboard })))
const DevicePage                = lazy(() => import('./pages/DevicePage').then(m => ({ default: m.DevicePage })))
const SettingsPage              = lazy(() => import('./pages/SettingsPage').then(m => ({ default: m.SettingsPage })))
const BackupPage                = lazy(() => import('./pages/BackupPage').then(m => ({ default: m.BackupPage })))
const SitePage                  = lazy(() => import('./pages/SitePage').then(m => ({ default: m.SitePage })))
const CustomerPage              = lazy(() => import('./pages/CustomerPage').then(m => ({ default: m.CustomerPage })))
const CameraPage                = lazy(() => import('./pages/CameraPage').then(m => ({ default: m.CameraPage })))
const GlobalConfigPage          = lazy(() => import('./pages/GlobalConfigPage').then(m => ({ default: m.GlobalConfigPage })))
const LabPage                   = lazy(() => import('./pages/LabPage'))
const SystemAdminPage           = lazy(() => import('./pages/SystemAdminPage').then(m => ({ default: m.SystemAdminPage })))
const LocalAccessOverviewPage   = lazy(() => import('./pages/LocalAccessOverviewPage').then(m => ({ default: m.LocalAccessOverviewPage })))
const TagSearchPage             = lazy(() => import('./pages/TagSearchPage').then(m => ({ default: m.TagSearchPage })))
const NotificationsPage         = lazy(() => import('./pages/NotificationsPage').then(m => ({ default: m.NotificationsPage })))
const TimelapseVideoPage        = lazy(() => import('./pages/TimelapseVideoPage'))
const NewCustomerPage           = lazy(() => import('./pages/NewCustomerPage'))
const LoginPage                 = lazy(() => import('./pages/LoginPage'))
const UsersPage                 = lazy(() => import('./pages/UsersPage'))
const KeyManagementPage         = lazy(() => import('./pages/KeyManagementPage'))
const SshTunnelPage             = lazy(() => import('./pages/SshTunnelPage').then(m => ({ default: m.SshTunnelPage })))
const UpdatesPage               = lazy(() => import('./pages/UpdatesPage').then(m => ({ default: m.UpdatesPage })))
const ChangeTicketsPage         = lazy(() => import('./pages/ChangeTicketsPage').then(m => ({ default: m.ChangeTicketsPage })))
const CompliancePage            = lazy(() => import('./pages/CompliancePage').then(m => ({ default: m.CompliancePage })))
const RetentionPage             = lazy(() => import('./pages/RetentionPage').then(m => ({ default: m.RetentionPage })))
const RedactionPage             = lazy(() => import('./pages/RedactionPage'))
const CMDBPage                  = lazy(() => import('./pages/CMDBPage').then(m => ({ default: m.CMDBPage })))
const CMDBDetailPage            = lazy(() => import('./pages/CMDBPage').then(m => ({ default: m.CMDBDetailPage })))
const SIEMPage                  = lazy(() => import('./pages/SIEMPage').then(m => ({ default: m.SIEMPage })))
const ImportPage                = lazy(() => import('./pages/ImportPage').then(m => ({ default: m.ImportPage })))
const AIPage                    = lazy(() => import('./pages/AIPage'))
const OpenWebUIPage             = lazy(() => import('./pages/OpenWebUIPage'))
const PostProcessingPage        = lazy(() => import('./pages/PostProcessingPage'))
const DriftPage                 = lazy(() => import('./pages/DriftPage'))
const EdgeCommunicationsPage    = lazy(() => import('./pages/EdgeCommunicationsPage').then(m => ({ default: m.EdgeCommunicationsPage })))
const HelpPage                  = lazy(() => import('./pages/HelpPage').then(m => ({ default: m.HelpPage })))

function PageLoading() {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center text-sm text-gray-500">
      Indlæser side...
    </div>
  )
}

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
    <Suspense fallback={<PageLoading />}>
      <Routes>
        {/* Public */}
        <Route path="/login" element={<LoginPage />} />

        {/* Protected */}
        <Route path="/*" element={
          <RequireAuth>
            <div className="min-h-screen bg-gray-50">
              <Navbar />
              <main>
                <Suspense fallback={<PageLoading />}>
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
            <Route path="/edge-communications" element={<RequireRole minimum="admin"><EdgeCommunicationsPage /></RequireRole>} />
            <Route path="/help" element={<HelpPage />} />
                  </Routes>
                </Suspense>
              </main>
            </div>
          </RequireAuth>
        } />
      </Routes>
    </Suspense>
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
