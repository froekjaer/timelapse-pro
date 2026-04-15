import { Link, useLocation } from 'react-router-dom'
import { Camera, Settings, Database, Globe } from 'lucide-react'

export function Navbar() {
  const { pathname } = useLocation()

const links = [
  { to: '/', label: 'Enheder', icon: Camera },
  { to: '/backup', label: 'Backup', icon: Database },
  { to: '/global-config', label: 'Global Config', icon: Globe },
  { to: '/settings', label: 'Indstillinger', icon: Settings },
]
  return (
    <nav className="bg-slate-900 text-white">
      <div className="max-w-7xl mx-auto px-4 flex items-center gap-8 h-14">
        <Link to="/" className="flex items-center gap-2 font-semibold text-white">
          <Camera className="w-5 h-5 text-sky-400" />
          <span>TimeLapse Pro</span>
        </Link>
        <div className="flex items-center gap-1 ml-4">
          {links.map(({ to, label, icon: Icon }) => {
            const active = to === '/' ? pathname === '/' : pathname.startsWith(to)
            return (
              <Link
                key={to}
                to={to}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-colors ${
                  active
                    ? 'bg-slate-700 text-white'
                    : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                }`}
              >
                <Icon className="w-4 h-4" />
                {label}
              </Link>
            )
          })}
        </div>
        <div className="ml-auto flex items-center gap-2">
          <span className="text-xs text-slate-400">v1.0</span>
        </div>
      </div>
    </nav>
  )
}
