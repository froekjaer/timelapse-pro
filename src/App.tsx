import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Navbar } from './components/Navbar'
import { Dashboard } from './pages/Dashboard'
import { DevicePage } from './pages/DevicePage'
import { SettingsPage } from './pages/SettingsPage'
import LabPage from './pages/LabPage'

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
			<Route path="/devices/:id/lab" element={<LabPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
