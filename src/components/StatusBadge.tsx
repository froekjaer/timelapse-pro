interface Props {
  status: 'online' | 'offline' | 'unknown'
  size?: 'sm' | 'md'
}

export function StatusBadge({ status, size = 'md' }: Props) {
  const colors = {
    online:  'bg-emerald-100 text-emerald-800 ring-emerald-300',
    offline: 'bg-red-100 text-red-800 ring-red-300',
    unknown: 'bg-gray-100 text-gray-600 ring-gray-300',
  }
  const dots = {
    online:  'bg-emerald-500',
    offline: 'bg-red-500',
    unknown: 'bg-gray-400',
  }
  const labels = { online: 'Online', offline: 'Offline', unknown: 'Ukendt' }
  const pad = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs'

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full font-medium ring-1 ring-inset ${colors[status]} ${pad}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${dots[status]}`} />
      {labels[status]}
    </span>
  )
}
