import { useState, useRef, useEffect } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import {
  Brain, Camera, Settings, Database, Globe, LogOut,
  Shield, Users, Key, Terminal, Package, Server,
  ChevronDown, ClipboardCheck, Upload, Bot, Tag,
  Wrench, Activity, EyeOff, Clock, Menu, X, QrCode,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'

export function Navbar() {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const { user, logout, hasRole } = useAuth()
  const [adminOpen, setAdminOpen] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
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
    { to: '/',             label: 'Enheder',       icon: Camera, tooltip: 'Oversigt over alle kameraenheder. Se status, captures, og enhedsspecifikke indstillinger. Administrer enheder og fejlfind.', adminOnly: false },
    { to: '/backup',       label: 'Backup',        icon: Database, tooltip: 'Backup af captures og database. Schedule og overvåg backup jobs. Restore fra backup ved behov.', adminOnly: true },
    { to: '/global-config',label: 'Global Config', icon: Globe, tooltip: 'Hierarkisk konfiguration: Global → Kunde → Site → Kamera. Arv og overrides for alle parametre.', adminOnly: true },
    { to: '/tags',         label: 'Tag søgning',   icon: Tag, tooltip: 'Søg captures på tværs af tags. Find billeder baseret på brugerdefinerede labels og metadata.', adminOnly: false },
    { to: '/settings',     label: 'Indstillinger', icon: Settings, tooltip: 'Personlige indstillinger og præferencer. Tilpas din brugeroplevelse og notifikationer.', adminOnly: false },
    { to: '/ai',           label: 'AI Styring',    icon: Brain, tooltip: 'AI-drevet billedanalyse og kvalitetskontrol. Konfigurer NPU, adaptive exposure, og drift detection.', adminOnly: true },
    { to: '/openwebui',    label: 'Open WebUI',    icon: Bot, tooltip: 'AI assistent interface til natural language queries. Få svar om captures, kvalitet, og system status.', adminOnly: true },
    { to: '/compliance',   label: 'Compliance',    icon: ClipboardCheck, tooltip: 'SABSA compliance cockpit. Audit logs, sikkerhedsrapporter, og compliance status for hele systemet.', adminOnly: false },
  ].filter(link => !link.adminOnly || hasRole('super_admin', 'admin'))

  const adminLinks = [
    { to: '/system-admin',  label: 'System Admin',  icon: Shield, tooltip: 'Systemniveau administration. Service status, konfiguration, og avancerede systemindstillinger.' },
    { to: '/local-access',  label: 'Lokal adgang',  icon: QrCode, tooltip: 'Oversigt over BT PAN TOTP-status for alle kameraer du har adgang til. QR-kode og live kode åbnes fra det enkelte kamera.' },
    { to: '/users',         label: 'Brugere',       icon: Users, tooltip: 'Bruger- og rollestyring. Opret, rediger og deaktiver brugere. Konfigurer rettigheder og MFA.' },
    { to: '/key-management',label: 'Nøgler',        icon: Key, tooltip: 'API nøgle administration. Generer, roter og tilbagekald API tokens. Se nøgle forbrug og aktivitet.' },
    { to: '/ssh-tunnel',    label: 'SSH Tunnels',   icon: Terminal, tooltip: 'SSH tunnel management til edge-enheder. Opret sikre forbindelser til onsite udstyr.' },
    { to: '/updates',       label: 'Opdateringer',  icon: Package, tooltip: 'Systemopdateringer og patches. Release notes, versionsstyring, og deployment af opdateringer.' },
    { to: '/change-tickets',label: 'Change tickets',icon: ClipboardCheck, tooltip: 'Change management og tickets. Opret, tildel og spore ændringer gennem hele systemet.' },
    { to: '/post-processing',label: 'Post-processing',icon: Wrench, tooltip: 'Billedbehandling efter capture. Bildemanipulation, formatkonvertering, og eksport pipelines.' },
    { to: '/cmdb',          label: 'CMDB',          icon: Server, tooltip: 'Configuration Management Database. Asset tracking, relationer, og konfigurationshistorik.' },
    { to: '/import',        label: 'Import',        icon: Upload, tooltip: 'Import af data fra eksterne kilder. Bulk upload, migrering, og data integration.' },
    { to: '/siem',          label: 'SIEM',          icon: Shield, tooltip: 'SIEM integration og sikkerhedshændelser. Audit logs, alerts, og sikkerhedsmetrics.' },
    { to: '/retention',     label: 'Retention',     icon: Clock, tooltip: 'Data retention politikker. Konfigurer hvor længe captures og logs gemmes automatisk.' },
    { to: '/redaction',     label: 'GDPR Sløring',icon: EyeOff, tooltip: 'GDPR compliance med automatisk sløring. Detekter og slør personsensitive data i billeder.' },
    { to: '/observability', label: 'Drift',         icon: Activity, tooltip: 'Driftsovervågning og diagnostik. System health, performance metrics, og alerts.' },
  ]

  const isAdmin = hasRole('super_admin', 'admin')
  const adminActive = adminLinks.some(l => pathname.startsWith(l.to))

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <nav className="relative z-50 bg-slate-900 text-white">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-2 px-4">

        <Link to="/" className="flex items-center gap-2 font-semibold text-white flex-shrink-0 mr-2">
          <Camera className="w-5 h-5 text-sky-400" />
          <span>TimeLapse Pro</span>
        </Link>

        <div className="hidden items-center gap-1 xl:flex">
          {links.map(({ to, label, icon: Icon, tooltip }) => {
            const active = to === '/' ? pathname === '/' : pathname.startsWith(to)
            return (
              <Link key={to} to={to}
                title={tooltip}
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
          <div className="relative ml-1 hidden border-l border-slate-700 pl-2 xl:block" ref={dropdownRef}>
            <button
              onClick={() => setAdminOpen(o => !o)}
              title="Åbn eller luk administrationsmenuen"
              aria-label="Åbn eller luk administrationsmenuen"
              aria-expanded={adminOpen}
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
                {adminLinks.map(({ to, label, icon: Icon, tooltip }) => {
                  const active = pathname.startsWith(to)
                  return (
                    <Link key={to} to={to}
                      onClick={() => setAdminOpen(false)}
                      title={tooltip}
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

        <div className="ml-auto hidden items-center gap-3 xl:flex">
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
            title="Log ud af TimeLapse Pro"
            className="flex items-center gap-1.5 px-3 py-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded-md text-sm transition-colors">
            <LogOut className="w-4 h-4" />
            <span className="hidden sm:inline">Log ud</span>
          </button>
        </div>

        <button
          type="button"
          aria-label={mobileOpen ? 'Luk navigation' : 'Åbn navigation'}
          aria-expanded={mobileOpen}
          onClick={() => setMobileOpen(open => !open)}
          className="ml-auto flex h-11 w-11 items-center justify-center rounded-md text-slate-200 hover:bg-slate-800 xl:hidden"
        >
          {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>

      </div>

      {mobileOpen && (
        <div className="absolute left-0 right-0 top-14 max-h-[calc(100vh-3.5rem)] overflow-y-auto border-t border-slate-700 bg-slate-900 px-3 py-3 shadow-xl xl:hidden">
          <div className="grid grid-cols-1 gap-1 sm:grid-cols-2">
            {links.map(({ to, label, icon: Icon, tooltip }) => {
              const active = to === '/' ? pathname === '/' : pathname.startsWith(to)
              return (
                <Link key={to} to={to} onClick={() => setMobileOpen(false)} title={tooltip} className={`flex min-h-11 items-center gap-3 rounded-md px-3 text-sm ${active ? 'bg-slate-700 text-white' : 'text-slate-200 hover:bg-slate-800'}`}>
                  <Icon className="h-5 w-5 flex-shrink-0" />
                  {label}
                </Link>
              )
            })}
            {isAdmin && <div className="col-span-full my-2 border-t border-slate-700" />}
            {isAdmin && adminLinks.map(({ to, label, icon: Icon, tooltip }) => {
              const active = pathname.startsWith(to)
              return (
                <Link key={to} to={to} onClick={() => setMobileOpen(false)} title={tooltip} className={`flex min-h-11 items-center gap-3 rounded-md px-3 text-sm ${active ? 'bg-slate-700 text-white' : 'text-slate-200 hover:bg-slate-800'}`}>
                  <Icon className="h-5 w-5 flex-shrink-0" />
                  {label}
                </Link>
              )
            })}
          </div>
          <div className="mt-3 flex items-center justify-between border-t border-slate-700 pt-3">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">{user?.username}</p>
              <p className="text-xs capitalize text-slate-400">{user?.role.replace('_', ' ')}</p>
            </div>
            <button onClick={handleLogout} title="Log ud af TimeLapse Pro" className="flex min-h-11 items-center gap-2 rounded-md px-3 text-sm text-slate-200 hover:bg-slate-800">
              <LogOut className="h-5 w-5" />
              Log ud
            </button>
          </div>
        </div>
      )}
    </nav>
  )
}
