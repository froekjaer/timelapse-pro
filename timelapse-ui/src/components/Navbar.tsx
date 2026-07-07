import { useState, useRef, useEffect } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import {
  Brain, Camera, Settings, Database, Globe, LogOut,
  Shield, Users, Key, Terminal, Package, Server,
  ChevronDown, ClipboardCheck, Upload, Bot, Tag,
  Wrench, Activity, EyeOff, Clock,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'

export function Navbar() {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const { user, logout, hasRole } = useAuth()
  const [adminOpen, setAdminOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setAdminOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const links = [
    { to: '/',             label: 'Enheder',       icon: Camera },
    { to: '/backup',       label: 'Backup',        icon: Database },
    { to: '/global-config',label: 'Global Config', icon: Globe },
    { to: '/tags',         label: 'Tag søgning',   icon: Tag },
    { to: '/settings',     label: 'Indstillinger', icon: Settings },
    { to: '/ai',           label: 'AI Styring',    icon: Brain },
    { to: '/openwebui',    label: 'Open WebUI',    icon: Bot },
    { to: '/compliance',   label: 'Compliance',    icon: ClipboardCheck },
  ]

  const adminLinks = [
    { to: '/system-admin',  label: 'System Admin',  icon: Shield },
    { to: '/users',         label: 'Brugere',       icon: Users },
    { to: '/key-management',label: 'Nøgler',        icon: Key },
    { to: '/ssh-tunnel',    label: 'SSH Tunnels',   icon: Terminal },
    { to: '/updates',       label: 'Opdateringer',  icon: Package },
    { to: '/change-tickets',label: 'Change tickets',icon: ClipboardCheck },
    { to: '/post-processing',label: 'Post-processing',icon: Wrench },
    { to: '/cmdb',          label: 'CMDB',          icon: Server },
    { to: '/import',        label: 'Import',        icon: Upload },
    { to: '/siem',          label: 'SIEM',          icon: Shield },
    { to: '/retention',     label: 'Retention',     icon: Clock },
    { to: '/redaction',     label: 'GDPR Redaction',icon: EyeOff },
    { to: '/observability', label: 'Drift',         icon: Activity },
  ]

  const isAdmin = hasRole('super_admin', 'admin')
  const adminActive = adminLinks.some(l => pathname.startsWith(l.to))

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <nav className="bg-slate-900 text-white">
      <div className="max-w-7xl mx-auto px-4 flex items-center gap-2 h-14">

        <Link to="/" className="flex items-center gap-2 font-semibold text-white flex-shrink-0 mr-2">
          <Camera className="w-5 h-5 text-sky-400" />
          <span>TimeLapse Pro</span>
        </Link>

        <div className="flex items-center gap-1">
          {links.map(({ to, label, icon: Icon }) => {
            const active = to === '/' ? pathname === '/' : pathname.startsWith(to)
            return (
              <Link key={to} to={to}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-colors ${
                  active ? 'bg-slate-700 text-white' : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                }`}>
                <Icon className="w-4 h-4" />
                {label}
              </Link>
            )
          })}
        </div>

        {isAdmin && (
          <div className="relative border-l border-slate-700 pl-2 ml-1" ref={dropdownRef}>
            <button
              onClick={() => setAdminOpen(o => !o)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-colors ${
                adminActive || adminOpen
                  ? 'bg-slate-700 text-white'
                  : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
              }`}
            >
              <Shield className="w-4 h-4" />
              Admin
              <ChevronDown className={`w-3.5 h-3.5 transition-transform ${adminOpen ? 'rotate-180' : ''}`} />
            </button>

            {adminOpen && (
              <div className="absolute top-full left-0 mt-1 w-48 bg-slate-800 border border-slate-700 rounded-lg shadow-xl z-50 py-1">
                {adminLinks.map(({ to, label, icon: Icon }) => {
                  const active = pathname.startsWith(to)
                  return (
                    <Link key={to} to={to}
                      onClick={() => setAdminOpen(false)}
                      className={`flex items-center gap-2.5 px-3 py-2 text-sm transition-colors ${
                        active ? 'bg-slate-700 text-white' : 'text-slate-300 hover:bg-slate-700 hover:text-white'
                      }`}
                    >
                      <Icon className="w-4 h-4 flex-shrink-0" />
                      {label}
                    </Link>
                  )
                })}
              </div>
            )}
          </div>
        )}

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
                <p className="text-xs text-slate-400 leading-tight capitalize">{user.role.replace('_', ' ')}</p>
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
