// Many-to-many customer membership (Peter 2026-10-10): a user can be attached
// to several customers; the role applies to all of them. Only super_admin has
// global access — no customer means no customer data for any other role.
interface CustomerOption { id: string; name: string }

export function CustomerMultiSelect({ customers, value, onChange, role, compact = false }: {
  customers: CustomerOption[]
  value: string[]
  onChange: (ids: string[]) => void
  role: string
  compact?: boolean
}) {
  const toggle = (id: string) =>
    onChange(value.includes(id) ? value.filter(v => v !== id) : [...value, id])
  const text = compact ? 'text-xs' : 'text-sm'
  return (
    <div>
      <div className={`border border-gray-200 rounded-lg px-2 py-1.5 max-h-36 overflow-y-auto space-y-1 ${text}`}>
        {customers.length === 0 && <p className="text-gray-400">Ingen kunder oprettet</p>}
        {customers.map(c => (
          <label key={c.id} className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={value.includes(c.id)} onChange={() => toggle(c.id)}
              className="rounded border-gray-300" />
            <span className="text-gray-700">{c.name}</span>
          </label>
        ))}
      </div>
      <p className="text-xs text-gray-400 mt-1">
        {role === 'super_admin'
          ? 'Superadministrator har altid adgang til alle kunder.'
          : value.length === 0
            ? 'Ingen kunde valgt: brugeren får ingen adgang til kundedata.'
            : `Rollen gælder for ${value.length === 1 ? 'den valgte kunde' : `alle ${value.length} valgte kunder`}.`}
      </p>
    </div>
  )
}
