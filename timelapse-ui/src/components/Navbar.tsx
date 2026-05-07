import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Camera, Settings, Database, Globe, Users, LogOut, Shield, Key } from 'lucide-react'
import { useAuth } from '../context/AuthContext'

export function Navbar() {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const { user, logout, hasRole } = useAuth()

  const links = [
    { to: '/',            label: 'Enheder',      icon: Camera },
    { to: '/backup',      label: 'Backup',       icon: Database },
    { to: '/global-config',label: 'Global Config',icon: Globe },
    { to: '/settings',    label: 'Indstillinger', icon: Settings },
  ]

  const adminLinks = [
    hasRole('super_admin', 'admin') && { to: '/system-admin',    label: 'System Admin',   icon: Shield },
    hasRole('super_admin', 'admin') && { to: '/users',            label: 'Brugere',        icon: Users },
    hasRole('super_admin', 'admin') && { to: '/key-management',   label: 'Nøgler',         icon: Key },
  ].filter(Boolean) as { to: string; label: string; icon: any }[]

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <nav className="bg-slate-900 text-white">
      <div className="max-w-7xl mx-auto px-4 flex items-center gap-4 h-14 flex-wrap">

        <Link to="/" className="flex items-center gap-2 font-semibold text-white flex-shrink-0">
          <Camera className="w-5 h-5 text-sky-400" />
          <span>TimeLapse Pro</span>
        </Link>

        {/* Primære links */}
        <div className="flex items-center gap-1">
          {links.map(({ to, label, icon: Icon }) => {
            const active = to === '/' ? pathname === '/' : pathname.startsWith(to)
            return (
              <Link key={to} to={to}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-colors ${
                  active ? 'bg-slate-700 text-white' : 'text-slate-300 hover:bg-slate-800 hover:text-white'}`}>
                <Icon className="w-4 h-4" />
                {label}
              </Link>
            )
          })}
        </div>

        {/* Admin links */}
        {adminLinks.length > 0 && (
          <div className="flex items-center gap-1 border-l border-slate-700 pl-3">
            {adminLinks.map(({ to, label, icon: Icon }) => {
              const active = pathname.startsWith(to)
              return (
                <Link key={to} to={to}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-colors ${
                    active ? 'bg-slate-700 text-white' : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'}`}>
                  <Icon className="w-4 h-4" />
                  {label}
                </Link>
              )
            })}
          </div>
        )}

        {/* Bruger + logout */}
        <div className="ml-auto flex items-center gap-3">
          {user && (
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-full bg-sky-500 flex items-center justify-center flex-shrink-0">
                <span className="text-xs font-bold text-white">
                  {user.username.charAt(0).toUpperCase()}
                </span>
              </div>
              <div className="hidden sm:block">
                <p className="text-xs font-medium text-white leading-tight">{user.username}</p>
                <p className="text-xs text-slate-400 leading-tight capitalize">{user.role.replace('_',' ')}</p>
              </div>
            </div>
          )}
          <button onClick={handleLogout}
            className="flex items-center gap-1.5 px-3 py-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded-md text-sm transition-colors">
            <LogOut className="w-4 h-4" />
            <span className="hidden sm:inline">Log ud</span>
          </button>
        </div>
      </div>
    </nav>
  )
}
