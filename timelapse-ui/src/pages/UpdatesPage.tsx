// ═══════════════════════════════════════════════════════════════
// UpdatesPage.tsx
// Version: 1.0.0  |  08. maj 2026
// ═══════════════════════════════════════════════════════════════
import { type ChangeEvent, useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowLeft, RefreshCw, CheckCircle, XCircle, Clock,
  Package, AlertTriangle, Shield, ChevronDown, ChevronRight, Server, BarChart3, FileCheck, Fingerprint
} from 'lucide-react'
import { getApiUrl } from '../api/client'

function api(path: string, opts?: RequestInit) {
  return fetch(`${getApiUrl()}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(opts?.headers ?? {}) },
    ...opts
  }).then(async r => {
    if (r.status === 401) {
      window.location.href = '/login'
      throw new Error('401')
    }
    if (!r.ok) {
      let detail = `${r.status}`
      try {
        const payload = await r.json()
        detail = typeof payload.detail === 'string'
          ? payload.detail
          : payload.detail?.message || JSON.stringify(payload.detail || payload)
      } catch { /* ignore */ }
      throw new Error(detail)
    }
    return r.json()
  })
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message
  if (typeof error === 'string') return error
  try {
    return JSON.stringify(error)
  } catch {
    return 'Ukendt fejl'
  }
}

interface Update {
  id:                number
  update_type:       string
  version:           string
  description:       string | null
  severity:          string
  scope:             string
  scope_id:          string | null
  status:            string
  environment:       string | null
  deployed_count:    number
  failed_count:      number
  created_at:        string | null
  approved_at:       string | null
  approved_by:       string | null
  deployed_at:       string | null
  production_promotion_id?: number | null
  production_promotion_status?: string | null
  promotion_source_environment?: string | null
  prod_ready?: boolean
}

interface HeadendDeployStatus {
  update_id: number
  running: boolean
  status: string
  started_at: string | null
  finished_at: string | null
  message: string | null
  phase?: string | null
  backup_file?: string | null
  rollback_performed?: boolean
  rollback_message?: string | null
  stdout_tail: string
  stderr_tail: string
}

interface UpdateJobStatus {
  job_id: string
  kind: string
  title: string
  running: boolean
  status: string
  phase: string
  progress: number
  started_at: string | null
  finished_at: string | null
  message: string | null
  result?: unknown
  error?: string | null
}

interface UpdateFlowTarget {
  device_id: string
  hostname: string | null
  status: string
  waiting_for: string | null
  last_seen: string | null
  last_seen_age_s: number | null
  last_report_at: string | null
  started_at: string | null
  completed_at: string | null
  attempt_count: number
  last_error: string | null
  artifact_id: string | null
  target_version: string | null
}

interface UpdateFlowStatus {
  update_id: number
  status: string
  stage: {
    key: string
    label: string
  }
  artifact: UpdateArtifact | null
  ticket_id: string | null
  targets: UpdateFlowTarget[]
  next_edge_poll: string
  error?: string
}

interface RiskInfo {
  score: number
  level: 'low' | 'medium' | 'high' | 'critical' | string
  factors: string[]
}

interface UpdateCategory {
  key: string
  label: string
  types: string[]
}

interface Customer {
  id: string
  name: string
}

interface Site {
  id: string
  name: string
  customer_id: string
}

interface DeviceUpdateCategory {
  state: string
  installed: string | null
  available: string | null
  current_version?: string | null
  latest_available_version?: string | null
  version_gap_label?: string | null
  package_count?: number | null
  component?: string | null
  missing: boolean
  pending_update_id: number | null
  update_type: string | null
  description: string | null
  severity: string | null
  status: string | null
  created_at: string | null
  risk: RiskInfo
}

interface DeviceUpdateState {
  device_id: string
  cmdb_ref: string
  environment: string | null
  hardware_model: string | null
  hostname: string | null
  os_name: string | null
  kernel_version: string | null
  app_version: string | null
  customer_name: string | null
  site_name: string | null
  status: string | null
  last_seen: string | null
  inventory_reported_at: string | null
  risk_score: number
  missing_count: number
  categories: Record<string, DeviceUpdateCategory>
}

interface UpdateMatrix {
  categories: UpdateCategory[]
  devices: DeviceUpdateState[]
}

interface UpdateArtifact {
  artifact_id: string
  artifact_type: string
  version: string | null
  source_commit: string | null
  source_ref: string | null
  filename: string | null
  size_bytes: number | null
  sha256: string
  signed_by: string | null
  signed_at: string | null
  created_at: string | null
  manifest?: {
    source?: {
      dirty_worktree?: boolean
    }
    outputs?: unknown[]
    controls?: string[]
    distribution_model?: string
  }
}

interface ApproveOptions {
  environment:      'lab' | 'test' | 'production'
  scope:            'global' | 'device' | 'customer' | 'site'
  scope_id:         string
}

type Filter = 'pending' | 'approved' | 'blocked' | 'deployed' | 'rejected' | 'superseded' | 'rolled_back' | 'all'

const ACTIVE_FLOW_KEYS = new Set([
  'waiting_for_edge_poll',
  'queued',
  'backing_up',
  'downloading',
  'verifying',
  'installing',
])

function isActiveFlow(flowStatus: UpdateFlowStatus | undefined) {
  if (!flowStatus) return false
  if (ACTIVE_FLOW_KEYS.has(flowStatus.stage?.key || '')) return true
  return flowStatus.targets.some(target =>
    ['pending', 'queued', 'backing_up', 'downloading', 'verifying', 'installing'].includes(target.status)
  )
}

function fmt(iso: string | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('da-DK', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit'
  })
}

function severityBadge(s: string) {
  const map: Record<string, string> = {
    critical: 'bg-red-50 text-red-700 border-red-200',
    high:     'bg-orange-50 text-orange-700 border-orange-200',
    medium:   'bg-amber-50 text-amber-700 border-amber-200',
    low:      'bg-gray-50 text-gray-500 border-gray-200',
  }
  return map[s] ?? 'bg-gray-50 text-gray-500 border-gray-200'
}

function statusBadge(s: string) {
  const map: Record<string, string> = {
    pending:     'bg-amber-50 text-amber-700 border-amber-200',
    approved:    'bg-sky-50 text-sky-700 border-sky-200',
    queued:      'bg-sky-50 text-sky-700 border-sky-200',
    downloading: 'bg-sky-50 text-sky-700 border-sky-200',
    verifying:   'bg-sky-50 text-sky-700 border-sky-200',
    backing_up:  'bg-sky-50 text-sky-700 border-sky-200',
    installing:  'bg-sky-50 text-sky-700 border-sky-200',
    deployed:    'bg-green-50 text-green-700 border-green-200',
    blocked:     'bg-amber-50 text-amber-700 border-amber-200',
    failed:      'bg-red-50 text-red-500 border-red-200',
    rejected:    'bg-red-50 text-red-500 border-red-200',
    superseded:  'bg-gray-100 text-gray-500 border-gray-200',
    rolled_back: 'bg-purple-50 text-purple-700 border-purple-200',
  }
  return map[s] ?? 'bg-gray-50 text-gray-500 border-gray-200'
}

function riskBadge(risk: RiskInfo | null | undefined) {
  const level = risk?.level ?? 'low'
  const map: Record<string, string> = {
    critical: 'bg-red-600 text-white border-red-600',
    high:     'bg-red-50 text-red-700 border-red-200',
    medium:   'bg-amber-50 text-amber-700 border-amber-200',
    low:      'bg-gray-50 text-gray-500 border-gray-200',
  }
  return map[level] ?? map.low
}

function shortHash(value: string | null | undefined) {
  if (!value) return '-'
  return value.length > 18 ? `${value.slice(0, 12)}...${value.slice(-6)}` : value
}

function isProdReadyUpdate(u: Update) {
  return Boolean(u.prod_ready) || (
    u.environment === 'production' &&
    u.status === 'pending' &&
    Boolean(u.promotion_source_environment)
  )
}

const STATUS_LABELS: Record<string, string> = {
  pending:     'Afventer',
  prod_ready:  'Prod-klar',
  approved:    'Godkendt',
  blocked:     'Blokeret',
  deployed:    'Deployet',
  rejected:    'Afvist',
  superseded:  'Erstattet',
  rolled_back: 'Rullet tilbage',
}

const STATE_LABELS: Record<string, string> = {
  needs_approval: 'Mangler godkendelse',
  approved: 'Godkendt',
  blocked: 'Blokeret',
  deployed: 'Installeret',
  rolled_back: 'Rollback',
  rollback_requested: 'Rollback anmodet',
  no_update_reported: 'Ingen rapporteret',
  no_inventory: 'Mangler inventory',
}

const TARGET_STATUS_LABELS: Record<string, string> = {
  pending: 'Afventer',
  queued: 'Klar til Edge pull',
  downloading: 'Henter artifact',
  verifying: 'Verificerer',
  backing_up: 'Tager backup',
  installing: 'Installerer',
  deployed: 'Installeret',
  failed: 'Blokeret/fejlet',
  rejected: 'Afvist',
  rolled_back: 'Rollback',
  target_not_in_cmdb: 'Mangler CMDB',
}

const WAITING_LABELS: Record<string, string> = {
  edge_policy_pull: 'Afventer Edge policy-pull/heartbeat',
  downloading: 'Edge henter filer fra Headend',
  verifying: 'Edge verifierer signatur og hashes',
  backing_up: 'Edge tager pre-update backup',
  installing: 'Edge installerer offline',
  lab_os_bundle: 'Afventer lab-bygget offline OS bundle',
  artifact_or_lab_evidence: 'Afventer artifact/lab-evidens',
  cmdb_device_record: 'Afventer CMDB-enhed',
}

const TYPE_LABELS: Record<string, string> = {
  app_security: 'App sikkerhed',
  os_security:  'OS sikkerhed',
  app_updates:  'App opdatering',
  os_updates:   'OS opdatering',
  application_updates: 'Platform/app opdatering',
  application_update:  'Platform/app opdatering',
  third_party_updates: 'Platform/app opdatering',
}

function canDeployOnHeadend(u: Update) {
  const formula = headendFormula(u)
  return (
    u.status === 'approved' &&
    u.update_type === 'application_updates' &&
    u.scope === 'device' &&
    u.scope_id === 'TL-MACMINI-HEADEND-TEST-1' &&
    ['certbot', 'ffmpeg', 'nginx', 'node', 'ollama', 'postgresql@17'].includes(formula)
  )
}

function isHeadendScoped(u: Update) {
  return u.scope === 'device' && u.scope_id === 'TL-MACMINI-HEADEND-TEST-1'
}

function headendFormula(u: Update) {
  return (u.version || '').trim().split(/\s+/, 1)[0] || ''
}

type WorkflowStepState = 'done' | 'current' | 'waiting' | 'blocked' | 'failed'

interface WorkflowStep {
  title: string
  detail: string
  state: WorkflowStepState
}

function stepStyle(state: WorkflowStepState) {
  const map: Record<WorkflowStepState, string> = {
    done: 'border-emerald-200 bg-emerald-50 text-emerald-700',
    current: 'border-sky-200 bg-sky-50 text-sky-700',
    waiting: 'border-gray-200 bg-white text-gray-500',
    blocked: 'border-amber-200 bg-amber-50 text-amber-700',
    failed: 'border-red-200 bg-red-50 text-red-700',
  }
  return map[state]
}

function stepDotStyle(state: WorkflowStepState) {
  const map: Record<WorkflowStepState, string> = {
    done: 'bg-emerald-500',
    current: 'bg-sky-500 animate-pulse',
    waiting: 'bg-gray-300',
    blocked: 'bg-amber-500',
    failed: 'bg-red-500',
  }
  return map[state]
}

function workflowForUpdate(u: Update, deployStatus?: HeadendDeployStatus, flowStatus?: UpdateFlowStatus): { title: string; nextAction: string; steps: WorkflowStep[] } {
  const headendScoped = isHeadendScoped(u)
  const headendDeployable = canDeployOnHeadend(u)
  const deployFailed = deployStatus?.status === 'failed'
  const deployDone = u.status === 'deployed' || deployStatus?.status === 'deployed'
  const deployRunning = deployStatus?.running === true
  const phase = deployStatus?.phase || ''
  const edgeTargetStatus = flowStatus?.targets[0]?.status || ''

  if (u.status === 'pending' && (u.update_type === 'os_security' || u.update_type === 'os_updates') && !flowStatus?.artifact) {
    return {
      title: 'Edge OS offline update-flow',
      nextAction: 'Byg og bind et Headend-signeret offline OS artifact. Godkendelse er låst, indtil artifactet er valideret.',
      steps: [
        { title: 'Rapporteret', detail: 'Edge/CMDB har rapporteret den præcise pakkeliste.', state: 'done' },
        { title: 'Byg bundle', detail: 'Headend bygger pakken i isoleret Mac-container uden Edge-internet.', state: 'current' },
        { title: 'Signer og bind', detail: 'Manifest, sha256 og signatur bindes til change ticket.', state: 'waiting' },
        { title: 'Godkend', detail: 'Administrator kan godkende, når artifact trust er dokumenteret.', state: 'waiting' },
        { title: 'Edge pull', detail: 'Edge tager backup, validerer og installerer offline.', state: 'waiting' },
      ],
    }
  }

  if (u.status === 'pending') {
    const prodReady = isProdReadyUpdate(u)
    return {
      title: prodReady ? 'Production readiness-flow' : 'Approval-flow',
      nextAction: prodReady
        ? `Test-evidens fra ${u.promotion_source_environment || 'test'} er klar. Production kræver separat godkendelse før deployment.`
        : 'Godkend eller afvis opdateringen. Godkendelse flytter den videre til installationsflowet.',
      steps: [
        { title: prodReady ? 'Test-evidens' : 'Registreret', detail: prodReady ? `Pakken er deployet og testet på ${u.promotion_source_environment || 'test'}-miljø.` : 'Headend har oprettet update-kandidat fra CMDB/inventory.', state: 'done' },
        { title: prodReady ? 'Prod-klar' : 'Godkendelse', detail: prodReady ? 'Afventer separat production-godkendelse.' : 'Afventer admin-beslutning og scope/miljø.', state: 'current' },
        { title: 'Installation', detail: prodReady ? 'Production deployment starter først efter production-godkendelse.' : 'Starter først efter godkendelse.', state: 'waiting' },
      ],
    }
  }

  if (headendScoped) {
    const installerState: WorkflowStepState = headendDeployable
      ? (deployDone ? 'done' : deployRunning ? 'current' : deployFailed ? 'failed' : 'current')
      : (u.status === 'approved' ? 'blocked' : deployDone ? 'done' : 'waiting')
    const preflightState: WorkflowStepState = deployDone || phase === 'backup' || phase === 'install' || phase === 'restart' || phase === 'postflight' || phase === 'complete'
      ? 'done'
      : phase === 'preflight'
        ? 'current'
        : installerState === 'failed'
          ? 'failed'
          : headendDeployable
            ? 'waiting'
            : 'blocked'
    const backupState: WorkflowStepState = deployDone || phase === 'install' || phase === 'restart' || phase === 'postflight' || phase === 'complete'
      ? 'done'
      : phase === 'backup'
        ? 'current'
        : headendDeployable
          ? 'waiting'
          : 'blocked'
    const installState: WorkflowStepState = deployDone || phase === 'postflight' || phase === 'complete'
      ? 'done'
      : phase === 'install' || phase === 'restart'
        ? 'current'
        : deployFailed
          ? 'failed'
          : headendDeployable
            ? 'waiting'
            : 'blocked'
    const postflightState: WorkflowStepState = deployDone
      ? 'done'
      : phase === 'postflight'
        ? 'current'
        : deployFailed
          ? 'failed'
          : headendDeployable
            ? 'waiting'
            : 'blocked'

    return {
      title: 'Headend installationsflow',
      nextAction: deployDone
        ? (u.environment === 'test' && u.production_promotion_id
          ? `Test-deploy er færdig og promoveret til production som #${u.production_promotion_id}.`
          : u.environment === 'test'
            ? 'Test-deploy er færdig. Næste governance-trin er promovering til production.'
            : 'Production aktivering er færdig og postflight-valideret.')
        : headendDeployable
        ? 'Tryk “Installer på Headend”. Flowet tager backup, installerer og funktionstester før status ændres.'
        : 'Der mangler et implementeret Headend-installer-flow for denne applikation. Den må ikke installeres manuelt uden lab-flow, backup og postflight-test.',
      steps: [
        { title: 'Godkendt', detail: `${u.approved_by || 'Admin'} godkendte til ${u.environment || 'ukendt miljø'}.`, state: 'done' },
        { title: 'Installer-flow', detail: deployDone ? 'Headend flow er gennemført og dokumenteret.' : headendFormula(u) === 'postgresql@17' ? 'DB-maintenance profil er implementeret med ekstra database-checks.' : headendDeployable ? 'UI-installation er implementeret for denne Headend update.' : 'Installer-flow skal bygges og testes i lab før installation.', state: installerState },
        { title: 'Preflight', detail: headendFormula(u) === 'postgresql@17' ? 'Tjek PostgreSQL version, pg_isready, DB-login og service-state.' : 'Tjek nuværende version, service, API og relevante logs.', state: preflightState },
        { title: 'Pre-update backup', detail: headendFormula(u) === 'postgresql@17' ? 'Tag pg_dump/database backup og LaunchAgent rollback-evidence.' : 'Tag Headend config/database backup og rollback-evidence.', state: backupState },
        { title: 'Install/reload', detail: u.environment === 'production' ? 'Production aktivering validerer deployed test-version uden ny brew upgrade på samme Headend.' : 'Installer pakken og reload relevant LaunchAgent/service.', state: installState },
        { title: 'Postflight', detail: 'Valider version, API, funktionstest og fejl i logs.', state: postflightState },
      ],
    }
  }

  if (u.status === 'approved') {
    const edgeStarted = ['backing_up', 'downloading', 'verifying', 'installing'].includes(edgeTargetStatus)
    const backupActive = edgeTargetStatus === 'backing_up'
    const backupDone = ['downloading', 'verifying', 'installing'].includes(edgeTargetStatus)
    const trustActive = edgeTargetStatus === 'verifying'
    const trustDone = edgeStarted && !trustActive
    const installActive = ['downloading', 'installing'].includes(edgeTargetStatus)
    return {
      title: 'Edge pull-flow',
      nextAction: 'Edge henter selv opdateringen ved næste policy-poll. Den skal have et signeret artifact og lave pre-update backup før installation.',
      steps: [
        { title: 'Godkendt', detail: `${u.approved_by || 'Admin'} godkendte update til ${u.environment || 'ukendt miljø'}.`, state: 'done' },
        { title: 'Afventer Edge poll', detail: 'Edge kalder Headend og henter update-policy.', state: edgeStarted ? 'done' : 'current' },
        { title: 'Artifact trust check', detail: 'Edge validerer signatur, sha256 og signer-scope.', state: trustActive ? 'current' : trustDone ? 'done' : 'waiting' },
        { title: 'Pre-update backup', detail: 'Edge laver lokal restore-backup og uploader til Headend.', state: backupActive ? 'current' : backupDone ? 'done' : 'waiting' },
        { title: 'Install/rollback', detail: 'Edge downloader, installerer eller ruller tilbage og rapporterer resultat.', state: installActive ? 'current' : 'waiting' },
      ],
    }
  }

  if (u.status === 'blocked' && (u.update_type === 'os_security' || u.update_type === 'os_updates')) {
    return {
      title: 'Edge OS offline update-flow',
      nextAction: 'Denne Edge OS update er blokeret, indtil lab har bygget og registreret et Headend-signeret offline OS artifact.',
      steps: [
        { title: 'Rapporteret', detail: 'Edge/CMDB har rapporteret manglende OS-pakker.', state: 'done' },
        { title: 'Blokeret', detail: 'Edge må ikke køre apt-get upgrade eller hente direkte fra internet.', state: 'blocked' },
        { title: 'Lab bundle', detail: 'Byg offline apt/dpkg bundle i lab med præcis pakkeliste og test-evidence.', state: 'current' },
        { title: 'Signer artifact', detail: 'Registrer bundle i Headend artifact-kataloget med manifest, sha256 og signatur.', state: 'waiting' },
        { title: 'Godkend', detail: 'Bind artifact til update og godkend deployment.', state: 'waiting' },
        { title: 'Edge pull', detail: 'Edge henter bundle, tager backup, installerer offline og rapporterer resultat.', state: 'waiting' },
      ],
    }
  }

  if (u.status === 'deployed') {
    if (!headendScoped) {
      return {
        title: 'Edge pull-flow',
        nextAction: u.environment === 'test' ? 'Test-deploy er færdig. Næste governance-trin er testaccept før pakken markeres Prod-klar.' : 'Deploy er færdig. Overvåg drift og behold rollback-evidence.',
        steps: [
          { title: 'Godkendt', detail: 'Update blev godkendt.', state: 'done' },
          { title: 'Edge poll', detail: 'Edge hentede den signerede update-policy.', state: 'done' },
          { title: 'Artifact trust check', detail: 'Signatur, sha256 og signer-scope blev accepteret.', state: 'done' },
          { title: 'Pre-update backup', detail: 'Restore-backup blev oprettet før installation.', state: 'done' },
          { title: 'Installeret', detail: `Edge rapporterede deployment ${fmt(u.deployed_at)}.`, state: 'done' },
        ],
      }
    }
    return {
      title: 'Deploy-flow',
      nextAction: u.environment === 'test' ? 'Test-deploy er færdig. Næste governance-trin er at markere pakken Prod-klar efter testaccept.' : 'Deploy er færdig. Overvåg drift og behold rollback-evidence.',
      steps: [
        { title: 'Godkendt', detail: 'Update blev godkendt.', state: 'done' },
        { title: 'Installeret', detail: `Deployet ${fmt(u.deployed_at)}.`, state: 'done' },
        { title: 'Næste trin', detail: u.environment === 'test' ? 'Kan markeres Prod-klar efter testaccept.' : 'Drift/monitorering.', state: u.environment === 'test' ? 'current' : 'done' },
      ],
    }
  }

  return {
    title: 'Update-flow',
    nextAction: `Aktuel status er ${STATUS_LABELS[u.status] ?? u.status}.`,
    steps: [
      { title: STATUS_LABELS[u.status] ?? u.status, detail: u.status === 'blocked' ? 'Kræver artifact/profil før installation kan fortsætte.' : 'Se beskrivelse og auditfelter ovenfor.', state: u.status === 'rolled_back' ? 'failed' : u.status === 'blocked' ? 'blocked' : 'current' },
    ],
  }
}

