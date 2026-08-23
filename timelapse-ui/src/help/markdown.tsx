import { Fragment, type ReactNode } from 'react'
import { slugify } from './headings'

/**
 * Minimal markdown-renderer til /help-siden.
 *
 * Skræddersyet til projektets egne kuraterede dokumenter (menuguides, FAQ,
 * manualer) — ikke en generel CommonMark-implementation. Understøtter:
 * overskrifter (#..####), afsnit, **fed**, *kursiv*, `inline kode`,
 * ``` kodeblokke, - / * / 1. lister (ét indrykningsniveau), | tabeller |,
 * > citater, --- skillelinjer og [links](url).
 *
 * Kun projektets egne, reviewede Markdown-filer må renderes her — der er
 * bevidst ingen HTML-passthrough, så indholdet kan ikke injicere markup.
 */

// ---------- inline-formatering ----------

function renderInline(text: string, keyBase: string): ReactNode[] {
  // Split på inline tokens i prioriteret rækkefølge: link, kode, fed, kursiv
  const pattern = /(\[([^\]]+)\]\(([^)]+)\))|(`([^`]+)`)|(\*\*([^*]+)\*\*)|(\*([^*]+)\*)/g
  const out: ReactNode[] = []
  let last = 0
  let m: RegExpExecArray | null
  let i = 0
  while ((m = pattern.exec(text)) !== null) {
    if (m.index > last) out.push(text.slice(last, m.index))
    const key = `${keyBase}-${i++}`
    if (m[1]) {
      const href = m[3]
      const external = /^https?:\/\//.test(href)
      out.push(
        <a
          key={key}
          href={href}
          {...(external ? { target: '_blank', rel: 'noreferrer' } : {})}
          className="text-sky-700 hover:underline break-all"
        >
          {m[2]}
        </a>,
      )
    } else if (m[4]) {
      out.push(
        <code key={key} className="rounded bg-gray-100 px-1 py-0.5 text-[0.85em] font-mono text-gray-800 break-all">
          {m[5]}
        </code>,
      )
    } else if (m[6]) {
      out.push(<strong key={key} className="font-semibold text-gray-900">{m[7]}</strong>)
    } else if (m[8]) {
      out.push(<em key={key}>{m[9]}</em>)
    }
    last = m.index + m[0].length
  }
  if (last < text.length) out.push(text.slice(last))
  return out
}

// ---------- blok-parser ----------

interface ListItem {
  indent: number
  ordered: boolean
  text: string
}

function parseListItem(line: string): ListItem | null {
  const m = /^(\s*)(?:[-*]|(\d+)\.)\s+(.+)$/.exec(line)
  if (!m) return null
  return { indent: m[1].length, ordered: m[2] !== undefined, text: m[3] }
}

function isTableRow(line: string): boolean {
  const t = line.trim()
  return t.startsWith('|') && t.endsWith('|') && t.length > 1
}

function isTableSeparator(line: string): boolean {
  return /^\|?[\s:|-]+\|?$/.test(line.trim()) && line.includes('-')
}

function splitTableRow(line: string): string[] {
  return line.trim().replace(/^\||\|$/g, '').split('|').map((c) => c.trim())
}

export function Markdown({ source }: { source: string }) {
  const lines = source.split('\n')
  const blocks: ReactNode[] = []
  let i = 0
  let key = 0

  while (i < lines.length) {
    const line = lines[i]

    // Kodeblok
    if (line.trimStart().startsWith('```')) {
      const buf: string[] = []
      i++
      while (i < lines.length && !lines[i].trimStart().startsWith('```')) {
        buf.push(lines[i])
        i++
      }
      i++ // skip lukkende fence
      blocks.push(
        <pre key={key++} className="my-3 overflow-x-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-100">
          <code>{buf.join('\n')}</code>
        </pre>,
      )
      continue
    }

    // Overskrift
    const h = /^(#{1,4})\s+(.+)$/.exec(line)
    if (h) {
      const level = h[1].length
      const text = h[2].trim()
      const id = slugify(text.replace(/\*\*/g, '').replace(/`/g, ''))
      const cls =
        level === 1
          ? 'mt-6 mb-3 text-2xl font-bold text-gray-900 first:mt-0'
          : level === 2
            ? 'mt-6 mb-2 text-lg font-semibold text-gray-900 border-b border-gray-200 pb-1'
            : level === 3
              ? 'mt-4 mb-1.5 text-base font-semibold text-gray-800'
              : 'mt-3 mb-1 text-sm font-semibold text-gray-700'
      blocks.push(
        <HeadingTag key={key++} level={level} id={id} className={cls}>
          {renderInline(text, `h${key}`)}
        </HeadingTag>,
      )
      i++
      continue
    }

    // Skillelinje
    if (/^\s*---+\s*$/.test(line)) {
      blocks.push(<hr key={key++} className="my-4 border-gray-200" />)
      i++
      continue
    }

    // Tabel
    if (isTableRow(line) && i + 1 < lines.length && isTableSeparator(lines[i + 1])) {
      const header = splitTableRow(line)
      i += 2
      const rows: string[][] = []
      while (i < lines.length && isTableRow(lines[i])) {
        rows.push(splitTableRow(lines[i]))
        i++
      }
      blocks.push(
        <div key={key++} className="my-3 overflow-x-auto">
          <table className="min-w-full border-collapse text-sm">
            <thead>
              <tr>
                {header.map((c, ci) => (
                  <th key={ci} className="border-b-2 border-gray-300 px-3 py-1.5 text-left font-semibold text-gray-800">
                    {renderInline(c, `th${key}-${ci}`)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, ri) => (
                <tr key={ri} className="even:bg-gray-50">
                  {row.map((c, ci) => (
                    <td key={ci} className="border-b border-gray-100 px-3 py-1.5 align-top text-gray-700">
                      {renderInline(c, `td${key}-${ri}-${ci}`)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      )
      continue
    }

    // Liste
    const li = parseListItem(line)
    if (li) {
      const items: ListItem[] = []
      while (i < lines.length) {
        const it = parseListItem(lines[i])
        if (!it) break
        items.push(it)
        i++
      }
      const ordered = items[0].ordered
      const Tag = ordered ? 'ol' : 'ul'
      blocks.push(
        <Tag
          key={key++}
          className={`my-2 space-y-1 text-sm text-gray-700 ${ordered ? 'list-decimal' : 'list-disc'} pl-6`}
        >
          {items.map((it, idx) => (
            <li key={idx} style={it.indent >= 2 ? { marginLeft: '1.25rem' } : undefined}>
              {renderInline(it.text, `li${key}-${idx}`)}
            </li>
          ))}
        </Tag>,
      )
      continue
    }

    // Citat
    if (line.trimStart().startsWith('>')) {
      const buf: string[] = []
      while (i < lines.length && lines[i].trimStart().startsWith('>')) {
        buf.push(lines[i].trimStart().replace(/^>\s?/, ''))
        i++
      }
      blocks.push(
        <blockquote key={key++} className="my-3 border-l-4 border-sky-200 bg-sky-50 px-4 py-2 text-sm text-sky-950">
          {renderInline(buf.join(' '), `bq${key}`)}
        </blockquote>,
      )
      continue
    }

    // Tom linje
    if (line.trim() === '') {
      i++
      continue
    }

    // Afsnit: saml sammenhængende almindelige linjer
    const buf: string[] = [line.trim()]
    i++
    while (
      i < lines.length &&
      lines[i].trim() !== '' &&
      !/^(#{1,4})\s/.test(lines[i]) &&
      !lines[i].trimStart().startsWith('```') &&
      !lines[i].trimStart().startsWith('>') &&
      !parseListItem(lines[i]) &&
      !isTableRow(lines[i]) &&
      !/^\s*---+\s*$/.test(lines[i])
    ) {
      buf.push(lines[i].trim())
      i++
    }
    blocks.push(
      <p key={key++} className="my-2 text-sm leading-relaxed text-gray-700">
        {renderInline(buf.join(' '), `p${key}`)}
      </p>,
    )
  }

  return <>{blocks.map((b, idx) => <Fragment key={idx}>{b}</Fragment>)}</>
}

function HeadingTag({
  level,
  id,
  className,
  children,
}: {
  level: number
  id: string
  className: string
  children: ReactNode
}) {
  const Tag = (`h${Math.min(level, 4)}`) as 'h1' | 'h2' | 'h3' | 'h4'
  return (
    <Tag id={id} className={`${className} scroll-mt-4`}>
      {children}
    </Tag>
  )
}
