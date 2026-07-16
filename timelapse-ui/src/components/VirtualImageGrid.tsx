import { useLayoutEffect, useRef, useState, type ReactNode } from 'react'

interface Props {
  count: number
  renderItem: (index: number) => ReactNode
  minColWidth?: number   // px — styrer antal kolonner (auto-fill, responsivt)
  gap?: number           // px mellem celler
  aspect?: number        // celle bredde/højde (16/9 for aspect-video-kort)
  footerHeight?: number  // fast indhold under billedfladen, fx dato/QA på capture-kort
  overscanRows?: number  // ekstra rækker over/under viewport (blødere scroll)
  className?: string
}

// Afhængighedsfri virtuel grid: renderer KUN de rækker der er synlige (+ overscan),
// så et grid med mange tusinde elementer (fx 21.000 timelapse-frames) ikke vælter
// browseren. Bruger vindues-scroll og måler grid'ets position via getBoundingClientRect,
// så det er robust selv når layoutet ovenfor ændrer højde.
export function VirtualImageGrid({
  count, renderItem, minColWidth = 96, gap = 6, aspect = 16 / 9,
  footerHeight = 0, overscanRows = 4, className,
}: Props) {
  const ref = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(0)
  const [viewTop, setViewTop] = useState(0)   // hvor langt ned i grid'et viewport-toppen er
  const [viewportH, setViewportH] = useState(
    typeof window !== 'undefined' ? window.innerHeight : 800,
  )

  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    let raf = 0
    // Bredde/viewport måles KUN ved mount + resize (ikke ved scroll).
    const measureSize = () => { setWidth(el.clientWidth); setViewportH(window.innerHeight) }
    // Scroll opdaterer KUN viewTop — og throttles til én gang pr. frame (rAF),
    // så vi ikke laver en layout-læsning + re-render pr. scroll-event.
    const measureScroll = () => setViewTop(-el.getBoundingClientRect().top)
    const onScroll = () => { if (!raf) raf = requestAnimationFrame(() => { raf = 0; measureScroll() }) }
    const onResize = () => { measureSize(); measureScroll() }

    measureSize(); measureScroll()
    const ro = new ResizeObserver(measureSize)
    ro.observe(el)
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onResize)
    return () => {
      if (raf) cancelAnimationFrame(raf)
      ro.disconnect()
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('resize', onResize)
    }
  }, [])

  const cols = Math.max(1, Math.floor((width + gap) / (minColWidth + gap)))
  const cellW = cols > 0 ? (width - (cols - 1) * gap) / cols : minColWidth
  const cellH = cellW / aspect + footerHeight
  const rowH = cellH + gap
  const rows = Math.ceil(count / Math.max(1, cols))
  const totalH = rows * rowH

  const firstRow = Math.max(0, Math.floor(viewTop / rowH) - overscanRows)
  const lastRow = Math.min(rows, Math.ceil((viewTop + viewportH) / rowH) + overscanRows)

  const cells: ReactNode[] = []
  if (width > 0 && cellW > 0) {
    const end = Math.min(count, lastRow * cols)
    for (let i = firstRow * cols; i < end; i++) {
      const r = Math.floor(i / cols)
      const c = i % cols
      cells.push(
        <div
          key={i}
          style={{
            position: 'absolute',
            transform: `translate(${c * (cellW + gap)}px, ${r * rowH}px)`,
            width: cellW,
            height: cellH,
          }}
        >
          {renderItem(i)}
        </div>,
      )
    }
  }

  return (
    <div ref={ref} className={className} style={{ position: 'relative', height: totalH || undefined }}>
      {cells}
    </div>
  )
}
