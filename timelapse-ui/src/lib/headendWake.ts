// Read/write system.headend_wake as a tri-state ('' = inherit) in a config
// overrides object (Peter 2026-10-10). The customer/site PUT merges only at
// the top level — the `system` section is replaced as a whole — so "inherit"
// must delete the key rather than store null (null would mask the layer above).
type Overrides = Record<string, unknown> | undefined | null

function systemOf(overrides: Overrides): Record<string, unknown> {
  const system = (overrides ?? {}).system
  return system && typeof system === 'object' ? { ...(system as Record<string, unknown>) } : {}
}

export function wakeTriFrom(overrides: Overrides): string {
  const v = systemOf(overrides).headend_wake
  return v === true || v === 'true' ? 'true' : v === false || v === 'false' ? 'false' : ''
}

export function withWake(overrides: Overrides, tri: string): Record<string, unknown> {
  const system = systemOf(overrides)
  if (tri === '') delete system.headend_wake
  else system.headend_wake = tri === 'true'
  return { ...(overrides ?? {}), system }
}
