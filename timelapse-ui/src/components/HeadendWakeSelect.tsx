// Whether an Edge may be woken by the Headend through its SSH tunnel
// (system.headend_wake, config hierarchy global → device → customer → site →
// camera; Peter 2026-10-10). '' = inherit, 'true' / 'false' = override.
export function HeadendWakeSelect({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-1">
        <label className="text-xs text-gray-400">Vækning gennem SSH-tunnel</label>
        <span className="text-xs text-gray-300 cursor-help"
          title="Headend må bede Edgen hente nyt med det samme (fx LAB mode), via en låst nøgle der kun virker gennem SSH-tunnelen og kun kan udløse en sync. Fra = Edgen fjerner nøglen og henter først ved næste normale poll.">ⓘ</span>
      </div>
      <select className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
        value={value} onChange={e => onChange(e.target.value)}>
        <option value="">Arv</option>
        <option value="true">Tilladt</option>
        <option value="false">Ikke tilladt</option>
      </select>
    </div>
  )
}
