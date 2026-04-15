import { BrowserRouter, Routes, Route } from 'react-router-dom'
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

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-50">
        <Navbar />
        <main>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/devices/:id" element={<DevicePage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/backup" element={<BackupPage />} />
            <Route path="/sites/:siteId" element={<SitePage />} />
            <Route path="/customers/:customerId" element={<CustomerPage />} />
            <Route path="/cameras/:deviceId" element={<CameraPage />} />
            <Route path="/global-config" element={<GlobalConfigPage />} />
            <Route path="/lab/:deviceId" element={<LabPage />} />
            <Route path="/system-admin" element={<SystemAdminPage />} />
            <Route path="/devices/:id/timelapse" element={<TimelapseVideoPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
