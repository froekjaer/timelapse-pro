/**
 * Centralt rute→kapitel-kort for kontekstuel hjælp: ét sted at vedligeholde
 * i stedet for redigering af hver enkelt side. Anker-id'erne svarer til
 * overskrifterne i Dokumentation/MENUGUIDE_BRUGER_v1.md og
 * Dokumentation/MENUGUIDE_ADMIN_v1.md (slug-reglen lever i
 * src/help/headings.ts). Rammer et link ikke længere en overskrift (fx efter
 * omdøbning), åbnes dokumentet bare i toppen — links degraderer altså pænt,
 * de kan ikke fejle hårdt.
 */

export interface HelpTarget {
  doc: 'menuguide-bruger' | 'menuguide-admin'
  section?: string
}

// Mere specifikke mønstre står først — første match vinder.
export const HELP_ROUTE_MAP: Array<[pattern: string, target: HelpTarget]> = [
  ['/devices/:id/timelapse', { doc: 'menuguide-bruger', section: 'relaterede-sider-uden-eget-menupunkt' }],
  ['/devices/:deviceId/lab', { doc: 'menuguide-admin', section: 'kamera-laboratoriet-lab-deviceid' }],
  ['/lab/:deviceId', { doc: 'menuguide-admin', section: 'kamera-laboratoriet-lab-deviceid' }],
  ['/devices/:id', { doc: 'menuguide-bruger', section: 'enhedssiden-devices-id' }],
  ['/settings', { doc: 'menuguide-bruger', section: 'indstillinger-settings' }],
  ['/backup', { doc: 'menuguide-admin', section: 'backup-backup-drift-resilience' }],
  ['/sites/:siteId', { doc: 'menuguide-bruger', section: 'sitesiden-sites-siteid' }],
  ['/customers/new', { doc: 'menuguide-admin', section: 'ny-kunde-customers-new-kun-super-admin' }],
  ['/customers/:customerId', { doc: 'menuguide-bruger', section: 'kundesiden-customers-customerid' }],
  ['/cameras/:deviceId', { doc: 'menuguide-admin', section: 'kamera-siden-cameras-deviceid' }],
  ['/global-config', { doc: 'menuguide-admin', section: 'global-config-global-config' }],
  ['/system-admin', { doc: 'menuguide-admin', section: 'system-admin-system-admin' }],
  ['/local-access', { doc: 'menuguide-admin', section: 'lokal-adgang-local-access' }],
  ['/tags', { doc: 'menuguide-bruger', section: 'tag-soegning-tags' }],
  ['/notifications', { doc: 'menuguide-bruger', section: 'alarm-notifikationer-notifications' }],
  ['/users', { doc: 'menuguide-admin', section: 'brugere-users-kun-super-admin' }],
  ['/key-management', { doc: 'menuguide-admin', section: 'noegler-key-management' }],
  ['/ssh-tunnel', { doc: 'menuguide-admin', section: 'ssh-tunnels-ssh-tunnel' }],
  ['/updates', { doc: 'menuguide-admin', section: 'opdateringer-updates' }],
  ['/change-tickets', { doc: 'menuguide-admin', section: 'change-tickets-change-tickets' }],
  ['/compliance', { doc: 'menuguide-bruger', section: 'compliance-compliance' }],
  ['/retention', { doc: 'menuguide-admin', section: 'retention-retention' }],
  ['/redaction', { doc: 'menuguide-admin', section: 'gdpr-sloering-redaction' }],
  ['/cmdb/:deviceId', { doc: 'menuguide-admin', section: 'cmdb-cmdb' }],
  ['/cmdb', { doc: 'menuguide-admin', section: 'cmdb-cmdb' }],
  ['/siem', { doc: 'menuguide-admin', section: 'siem-siem' }],
  ['/import', { doc: 'menuguide-admin', section: 'import-import' }],
  ['/ai', { doc: 'menuguide-admin', section: 'ai-styring-ai' }],
  ['/openwebui', { doc: 'menuguide-admin', section: 'open-webui-openwebui' }],
  ['/post-processing', { doc: 'menuguide-admin', section: 'post-processing-post-processing' }],
  ['/observability', { doc: 'menuguide-admin', section: 'drift-observability' }],
  ['/', { doc: 'menuguide-bruger', section: 'enheder-dashboard' }],
]

function matchPath(pattern: string, path: string): boolean {
  const p = pattern.split('/').filter(Boolean)
  const a = path.split('/').filter(Boolean)
  if (p.length !== a.length) return false
  return p.every((seg, i) => seg.startsWith(':') || seg === a[i])
}

/**
 * Find det hjælpekapitel der dokumenterer en given side.
 * Returnerer null på selve hjælpesiden og på sider uden kortlægning.
 */
export function resolveHelpTarget(pathname: string): HelpTarget | null {
  if (pathname.startsWith('/help')) return null
  const match = HELP_ROUTE_MAP.find(([pattern]) => matchPath(pattern, pathname))
  return match ? match[1] : null
}

/** Byg URL'en til /help for et givent target. */
export function helpUrl(target: HelpTarget): string {
  return `/help?d=${target.doc}${target.section ? `&h=${target.section}` : ''}`
}