function WorkflowStatusPanel({ update, deployStatus, flowStatus }: { update: Update; deployStatus?: HeadendDeployStatus; flowStatus?: UpdateFlowStatus }) {
  const workflow = workflowForUpdate(update, deployStatus, flowStatus)
  const prodReady = isProdReadyUpdate(update)
  return (
    <div className="mt-3 rounded-lg border border-gray-200 bg-white p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-xs font-semibold text-gray-800">{workflow.title}</div>
          <div className="text-[11px] text-gray-500 mt-0.5">{workflow.nextAction}</div>
        </div>
        <span className={`text-[11px] px-1.5 py-0.5 rounded border ${prodReady ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-gray-50 text-gray-500 border-gray-200'}`}>
          {prodReady ? 'prod-klar' : (update.environment || 'ukendt miljø')}
        </span>
      </div>
      <div className="mt-3 grid grid-cols-1 md:grid-cols-3 xl:grid-cols-6 gap-2">
        {workflow.steps.map((step, index) => (
          <div key={`${step.title}-${index}`} className={`rounded-lg border p-3 min-h-[92px] ${stepStyle(step.state)}`}>
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full flex-shrink-0 ${stepDotStyle(step.state)}`} />
              <span className="text-[11px] font-semibold">{index + 1}. {step.title}</span>
            </div>
            <div className="mt-1 text-[11px] leading-4 opacity-90">{step.detail}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

function FlowTargetsPanel({ flowStatus }: { flowStatus?: UpdateFlowStatus }) {
  if (!flowStatus) {
    return (
      <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-700">
        Edge flow-status er ikke hentet endnu. Opdatér siden eller fold rækken ud igen.
      </div>
    )
  }
  if (flowStatus.error) {
    return (
      <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-700">
        Edge flow-status kunne ikke hentes: {flowStatus.error}
      </div>
    )
  }
  return (
    <div className="mt-3 rounded-lg border border-gray-200 bg-white p-3 text-xs">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-semibold text-gray-800">Edge flow-status</div>
          <div className="mt-0.5 text-gray-500">{flowStatus.stage.label}</div>
        </div>
        <div className="text-right text-[11px] text-gray-400">
          {flowStatus.ticket_id ? `Ticket ${flowStatus.ticket_id}` : 'Ingen ticket'}
          <br />
          {flowStatus.artifact?.artifact_id ? `Artifact ${flowStatus.artifact.artifact_id}` : 'Ingen artifact'}
        </div>
      </div>
      <div className="mt-3 divide-y divide-gray-100">
        {flowStatus.targets.length === 0 ? (
          <div className="py-2 text-gray-400">Ingen target-enheder fundet for denne update.</div>
        ) : flowStatus.targets.map(target => (
          <div key={target.device_id} className="py-2 first:pt-0 last:pb-0">
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="font-mono text-[11px] text-gray-800 truncate">{target.device_id}</div>
                <div className="text-[11px] text-gray-400 truncate">{target.hostname || 'hostname ukendt'}</div>
              </div>
              <span className={`px-2 py-1 rounded border text-[11px] font-medium ${statusBadge(target.status === 'failed' ? 'blocked' : target.status)}`}>
                {TARGET_STATUS_LABELS[target.status] ?? target.status}
              </span>
            </div>
            <div className="mt-2 grid grid-cols-1 sm:grid-cols-3 gap-x-4 gap-y-1 text-[11px] text-gray-500">
              <div><span className="text-gray-400">Venter på: </span>{target.waiting_for ? (WAITING_LABELS[target.waiting_for] ?? target.waiting_for) : '—'}</div>
              <div><span className="text-gray-400">Sidst set: </span>{fmt(target.last_seen)}</div>
              <div><span className="text-gray-400">Sidste rapport: </span>{fmt(target.last_report_at)}</div>
            </div>
            {target.last_error && (
              <div className="mt-2 rounded bg-red-50 p-2 text-[11px] text-red-700">{target.last_error}</div>
            )}
          </div>
        ))}
      </div>
      <div className="mt-3 border-t border-gray-100 pt-2 text-[11px] text-gray-400">
        {flowStatus.next_edge_poll}
      </div>
    </div>
  )
}

function UpdateRow({ u, onApprove, onReject, onPromote, onRollback, onHeadendDeploy, onBindArtifact, onBuildOsBundle, onRequestFlow, busy, deployStatus, flowStatus }: {
  u: Update
  onApprove:  (id: number) => void
  onReject:   (id: number) => void
  onPromote:  (id: number, target: 'staging' | 'production') => void
  onRollback: (id: number) => void
  onHeadendDeploy: (id: number) => void
  onBindArtifact: (id: number, artifactId: string) => void
  onBuildOsBundle: (id: number) => void
  onRequestFlow: (id: number) => void
  busy: number | null
  deployStatus?: HeadendDeployStatus
  flowStatus?: UpdateFlowStatus
}) {
  const [open, setOpen] = useState(false)
  const [artifactId, setArtifactId] = useState('')
  const isBusy = busy === u.id
  const prodReady = isProdReadyUpdate(u)
  const headendDeployable = canDeployOnHeadend(u)
  const headendScoped = isHeadendScoped(u)
  const deployRunning = deployStatus?.running === true
  const isOsUpdate = u.update_type === 'os_security' || u.update_type === 'os_updates'
  const osArtifactMissing = isOsUpdate && !flowStatus?.artifact

  return (
    <div className="border-b border-gray-50 last:border-0">
      <button onClick={() => {
        const nextOpen = !open
        setOpen(nextOpen)
        if (nextOpen && !flowStatus) onRequestFlow(u.id)
      }}
        title={open ? 'Luk opdateringsdetaljer' : 'Vis opdateringsdetaljer og aktuel flow-status'}
        className="w-full flex items-center gap-3 px-5 py-4 hover:bg-gray-50 transition-colors text-left">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-mono font-semibold text-gray-700">#{u.id}</span>
            <span className="text-sm font-medium text-gray-800">
              {TYPE_LABELS[u.update_type] ?? u.update_type}
            </span>
            <span className="text-xs font-mono text-gray-500">{u.version.startsWith('v') ? u.version : `commit ${shortHash(u.version)}`}</span>
            <span className={`text-[11px] px-1.5 py-0.5 rounded border font-medium ${severityBadge(u.severity)}`}>
              {u.severity}
            </span>
            <span className={`text-[11px] px-1.5 py-0.5 rounded border font-medium ${statusBadge(u.status)}`}>
              {prodReady ? 'Prod-klar' : (STATUS_LABELS[u.status] ?? u.status)}
            </span>
            {u.environment && (
              <span className={`text-[11px] px-1.5 py-0.5 rounded border font-medium ${u.environment === 'lab' ? 'bg-sky-50 text-sky-700 border-sky-200' : u.environment === 'test' ? 'bg-purple-50 text-purple-700 border-purple-200' : prodReady ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-gray-50 text-gray-500 border-gray-200'}`}>
                {u.environment === 'lab' ? 'lab' : u.environment === 'test' ? 'test' : prodReady ? 'prod-klar' : 'prod'}
              </span>
            )}
            {u.scope !== 'global' && (
              <span className="text-[11px] px-1.5 py-0.5 rounded border bg-gray-50 text-gray-500 border-gray-200">
                {u.scope}{u.scope_id ? `: ${u.scope_id}` : ''}
              </span>
            )}
          </div>
          {flowStatus?.artifact && (
            <p className="text-[11px] font-mono text-gray-500 mt-1 break-all">
              Artifact: {flowStatus.artifact.artifact_id}
              {flowStatus.artifact.version ? ` · ${flowStatus.artifact.version}` : ''}
            </p>
          )}
          <p className="text-xs text-gray-400 mt-0.5">Oprettet {fmt(u.created_at)}</p>
        </div>
        {u.status === 'pending' && (
          <div className="flex items-center gap-1.5 flex-shrink-0" onClick={e => e.stopPropagation()}>
            <button onClick={() => { onApprove(u.id) }}
              disabled={isBusy || osArtifactMissing}
              title={osArtifactMissing ? 'Byg og bind et signeret offline OS artifact først' : undefined}
              className="flex items-center gap-1 px-3 py-1.5 bg-green-500 hover:bg-green-600 text-white text-xs rounded-lg disabled:opacity-50 transition-colors">
              <CheckCircle className="w-3.5 h-3.5" />
              {prodReady ? 'Godkend prod' : 'Godkend'}
            </button>
            <button onClick={() => onReject(u.id)} disabled={isBusy}
              title="Afvis opdateringen. Den distribueres ikke; begrundelsen registreres i change-flowet."
              className="flex items-center gap-1 px-3 py-1.5 bg-red-50 hover:bg-red-100 text-red-600 text-xs rounded-lg border border-red-200 disabled:opacity-50 transition-colors">
              <XCircle className="w-3.5 h-3.5" />
              Afvis
            </button>
          </div>
        )}
        {(u.status === 'blocked' || u.status === 'rolled_back') && (
          <div className="flex items-center gap-1.5 flex-shrink-0" onClick={e => e.stopPropagation()}>
            <button onClick={() => onApprove(u.id)} disabled={isBusy}
              title="Genåbn den blokerede eller tilbagekaldte opdatering til fornyet godkendelse."
              className="flex items-center gap-1 px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white text-xs rounded-lg disabled:opacity-50">
              <RefreshCw className="w-3.5 h-3.5" />
              Genprøv
            </button>
          </div>
        )}
        {u.status === 'deployed' && u.environment === 'test' && (
          <div className="flex items-center gap-1.5 flex-shrink-0" onClick={e => e.stopPropagation()}>
            {u.production_promotion_id ? (
              <span className="px-3 py-1.5 rounded-lg border border-emerald-200 bg-emerald-50 text-emerald-700 text-xs">
                Prod #{u.production_promotion_id} · {u.production_promotion_status === 'pending' ? 'Prod-klar' : (STATUS_LABELS[u.production_promotion_status || ''] ?? u.production_promotion_status)}
              </span>
            ) : (
              <>
                <button onClick={() => onPromote(u.id, 'staging')} disabled={isBusy}
                  title="Opret en staging-promotion. Installeres først efter staging-godkendelse."
                  className="flex items-center gap-1 px-3 py-1.5 bg-white hover:bg-gray-50 text-gray-700 text-xs rounded-lg border border-gray-200 disabled:opacity-50">
                  Promovér til staging
                </button>
                <button onClick={() => onPromote(u.id, 'production')} disabled={isBusy}
                  title="Marker som klar til produktionsgodkendelse. Det installerer ikke noget endnu."
                  className="flex items-center gap-1 px-3 py-1.5 bg-sky-500 hover:bg-sky-600 text-white text-xs rounded-lg disabled:opacity-50">
                  Markér prod-klar
                </button>
              </>
            )}
          </div>
        )}
        {u.status === 'deployed' && (
          <div className="flex items-center gap-1.5 flex-shrink-0" onClick={e => e.stopPropagation()}>
            <button onClick={() => onRollback(u.id)} disabled={isBusy}
              title="Anmod Edge eller Headend om kontrolleret rollback til forrige verificerede release."
              className="flex items-center gap-1 px-3 py-1.5 bg-amber-50 hover:bg-amber-100 text-amber-700 text-xs rounded-lg border border-amber-200 disabled:opacity-50">
              ↩ Rollback
            </button>
          </div>
        )}
        {u.status === 'approved' && (
          headendDeployable ? (
            <div className="flex items-center gap-1.5 mr-3 flex-shrink-0" onClick={e => e.stopPropagation()}>
              <button onClick={() => onHeadendDeploy(u.id)} disabled={isBusy || deployRunning}
                title={u.environment === 'production' ? 'Aktivér den allerede godkendte release på Headend.' : 'Installer den godkendte release på test-Headend.'}
                className="flex items-center gap-1 px-3 py-1.5 bg-gray-900 hover:bg-gray-800 text-white text-xs rounded-lg disabled:opacity-50">
                <Package className="w-3.5 h-3.5" />
                {deployRunning ? 'Kører...' : u.environment === 'production' ? 'Aktivér prod' : 'Installer på Headend'}
              </button>
            </div>
          ) : (
            <div className={`flex items-center gap-1.5 mr-3 text-xs flex-shrink-0 ${headendScoped ? 'text-amber-600' : 'text-sky-500'}`}>
              <Clock className="w-3.5 h-3.5 animate-pulse" />
              {headendScoped ? 'Afventer Headend-flow' : 'Afventer edge'}
            </div>
          )
        )}
        {open ? <ChevronDown className="w-4 h-4 text-gray-300 flex-shrink-0" />
               : <ChevronRight className="w-4 h-4 text-gray-300 flex-shrink-0" />}
      </button>
      {open && (
        <div className="px-5 pb-4 pt-1 bg-gray-50 border-t border-gray-100">
          <div className="grid grid-cols-2 gap-x-8 gap-y-1.5 text-xs">
            {u.description && (
              <div className="col-span-2 mb-1">
                <span className="text-gray-400">Beskrivelse: </span>
                <span className="text-gray-700">{u.description}</span>
              </div>
            )}
            <div><span className="text-gray-400">Type: </span><span className="text-gray-700 font-mono">{u.update_type}</span></div>
            <div><span className="text-gray-400">Scope: </span><span className="text-gray-700">{u.scope}{u.scope_id ? ` / ${u.scope_id}` : ''}</span></div>
            <div><span className="text-gray-400">Oprettet: </span><span className="text-gray-700">{fmt(u.created_at)}</span></div>
            {u.approved_at && <div><span className="text-gray-400">Behandlet: </span><span className="text-gray-700">{fmt(u.approved_at)} af {u.approved_by}</span></div>}
            {u.deployed_at && <div><span className="text-gray-400">Deployet: </span><span className="text-gray-700">{fmt(u.deployed_at)}</span></div>}
            <div><span className="text-gray-400">ID: </span><span className="text-gray-500 font-mono">#{u.id}</span></div>
          </div>
          <WorkflowStatusPanel update={u} deployStatus={deployStatus} flowStatus={flowStatus} />
          {!headendScoped && <FlowTargetsPanel flowStatus={flowStatus} />}
          {(u.status === 'pending' || u.status === 'blocked') && isOsUpdate && osArtifactMissing && (
            <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs">
              <div className="font-medium text-amber-800">Byg og bind signeret OS artifact før godkendelse</div>
              <div className="mt-1 text-amber-700">
                Headend bygger via Mac-container/lab-builder, registrerer artifactet og binder det til denne update. Manuel artifact-binding er kun til fejlsøgning.
              </div>
              <div className="mt-3 flex flex-col sm:flex-row gap-2">
                <button onClick={() => onBuildOsBundle(u.id)} disabled={isBusy}
                  title="Byg, signér, registrér og bind et offline OS-artifact fra Headend. Edge henter det ved næste poll."
                  className="px-3 py-2 rounded-lg bg-gray-900 text-white text-xs disabled:opacity-50">
                  Byg artifact og bind
                </button>
                <input value={artifactId} onChange={e => setArtifactId(e.target.value)}
                  placeholder="TL-OS-YYYYMMDD-..."
                  title="ID på et allerede lab-testet og signeret OS-artifact. Brug kun ved kontrolleret fejlsøgning."
                  className="flex-1 rounded-lg border border-amber-200 bg-white px-3 py-2 font-mono text-[11px] text-gray-800" />
                <button onClick={() => onBindArtifact(u.id, artifactId.trim())} disabled={!artifactId.trim() || isBusy}
                  title="Bind det angivne, signerede artifact til opdateringen."
                  className="px-3 py-2 rounded-lg bg-amber-600 text-white text-xs disabled:opacity-50">
                  Bind artifact
                </button>
              </div>
            </div>
          )}
          {deployStatus && (
            <div className="mt-3 rounded-lg border border-gray-200 bg-white p-3 text-xs">
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${deployStatus.running ? 'bg-sky-500 animate-pulse' : deployStatus.status === 'failed' ? 'bg-red-500' : deployStatus.status === 'deployed' ? 'bg-green-500' : 'bg-gray-300'}`} />
                <span className="font-medium text-gray-700">{deployStatus.message || deployStatus.status}</span>
              </div>
              <div className="mt-2 grid grid-cols-2 gap-x-5 gap-y-1 text-[11px] text-gray-500">
                {deployStatus.phase && <div><span className="text-gray-400">Fase: </span>{deployStatus.phase}</div>}
                {deployStatus.backup_file && <div className="truncate"><span className="text-gray-400">Backup: </span>{deployStatus.backup_file}</div>}
                {deployStatus.rollback_performed && <div><span className="text-gray-400">Rollback: </span>udført</div>}
                {deployStatus.rollback_message && <div className="col-span-2"><span className="text-gray-400">Rollback note: </span>{deployStatus.rollback_message}</div>}
              </div>
              {deployStatus.stderr_tail && (
                <pre className="mt-2 max-h-28 overflow-auto whitespace-pre-wrap rounded bg-red-50 p-2 text-[11px] text-red-700">{deployStatus.stderr_tail}</pre>
              )}
              {deployStatus.stdout_tail && (
                <pre className="mt-2 max-h-28 overflow-auto whitespace-pre-wrap rounded bg-gray-50 p-2 text-[11px] text-gray-600">{deployStatus.stdout_tail}</pre>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function DeviceUpdateMatrix({ matrix }: { matrix: UpdateMatrix | null }) {
  if (!matrix) return null
  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden mb-5">
      <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
            <Server className="w-4 h-4 text-gray-500" />
            CMDB-baseret opdateringsstatus
          </h2>
          <p className="text-xs text-gray-400 mt-0.5">
            Installeret, tilgængeligt og manglende patches pr. enhed med samlet risikoscore.
          </p>
        </div>
        <div className="text-xs text-gray-400">
          {matrix.devices.length} enhed{matrix.devices.length === 1 ? '' : 'er'}
        </div>
      </div>

      {matrix.devices.length === 0 ? (
        <div className="py-10 text-center text-sm text-gray-400">Ingen CMDB-enheder fundet</div>
      ) : (
        <div className="divide-y divide-gray-100">
          {matrix.devices.map(device => (
            <div key={device.device_id} className="p-5">
              <div className="flex items-start justify-between gap-4 mb-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-semibold text-gray-900 font-mono">{device.device_id}</span>
                    <span className="text-[11px] px-1.5 py-0.5 rounded border bg-sky-50 text-sky-700 border-sky-200">
                      {device.cmdb_ref}
                    </span>
                    <span className="text-[11px] px-1.5 py-0.5 rounded border bg-gray-50 text-gray-600 border-gray-200">
                      {device.environment || 'ukendt miljø'}
                    </span>
                    {device.missing_count > 0 && (
                      <span className="text-[11px] px-1.5 py-0.5 rounded border bg-amber-50 text-amber-700 border-amber-200">
                        {device.missing_count} mangler
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-gray-400 mt-1">
                    {[device.hardware_model, device.hostname, device.customer_name, device.site_name].filter(Boolean).join(' / ') || 'Ingen ekstra CMDB-kontekst'}
                  </p>
                </div>
                <div className={`flex items-center gap-1.5 px-2 py-1 rounded border text-xs font-medium ${riskBadge({ score: device.risk_score, level: device.risk_score >= 85 ? 'critical' : device.risk_score >= 70 ? 'high' : device.risk_score >= 45 ? 'medium' : 'low', factors: [] })}`}>
                  <BarChart3 className="w-3.5 h-3.5" />
                  Risk {device.risk_score}
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-2">
                {matrix.categories.map(category => {
                  const cell = device.categories[category.key]
                  if (!cell) return null
                  return (
                    <div key={category.key} className="border border-gray-100 rounded-lg p-3 bg-gray-50">
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <div className="text-xs font-medium text-gray-800">{category.label}</div>
                          <div className="text-[11px] text-gray-400 mt-0.5">{STATE_LABELS[cell.state] ?? cell.state}</div>
                        </div>
                        <span className={`text-[11px] px-1.5 py-0.5 rounded border font-medium ${riskBadge(cell.risk)}`}>
                          {cell.risk.score}
                        </span>
                      </div>
                      <div className="mt-2 space-y-1 text-[11px]">
                        <div className="flex justify-between gap-2">
                          <span className="text-gray-400">Aktuel version</span>
                          <span className="text-gray-700 truncate text-right">{cell.current_version || cell.installed || '-'}</span>
                        </div>
                        <div className="flex justify-between gap-2">
                          <span className="text-gray-400">Senest tilgængelig</span>
                          <span className={cell.available ? 'text-gray-800 font-medium truncate text-right' : 'text-gray-300'}>
                            {cell.latest_available_version || cell.available || 'Ingen'}
                          </span>
                        </div>
                        {cell.package_count != null && (
                          <div className="flex justify-between gap-2">
                            <span className="text-gray-400">Pakker</span>
                            <span className="text-gray-600">{cell.package_count}</span>
                          </div>
                        )}
                        {cell.pending_update_id && (
                          <div className="flex justify-between gap-2">
                            <span className="text-gray-400">Update ID</span>
                            <span className="text-gray-600 font-mono">#{cell.pending_update_id}</span>
                          </div>
                        )}
                        {cell.risk.factors.length > 0 && (
                          <div className="text-gray-400 pt-1 line-clamp-2">
                            {cell.risk.factors.join(', ')}
                          </div>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function ArtifactCatalog({
  artifacts,
  onCatalogCurrent,
  onCatalogOsBundle,
  busy,
}: {
  artifacts: UpdateArtifact[]
  onCatalogCurrent: () => void
  onCatalogOsBundle: (payload: Record<string, unknown>) => void
  busy: boolean
}) {
  const [osOpen, setOsOpen] = useState(false)
  const [osPath, setOsPath] = useState('/tmp/timelapse-os-bundle')
  const [osVersion, setOsVersion] = useState('edge-os-security-bundle')
  const [osCommands, setOsCommands] = useState('[{"name":"offline dpkg install","argv":["/bin/bash","{bundle}/install-offline.sh"],"timeout_s":1800}]')
  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden mb-5">
      <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
            <FileCheck className="w-4 h-4 text-gray-500" />
            Signeret artifact-katalog
          </h2>
          <p className="text-xs text-gray-400 mt-0.5">
            Release- og OS-manifester som Headend kan binde til change tickets og stille klar til Edge pull-flow.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setOsOpen(o => !o)} disabled={busy}
            title="Vis eller skjul manuel registrering af et allerede bygget OS-bundle."
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-white text-gray-700 border border-gray-200 rounded-lg disabled:opacity-50">
            <Package className="w-3.5 h-3.5" />
            OS bundle
          </button>
          <button onClick={onCatalogCurrent} disabled={busy}
            title="Verificér det seneste signerede Git-tag og registrér det som release-artifact."
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-gray-900 text-white rounded-lg disabled:opacity-50">
            <Fingerprint className="w-3.5 h-3.5" />
            Registrer seneste signerede tag
          </button>
        </div>
      </div>
      {osOpen && (
        <div className="px-5 py-4 border-b border-gray-100 bg-gray-50">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
            <div>
              <label className="block text-gray-500 mb-1" title="Eksisterende mappe med et lab-testet offline OS-bundle på Headend.">Bundle-sti på Headend</label>
              <input value={osPath} onChange={e => setOsPath(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 font-mono" />
            </div>
            <div>
              <label className="block text-gray-500 mb-1" title="Entydig, menneskelæsbar version for artifactet.">Version</label>
              <input value={osVersion} onChange={e => setOsVersion(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 font-mono" />
            </div>
            <div className="md:col-span-2">
              <label className="block text-gray-500 mb-1" title="Strukturerede, offline installkommandoer. Må kun pege på filer inde i det signerede bundle.">Install commands JSON</label>
              <textarea value={osCommands} onChange={e => setOsCommands(e.target.value)}
                className="w-full min-h-20 border border-gray-200 rounded-lg px-3 py-2 font-mono" />
              <p className="mt-1 text-[11px] text-gray-400">
                Bundlet skal være bygget i lab og indeholde packages/*.deb, package-manifest.json og verify-installed.sh.
              </p>
            </div>
          </div>
          <button onClick={() => onCatalogOsBundle({
            storage_path: osPath,
            version: osVersion,
            commands_json: osCommands,
          })} disabled={busy}
            title="Valider bundleindholdet, opret manifest og signér artifactet."
            className="mt-3 flex items-center gap-1.5 px-3 py-1.5 text-xs bg-gray-900 text-white rounded-lg disabled:opacity-50">
            <FileCheck className="w-3.5 h-3.5" />
            Registrer signeret OS artifact
          </button>
        </div>
      )}
      {artifacts.length === 0 ? (
        <div className="px-5 py-8 text-center text-sm text-gray-400">
          Ingen artifacts registreret endnu.
        </div>
      ) : (
        <div className="divide-y divide-gray-100">
          {artifacts.slice(0, 5).map(artifact => (
            <div key={artifact.artifact_id} className="px-5 py-4">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-semibold text-gray-900 font-mono">{artifact.artifact_id}</span>
                    <span className="text-[11px] px-1.5 py-0.5 rounded border bg-sky-50 text-sky-700 border-sky-200">
                      {artifact.artifact_type}
                    </span>
                    {artifact.manifest?.source?.dirty_worktree && (
                      <span className="text-[11px] px-1.5 py-0.5 rounded border bg-amber-50 text-amber-700 border-amber-200">
                        dirty worktree
                      </span>
                    )}
                  </div>
                  <div className="mt-1 text-xs text-gray-400">
                    {artifact.source_ref || '-'} / {shortHash(artifact.source_commit)} / {fmt(artifact.created_at)}
                  </div>
                  <div className="mt-2 grid grid-cols-1 md:grid-cols-3 gap-2 text-[11px]">
                    <div className="bg-gray-50 rounded-lg px-3 py-2">
                      <div className="text-gray-400">Manifest SHA-256</div>
                      <div className="font-mono text-gray-700">{shortHash(artifact.sha256)}</div>
                    </div>
                    <div className="bg-gray-50 rounded-lg px-3 py-2">
                      <div className="text-gray-400">Signeret af</div>
                      <div className="text-gray-700 truncate">{artifact.signed_by || '-'}</div>
                    </div>
                    <div className="bg-gray-50 rounded-lg px-3 py-2">
                      <div className="text-gray-400">Outputs</div>
                      <div className="text-gray-700">{artifact.manifest?.outputs?.length ?? 0} filer</div>
                    </div>
                  </div>
                </div>
                <div className="text-right text-xs text-gray-400 flex-shrink-0">
                  <div>{artifact.filename || 'manifest'}</div>
                  <div>{artifact.size_bytes ? `${Math.round(artifact.size_bytes / 1024)} KB` : '-'}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function LabCatalogImport({
  onImport,
  onRefreshBuilder,
  busy,
}: {
  onImport: (payload: Record<string, unknown>) => void
  onRefreshBuilder: (payload: Record<string, unknown>) => void
  busy: boolean
}) {
  const [open, setOpen] = useState(false)
  const [deviceId, setDeviceId] = useState('TL-C87FF9587CA0')
  const [environment, setEnvironment] = useState('lab')
  const [source, setSource] = useState('lab-import:ubuntu-24.04-arm64')
  const [aptText, setAptText] = useState('')
  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden mb-5">
      <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
            <Shield className="w-4 h-4 text-gray-500" />
            Lab-katalog til Edge OS updates
          </h2>
          <p className="text-xs text-gray-400 mt-0.5">
            Importerer lab/mirror apt-output, reconciler mod CMDB og opretter blokerede update-poster indtil der findes signeret OS bundle.
          </p>
        </div>
        <button onClick={() => setOpen(o => !o)} disabled={busy}
          title="Vis eller skjul import af OS-katalog fra lab eller Headend-builder."
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-white text-gray-700 border border-gray-200 rounded-lg disabled:opacity-50">
          <Package className="w-3.5 h-3.5" />
          Importér katalog
        </button>
      </div>
      {open && (
        <div className="px-5 py-4 bg-gray-50">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
            <div>
              <label className="block text-gray-500 mb-1" title="Den Edge, hvis CMDB-inventory danner grundlag for kataloget.">Device ID</label>
              <input value={deviceId} onChange={e => setDeviceId(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 font-mono" />
            </div>
            <div>
              <label className="block text-gray-500 mb-1" title="Miljøet som kataloget og de oprettede update-poster hører til.">Miljø</label>
              <select value={environment} onChange={e => setEnvironment(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2">
                <option value="lab">Lab</option>
                <option value="staging">Staging</option>
                <option value="production">Production</option>
              </select>
            </div>
            <div>
              <label className="block text-gray-500 mb-1" title="Sporbar reference til den lab-builder eller mirror, der leverede kataloget.">Kilde</label>
              <input value={source} onChange={e => setSource(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 font-mono" />
            </div>
            <div className="md:col-span-3">
              <label className="block text-gray-500 mb-1" title="Pakkekatalog fra en godkendt lab/mirror-host. Edge må aldrig selv hente denne liste fra internettet.">Lab-output fra apt list --upgradable</label>
              <textarea value={aptText} onChange={e => setAptText(e.target.value)}
                placeholder={'Listing...\\nlibssl3/noble-security 3.0.13-0ubuntu3.5 arm64 [upgradable from: 3.0.13-0ubuntu3.4]'}
                className="w-full min-h-36 border border-gray-200 rounded-lg px-3 py-2 font-mono text-[11px]" />
              <p className="mt-1 text-[11px] text-gray-400">
                Listen må komme fra lab/mirror-hosten. Edge bruger den ikke som beslutningskilde og må stadig ikke køre online apt upgrade.
              </p>
            </div>
          </div>
          <button onClick={() => onImport({
            device_id: deviceId.trim(),
            environment,
            source: source.trim() || undefined,
            apt_list_text: aptText,
            create_updates: true,
          })} disabled={busy || !deviceId.trim() || !aptText.trim()}
            title="Sammenlign lab-kataloget med CMDB og opret blokerede updates, indtil et signeret artifact findes."
            className="mt-3 flex items-center gap-1.5 px-3 py-1.5 text-xs bg-gray-900 text-white rounded-lg disabled:opacity-50">
            <FileCheck className="w-3.5 h-3.5" />
            Reconcile og opret blokerede updates
          </button>
          <button onClick={() => onRefreshBuilder({
            device_id: deviceId.trim(),
            environment,
            source: `mac-docker-builder:${deviceId.trim()}`,
            image: 'ubuntu:24.04',
            architecture: 'arm64',
            create_updates: true,
          })} disabled={busy || !deviceId.trim()}
            title="Lad Headend generere et kandidatkatalog i den kontrollerede Mac Docker-builder."
            className="mt-3 ml-2 inline-flex items-center gap-1.5 px-3 py-1.5 text-xs bg-white text-gray-700 border border-gray-200 rounded-lg disabled:opacity-50">
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh fra CMDB/Mac-builder
          </button>
        </div>
      )}
    </div>
  )
}

function UpdateJobsPanel({ jobs }: { jobs: Record<string, UpdateJobStatus> }) {
  const items = Object.values(jobs).sort((a, b) => String(b.started_at || '').localeCompare(String(a.started_at || ''))).slice(0, 5)
  if (items.length === 0) return null
  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden mb-5">
      <div className="px-5 py-4 border-b border-gray-100">
        <h2 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
          <Clock className="w-4 h-4 text-gray-500" />
          Update jobs
        </h2>
      </div>
      <div className="divide-y divide-gray-100">
        {items.map(job => (
          <div key={job.job_id} className="px-5 py-3 text-xs">
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="font-medium text-gray-800 truncate">{job.title}</div>
                <div className="mt-0.5 text-gray-400 font-mono truncate">{job.job_id} · {job.phase}</div>
              </div>
              <span className={`px-2 py-0.5 rounded border ${job.status === 'done' ? 'bg-green-50 text-green-700 border-green-200' : job.status === 'failed' ? 'bg-red-50 text-red-700 border-red-200' : 'bg-sky-50 text-sky-700 border-sky-200'}`}>
                {job.running ? 'Kører' : job.status}
              </span>
            </div>
            <div className="mt-2 h-1.5 bg-gray-100 rounded-full overflow-hidden">
              <div className={`h-full ${job.status === 'failed' ? 'bg-red-500' : job.status === 'done' ? 'bg-green-500' : 'bg-sky-500'}`} style={{ width: `${Math.max(0, Math.min(100, job.progress || 0))}%` }} />
            </div>
            {job.message && <div className="mt-2 text-gray-500">{job.message}</div>}
          </div>
        ))}
      </div>
    </div>
  )
}

const FILTERS: { key: Filter; label: string }[] = [
  { key: 'pending',  label: 'Afventer' },
  { key: 'approved', label: 'Godkendt' },
  { key: 'blocked', label: 'Blokeret' },
  { key: 'deployed', label: 'Deployet' },
  { key: 'rejected',     label: 'Afvist' },
  { key: 'superseded',   label: 'Erstattet' },
  { key: 'rolled_back',  label: 'Rullet tilbage' },
  { key: 'all',      label: 'Alle' },
]

export function UpdatesPage() {
  const [updates, setUpdates]       = useState<Update[]>([])
  const [matrix, setMatrix]         = useState<UpdateMatrix | null>(null)
  const [artifacts, setArtifacts]   = useState<UpdateArtifact[]>([])
  const [loading, setLoading]       = useState(true)
  const [filter, setFilter]         = useState<Filter>('pending')
  const [busy, setBusy]             = useState<number | null>(null)
  const [lastRefresh, setLast]      = useState<Date | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError]           = useState<string | null>(null)
  const [notice, setNotice]         = useState<string | null>(null)
  const [approveId, setApproveId]   = useState<number | null>(null)
  const [headendDeployStatus, setHeadendDeployStatus] = useState<Record<number, HeadendDeployStatus>>({})
  const [flowStatuses, setFlowStatuses] = useState<Record<number, UpdateFlowStatus>>({})
  const [updateJobs, setUpdateJobs] = useState<Record<string, UpdateJobStatus>>({})
  const [customers, setCustomers]   = useState<Array<{id: string, name: string}>>([])
  const [sites, setSites]           = useState<Array<{id: string, name: string, customer_id: string}>>([])
  const [watchedUpdateIds, setWatchedUpdateIds] = useState<number[]>([])
  const [approveOpts, setApproveOpts] = useState<ApproveOptions>({
    environment: 'production', scope: 'device', scope_id: ''
  })
  const approveUpdate = approveId === null ? null : updates.find(update => update.id === approveId) ?? null

  const load = useCallback(async (spin = false, filterOverride?: Filter) => {
    if (spin) setRefreshing(true)
    setError(null)
    try {
      const activeFilter = filterOverride ?? filter
      const params = activeFilter === 'all' ? '' : `?status=${activeFilter}`
      const [data, matrixData, artifactData] = await Promise.all([
        api(`/api/updates/pending${params}`),
        api('/api/updates/device-matrix'),
        api('/api/updates/artifacts'),
      ])
      const updateList = Array.isArray(data) ? data as Update[] : []
      setUpdates(updateList)
      setMatrix(matrixData && Array.isArray(matrixData.devices) ? matrixData : null)
      setArtifacts(Array.isArray(artifactData) ? artifactData : [])
      const activeFlowUpdates = updateList.filter(u => u.status === 'approved')
      const flowPairs = await Promise.all(activeFlowUpdates.map(async u => {
        try {
          const status = await api(`/api/updates/${u.id}/flow-status`)
          return [u.id, status as UpdateFlowStatus] as const
        } catch (error: unknown) {
          return [u.id, {
            update_id: u.id,
            status: u.status,
            stage: { key: 'unavailable', label: 'Flow-status utilgængelig' },
            artifact: null,
            ticket_id: null,
            targets: [],
            next_edge_poll: '',
            error: getErrorMessage(error),
          } as UpdateFlowStatus] as const
        }
      }))
      const nextFlowStatuses: Record<number, UpdateFlowStatus> = {}
      for (const [id, value] of flowPairs) {
        if (value) nextFlowStatuses[id] = value
      }
      setFlowStatuses(nextFlowStatuses)
      setWatchedUpdateIds(ids => ids.filter(id => isActiveFlow(nextFlowStatuses[id])))
      setLast(new Date())
    } catch (error: unknown) {
      setError(`Kunne ikke hente opdateringer (${getErrorMessage(error)})`)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [filter])

  useEffect(() => { load() }, [load])

  const requestFlowStatus = useCallback(async (id: number) => {
    try {
      const status = await api(`/api/updates/${id}/flow-status`) as UpdateFlowStatus
      setFlowStatuses(current => ({ ...current, [id]: status }))
    } catch (error: unknown) {
      setFlowStatuses(current => ({
        ...current,
        [id]: {
          update_id: id,
          status: updates.find(update => update.id === id)?.status || 'unknown',
          stage: { key: 'unavailable', label: 'Flow-status utilgængelig' },
          artifact: null,
          ticket_id: null,
          targets: [],
          next_edge_poll: '',
          error: getErrorMessage(error),
        },
      }))
    }
  }, [updates])

  useEffect(() => {
    const shouldPoll =
      watchedUpdateIds.length > 0 ||
      updates.some(u => u.status === 'approved') ||
      Object.values(flowStatuses).some(isActiveFlow)
    if (!shouldPoll || loading || refreshing) return
    const timer = window.setInterval(() => {
      load(false)
    }, 5000)
    return () => window.clearInterval(timer)
  }, [watchedUpdateIds, updates, flowStatuses, loading, refreshing, load])

  // Hent customers og sites til scope dropdown (P1-02)
  useEffect(() => {
    const loadCustomersAndSites = async () => {
      try {
        const [customersData, sitesData] = await Promise.all([
          api('/api/admin/customers'),
          api('/api/admin/sites'),
        ])
        setCustomers(Array.isArray(customersData)
          ? customersData
              .filter((c): c is Customer => Boolean(c && typeof c === 'object' && typeof (c as { id?: unknown }).id === 'string' && typeof (c as { name?: unknown }).name === 'string'))
              .map(c => ({ id: c.id, name: c.name }))
          : [])
        setSites(Array.isArray(sitesData)
          ? sitesData
              .filter((s): s is Site => Boolean(s && typeof s === 'object' && typeof (s as { id?: unknown }).id === 'string' && typeof (s as { name?: unknown }).name === 'string' && typeof (s as { customer_id?: unknown }).customer_id === 'string'))
              .map(s => ({ id: s.id, name: s.name, customer_id: s.customer_id }))
          : [])
      } catch (error: unknown) {
        console.warn('Kunne ikke hente customers/sites:', getErrorMessage(error))
      }
    }
    loadCustomersAndSites()
  }, [])

  async function approve(id: number) {
    const requiresScopeId = ['device', 'customer', 'site'].includes(approveOpts.scope)
    if (requiresScopeId && !approveOpts.scope_id.trim()) {
      const label = approveOpts.scope === 'device' ? 'Device ID' : approveOpts.scope === 'customer' ? 'Kunde ID' : 'Site ID'
      setError(`${label} er påkrævet ved ${approveOpts.scope === 'device' ? 'specifik enhed' : approveOpts.scope === 'customer' ? 'kunde' : 'site'}-scope`)
      return
    }
    setBusy(id)
    const payload = {
      environment: approveOpts.environment,
      scope: approveOpts.scope,
      scope_id: requiresScopeId ? approveOpts.scope_id.trim() : null,
    }
    try {
      await api(`/api/updates/${id}/approve`, { method: 'POST', body: JSON.stringify(payload) })
      setApproveId(null)
      setWatchedUpdateIds(ids => ids.includes(id) ? ids : [...ids, id])
      setFilter('all')
      await load(false, 'all')
    }
    catch (error: unknown) { setError(getErrorMessage(error)) }
    finally { setBusy(null) }
  }

  async function reject(id: number) {
    setBusy(id)
    try { await api(`/api/updates/${id}/reject`, { method: 'POST' }); load() }
    catch (e: unknown) { setError(getErrorMessage(e)) }
    finally { setBusy(null) }
  }

  async function promote(id: number, target: 'staging' | 'production' = 'production') {
    setBusy(id)
    setError(null)
    setNotice(null)
    try {
      const result = await api(`/api/updates/${id}/promote`, {
        method: 'POST',
        body: JSON.stringify({ target_environment: target }),
      })
      setFilter(target === 'staging' ? 'approved' : 'pending')
      setNotice(result.existing
        ? `${target === 'staging' ? 'Staging' : 'Prod-klar'} opdatering findes allerede som #${result.new_id}`
        : `${target === 'staging' ? 'Staging' : 'Prod-klar'} opdatering oprettet som #${result.new_id}`
      )
      await load(false, target === 'staging' ? 'approved' : 'pending')
    }
    catch (error: unknown) { setError(getErrorMessage(error)) }
    finally { setBusy(null) }
  }

  async function forceRollback(id: number) {
    if (!confirm('Er du sikker på at du vil rulle denne opdatering tilbage?')) return
    setBusy(id)
    try { await api(`/api/updates/${id}/force-rollback`, { method: 'POST' }); load() }
    catch (error: unknown) { setError(getErrorMessage(error)) }
    finally { setBusy(null) }
  }

  async function bindArtifact(id: number, artifactId: string) {
    setBusy(id)
    setError(null)
    try {
      await api(`/api/updates/${id}/bind-artifact`, {
        method: 'POST',
        body: JSON.stringify({ artifact_id: artifactId }),
      })
      setFilter('pending')
      setNotice(`Artifact ${artifactId} er bundet til update #${id}. Den ligger nu i Afventer til godkendelse.`)
      await load(false, 'pending')
    } catch (e: unknown) {
      setError(`Kunne ikke binde artifact (${getErrorMessage(e)})`)
    } finally {
      setBusy(null)
    }
  }

  async function pollUpdateJob(jobId: string, reloadFilter?: Filter) {
    for (let i = 0; i < 360; i++) {
      const status = await api(`/api/updates/jobs/${jobId}`) as UpdateJobStatus
      setUpdateJobs(jobs => ({ ...jobs, [jobId]: status }))
      if (!status.running) {
        if (status.status === 'done') {
          setNotice(status.message || 'Job færdigt')
          await load(false, reloadFilter)
        } else {
          setError(status.error || status.message || 'Update job fejlede')
        }
        return status
      }
      await new Promise(resolve => setTimeout(resolve, 2000))
    }
    throw new Error('Job timeout')
  }

  async function buildOsBundle(id: number) {
    if (!confirm('Byg OS artifact via Headend Mac-builder og bind det til denne update?')) return
    setBusy(id)
    setError(null)
    setNotice(null)
    try {
      const started = await api(`/api/updates/${id}/os-bundle/build-bind-job`, {
        method: 'POST',
        body: JSON.stringify({
          builder_mode: 'auto',
          architecture: 'arm64',
          image: 'ubuntu:24.04',
        }),
      })
      setUpdateJobs(jobs => ({ ...jobs, [started.job_id]: started.status }))
      setNotice(`OS artifact job startet: ${started.job_id}`)
      await pollUpdateJob(started.job_id, 'pending')
      setFilter('pending')
    } catch (e: unknown) {
      setError(`Kunne ikke bygge OS artifact (${getErrorMessage(e)})`)
    } finally {
      setBusy(null)
    }
  }

  async function refreshHeadendDeployStatus(id: number) {
    const status = await api(`/api/updates/${id}/headend-deploy/status`)
    setHeadendDeployStatus(s => ({ ...s, [id]: status }))
    return status as HeadendDeployStatus
  }

  async function headendDeploy(id: number) {
    const update = updates.find(u => u.id === id)
    const actionLabel = update?.environment === 'production'
      ? 'Aktivér den godkendte Headend-opdatering i production? Der køres postflight-validering uden ny brew upgrade på samme Headend.'
      : 'Installer den godkendte Headend-opdatering i test/lab? Relevante services kan være kortvarigt utilgængelige.'
    if (!confirm(actionLabel)) return
    setBusy(id)
    setError(null)
    try {
      const started = await api(`/api/updates/${id}/headend-deploy`, { method: 'POST' })
      setHeadendDeployStatus(s => ({ ...s, [id]: started.status }))
      for (let i = 0; i < 180; i++) {
        await new Promise(resolve => setTimeout(resolve, 2000))
        const status = await refreshHeadendDeployStatus(id)
        if (!status.running) break
      }
      await load()
    } catch (e: unknown) {
      setError(`Headend-installation fejlede (${getErrorMessage(e)})`)
    } finally {
      setBusy(null)
    }
  }

  async function catalogCurrentRelease() {
    setRefreshing(true)
    setError(null)
    try {
      await api('/api/updates/artifacts/catalog-from-git-tag', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      })
      await load()
    } catch (e: unknown) {
      setError(`Kunne ikke registrere signeret release-tag (${getErrorMessage(e)})`)
    } finally {
      setRefreshing(false)
    }
  }

  async function catalogOsBundle(payload: Record<string, unknown>) {
    setRefreshing(true)
    setError(null)
    try {
      const commandsJson = String(payload.commands_json || '[]')
      const commands = JSON.parse(commandsJson)
      await api('/api/updates/artifacts/catalog-os-bundle', {
        method: 'POST',
        body: JSON.stringify({
          storage_path: payload.storage_path,
          version: payload.version,
          commands,
        }),
      })
      await load()
    } catch (e: unknown) {
      setError(`Kunne ikke registrere OS artifact (${getErrorMessage(e)})`)
    } finally {
      setRefreshing(false)
    }
  }

  async function importLabCatalog(payload: Record<string, unknown>) {
    setRefreshing(true)
    setError(null)
    setNotice(null)
    try {
      const result = await api('/api/updates/os-catalog/import-apt-list', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      const summary = result.summary || {}
      setFilter('blocked')
      setNotice(`Lab-katalog importeret: ${summary.os_security || 0} security og ${summary.os_updates || 0} funktionelle pakker. Plan: ${result.plan_path}`)
      await load(false, 'blocked')
    } catch (e: unknown) {
      setError(`Kunne ikke importere lab-katalog (${getErrorMessage(e)})`)
    } finally {
      setRefreshing(false)
    }
  }

  async function refreshCatalogFromBuilder(payload: Record<string, unknown>) {
    if (!confirm('Generér OS-katalog fra CMDB via Mac Docker-builder? Det kan tage nogle minutter.')) return
    setRefreshing(true)
    setError(null)
    setNotice(null)
    try {
      const started = await api('/api/updates/os-catalog/refresh-from-builder-job', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      setUpdateJobs(jobs => ({ ...jobs, [started.job_id]: started.status }))
      setNotice(`Mac-builder katalogjob startet: ${started.job_id}`)
      await pollUpdateJob(started.job_id, 'blocked')
      setFilter('blocked')
    } catch (e: unknown) {
      setError(`Kunne ikke refreshe OS-katalog fra Mac-builder (${getErrorMessage(e)})`)
    } finally {
      setRefreshing(false)
    }
  }

  const pending = updates.filter(u => u.status === 'pending').length
  const autoPolling =
    watchedUpdateIds.length > 0 ||
    updates.some(u => u.status === 'approved') ||
    Object.values(flowStatuses).some(isActiveFlow)
  const activeUpdates = updates.filter(u => {
    const flow = flowStatuses[u.id]
    const recentlyApproved = Boolean(u.approved_at) && Date.now() - new Date(u.approved_at as string).getTime() < 6 * 60 * 60 * 1000
    const targetStarted = flow?.targets.some(target => target.status !== 'pending')
    return u.status === 'approved' && (watchedUpdateIds.includes(u.id) || recentlyApproved || targetStarted)
  })

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="mb-8 flex flex-col gap-3 sm:flex-row sm:items-center">
        <Link to="/" className="p-2 hover:bg-gray-100 rounded-lg transition-colors">
          <ArrowLeft className="w-4 h-4 text-gray-500" />
        </Link>
        <div className="flex-1">
          <h1 className="text-xl font-semibold text-gray-900 flex items-center gap-2">
            <Package className="w-5 h-5 text-gray-400" />
            Opdateringer
            {pending > 0 && (
              <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full font-medium">
                {pending} afventer
              </span>
            )}
          </h1>
          <p className="text-sm text-gray-400 mt-0.5">Godkend eller afvis software-opdateringer til edge-enheder</p>
        </div>
        <div className="flex flex-wrap items-center gap-3 sm:justify-end">
          {lastRefresh && (
            <span className="text-xs text-gray-300 flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {lastRefresh.toLocaleTimeString('da-DK', { hour: '2-digit', minute: '2-digit' })}
            </span>
          )}
          {autoPolling && (
            <span className="text-xs text-sky-600 flex items-center gap-1">
              <RefreshCw className="w-3 h-3 animate-spin" />
              Auto-opdaterer flow
            </span>
          )}
          <button onClick={() => load(true)} disabled={refreshing}
            title="Hent seneste opdateringer, artifacts og flow-status fra Headend."
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-gray-500 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50">
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
            Opdatér
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 bg-red-50 border border-red-100 text-red-600 text-sm px-4 py-3 rounded-lg mb-4">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" /> {error}
        </div>
      )}
      {notice && (
        <div className="flex items-center gap-2 bg-emerald-50 border border-emerald-100 text-emerald-700 text-sm px-4 py-3 rounded-lg mb-4">
          <CheckCircle className="w-4 h-4 flex-shrink-0" /> {notice}
        </div>
      )}

      {activeUpdates.length > 0 && (
        <div className="sticky top-3 z-30 mb-4 border border-sky-200 bg-white shadow-lg rounded-lg px-4 py-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-gray-900">
            <RefreshCw className="w-4 h-4 text-sky-600 animate-spin" />
            Aktivt opdateringsflow
          </div>
          <div className="mt-2 space-y-2">
            {activeUpdates.map(update => {
              const flow = flowStatuses[update.id]
              const headendScoped = isHeadendScoped(update)
              const headendSupported = canDeployOnHeadend(update)
              const statusLabel = headendScoped
                ? (headendSupported ? 'Klar til Headend-installation' : 'Headend-installer mangler for denne type')
                : (flow?.stage?.label || 'Henter Edge flow-status...')
              return (
                <div key={update.id} className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between text-xs">
                  <div className="font-medium text-gray-800">
                    #{update.id} {TYPE_LABELS[update.update_type] ?? update.update_type}
                    <span className="ml-2 font-mono text-gray-400">{shortHash(update.version)}</span>
                  </div>
                  <div className={`flex items-center gap-2 ${headendScoped && !headendSupported ? 'text-amber-700' : 'text-sky-700'}`}>
                    <span className={`w-2 h-2 rounded-full ${headendScoped && !headendSupported ? 'bg-amber-500' : 'bg-sky-500'}`} />
                    {statusLabel}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      <div className="bg-sky-50 border border-sky-100 rounded-xl px-4 py-3 mb-4">
        <div className="text-sm font-medium text-sky-900">Headend-styret pull-flow</div>
        <p className="text-xs text-sky-700 mt-1 leading-5">
          Edge rapporterer CMDB-inventory og tilgængelige patches til Headend. Headend genererer signerede change tickets og stiller godkendte artifacts klar. Edge henter selv fra Headend ved næste poll; normal drift kræver ikke direkte internet/GitHub fra Edge, og SSH-tunnel bruges kun til manuel fejlsøgning.
        </p>
      </div>

      <div className="mb-4 min-w-0 overflow-x-auto">
        <div className="flex w-max gap-1">
          {FILTERS.map(f => (
          <button key={f.key} onClick={() => setFilter(f.key)}
            title={`Vis opdateringer med status: ${f.label}`}
            className={`min-h-11 whitespace-nowrap px-3 py-1.5 text-xs rounded-lg transition-colors ${
              filter === f.key ? 'bg-gray-900 text-white' : 'text-gray-500 hover:bg-gray-100'
            }`}>
            {f.label}
          </button>
          ))}
        </div>
      </div>

      <UpdateJobsPanel jobs={updateJobs} />

      <DeviceUpdateMatrix matrix={matrix} />

      <LabCatalogImport
        onImport={importLabCatalog}
        onRefreshBuilder={refreshCatalogFromBuilder}
        busy={refreshing}
      />

      <ArtifactCatalog
        artifacts={artifacts}
        onCatalogCurrent={catalogCurrentRelease}
        onCatalogOsBundle={catalogOsBundle}
        busy={refreshing}
      />

      {approveId !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-gray-950/45 p-4" role="dialog" aria-modal="true" aria-labelledby="approve-update-title">
        <div className="w-full max-w-xl max-h-[90vh] overflow-y-auto bg-white rounded-lg border border-gray-200 p-5 shadow-2xl">
          <h3 id="approve-update-title" className="text-base font-semibold text-gray-900">Godkend opdatering #{approveId}</h3>
          {approveUpdate && (
            <div className="mt-1 mb-3 text-xs text-gray-600">
              <div>{TYPE_LABELS[approveUpdate.update_type] ?? approveUpdate.update_type} · {approveUpdate.version.startsWith('v') ? approveUpdate.version : `commit ${shortHash(approveUpdate.version)}`}</div>
              <div className="font-mono mt-0.5">Mål: {approveUpdate.scope}{approveUpdate.scope_id ? ` / ${approveUpdate.scope_id}` : ''} · Miljø: {approveUpdate.environment || 'ikke angivet'}</div>
            </div>
          )}
          <div className="grid grid-cols-2 gap-3 mb-3">
            <div>
              <label className="text-xs text-gray-500 block mb-1" title="Vælg test før produktion, medmindre en dokumenteret undtagelse er godkendt.">Miljø</label>
              <select value={approveOpts.environment}
                onChange={(e: ChangeEvent<HTMLSelectElement>) => setApproveOpts(o => ({...o, environment: e.target.value as ApproveOptions['environment']}))}
                className="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-xs">
                <option value="test">Test (deploy til testmiljø først)</option>
                <option value="production">Produktion</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-500 block mb-1" title="Afgræns hvilke enheder den godkendte opdatering må gælde for.">Scope</label>
              <select value={approveOpts.scope}
                onChange={(e: ChangeEvent<HTMLSelectElement>) => setApproveOpts(o => ({...o, scope: e.target.value as ApproveOptions['scope'], scope_id: ''}))}
                className="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-xs">
                <option value="global">Alle enheder</option>
                <option value="device">Specifik enhed</option>
                <option value="customer">Kunde</option>
                <option value="site">Site</option>
              </select>
            </div>
            {approveOpts.scope === 'device' && (
              <div>
                <label className="text-xs text-gray-500 block mb-1" title="Vælg kun den konkrete R&D- eller produktions-Edge, som skal modtage ændringen.">Device ID</label>
                <input value={approveOpts.scope_id}
                  onChange={e => setApproveOpts(o => ({...o, scope_id: e.target.value}))}
                  placeholder="fx TL-C87FF9587CA0"
                  className="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-xs font-mono" />
              </div>
            )}
            {approveOpts.scope === 'customer' && (
              <div>
                <label className="text-xs text-gray-500 block mb-1">Kunde</label>
                <select value={approveOpts.scope_id}
                  onChange={e => setApproveOpts(o => ({...o, scope_id: e.target.value}))}
                  className="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-xs">
                  <option value="">Vælg kunde...</option>
                  {customers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </div>
            )}
            {approveOpts.scope === 'site' && (
              <div>
                <label className="text-xs text-gray-500 block mb-1">Site</label>
                <select value={approveOpts.scope_id}
                  onChange={e => setApproveOpts(o => ({...o, scope_id: e.target.value}))}
                  className="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-xs">
                  <option value="">Vælg site...</option>
                  {sites.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </div>
            )}
          </div>
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <button onClick={() => approve(approveId)}
              disabled={busy === approveId}
              title="Godkend med det viste miljø og scope. Næste flowtrin starter først efter policy og Edge-poll."
              className="px-4 py-2 bg-green-600 text-white text-sm rounded-lg hover:bg-green-700 disabled:opacity-50">
              {busy === approveId ? 'Godkender...' : 'Bekræft godkendelse'}
            </button>
            <button onClick={() => setApproveId(null)}
              disabled={busy === approveId}
              title="Luk dialogen uden at ændre opdateringens status."
              className="px-4 py-2 bg-gray-100 text-gray-700 text-sm rounded-lg disabled:opacity-50">
              Annuller
            </button>
          </div>
        </div>
        </div>
      )}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {loading ? (
          <div className="py-12 text-center">
            <Package className="w-6 h-6 text-gray-200 mx-auto mb-2 animate-pulse" />
            <p className="text-sm text-gray-400">Henter opdateringer…</p>
          </div>
        ) : updates.length === 0 ? (
          <div className="py-12 text-center">
            <Shield className="w-8 h-8 text-gray-200 mx-auto mb-3" />
            <p className="text-sm font-medium text-gray-500">Ingen opdateringer</p>
            <p className="text-xs text-gray-300 mt-1">
              {filter === 'pending' ? 'Alle opdateringer er behandlet' : `Ingen opdateringer med status "${filter}"`}
            </p>
          </div>
        ) : (
          updates.map(u => (
            <UpdateRow key={u.id} u={u}
              onApprove={id => {
                setApproveId(id)
                setApproveOpts({
                  environment: (u.environment === 'test' || u.environment === 'production') ? u.environment : 'production',
                  scope: (['global', 'device', 'customer', 'site'].includes(u.scope) ? u.scope : 'device') as ApproveOptions['scope'],
                  scope_id: u.scope_id || ''
                })
              }}
              onReject={reject}
              onPromote={(id, target) => promote(id, target)}
              onRollback={id => forceRollback(id)}
              onHeadendDeploy={headendDeploy}
              onBindArtifact={bindArtifact}
              onBuildOsBundle={buildOsBundle}
              onRequestFlow={requestFlowStatus}
              busy={busy}
              deployStatus={headendDeployStatus[u.id]}
              flowStatus={flowStatuses[u.id]}
            />
          ))
        )}
      </div>
    </div>
  )
}
