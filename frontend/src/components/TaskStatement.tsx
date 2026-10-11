import type { ReactNode } from 'react'

type Block =
  | { kind: 'text'; value: string }
  | { kind: 'code'; value: string }

const FENCE = /```(?:[a-zA-Z0-9_+-]*)\n?([\s\S]*?)```/g

function splitFences(source: string): Block[] {
  const blocks: Block[] = []
  let cursor = 0
  for (const match of source.matchAll(FENCE)) {
    const index = match.index ?? 0
    if (index > cursor) blocks.push({ kind: 'text', value: source.slice(cursor, index) })
    blocks.push({ kind: 'code', value: match[1].replace(/\n+$/, '') })
    cursor = index + match[0].length
  }
  if (cursor < source.length) blocks.push({ kind: 'text', value: source.slice(cursor) })
  return blocks
}

const CODE_LINE = /(=>|===|;\s*$|\bconst\b|\blet\b|\bvar\b|\bfunction\b|\breturn\b|\bdocument\.|\.push\(|\.addEventListener\(|querySelector\(|\bif\s*\()/

const TABLE_DIVIDER = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$/

function parseTableRow(line: string): string[] {
  const trimmed = line.trim().replace(/^\|/, '').replace(/\|$/, '')
  return trimmed.split('|').map((cell) => cell.trim())
}

function isTableStart(lines: string[], index: number): boolean {
  if (index + 1 >= lines.length) return false
  const header = lines[index]
  const divider = lines[index + 1]
  if (!header.includes('|') || !TABLE_DIVIDER.test(divider)) return false
  return parseTableRow(header).length >= 2
}

interface TableCell {
  kind: 'table'
  header: string[]
  rows: string[][]
}

function collectTable(lines: string[], start: number): { block: TableCell; next: number } {
  const header = parseTableRow(lines[start])
  let cursor = start + 2
  const rows: string[][] = []
  while (cursor < lines.length && lines[cursor].includes('|') && lines[cursor].trim() !== '') {
    rows.push(parseTableRow(lines[cursor]))
    cursor += 1
  }
  return { block: { kind: 'table', header, rows }, next: cursor }
}

function groupTables(blocks: Block[], keyPrefix: string): Array<Block | TableCell> {
  const result: Array<Block | TableCell> = []
  blocks.forEach((block) => {
    if (block.kind !== 'text') {
      result.push(block)
      return
    }
    const lines = block.value.split('\n')
    let buffer: string[] = []
    const flush = () => {
      if (buffer.length > 0) result.push({ kind: 'text', value: buffer.join('\n') })
      buffer = []
    }
    let index = 0
    while (index < lines.length) {
      if (isTableStart(lines, index)) {
        flush()
        const { block: table, next } = collectTable(lines, index)
        result.push(table)
        index = next
      } else {
        buffer.push(lines[index])
        index += 1
      }
    }
    flush()
  })
  void keyPrefix
  return result
}

function isCodeLine(line: string): boolean {
  if (/[А-Яа-яЁё]/.test(line)) return false
  return CODE_LINE.test(line)
}

function groupCodeRuns(text: string): Block[] {
  const lines = text.split('\n')
  const blocks: Block[] = []
  let textBuffer: string[] = []
  let codeBuffer: string[] = []
  const flushText = () => {
    if (textBuffer.length > 0) blocks.push({ kind: 'text', value: textBuffer.join('\n') })
    textBuffer = []
  }
  const flushCode = () => {
    if (codeBuffer.length > 0) blocks.push({ kind: 'code', value: codeBuffer.join('\n') })
    codeBuffer = []
  }
  for (const line of lines) {
    if (isCodeLine(line)) {
      flushText()
      codeBuffer.push(line)
    } else {
      flushCode()
      textBuffer.push(line)
    }
  }
  flushCode()
  flushText()
  return blocks
}

function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const parts = text.split(/(`[^`\n]+`)/g)
  return parts.map((part, index) => {
    if (part.startsWith('`') && part.endsWith('`') && part.length > 2) {
      return (
        <code className="rounded-md bg-ink/10 px-1.5 py-0.5 font-mono text-[0.92em] text-ink" key={`${keyPrefix}-${index}`}>
          {part.slice(1, -1)}
        </code>
      )
    }
    return <span key={`${keyPrefix}-${index}`}>{part}</span>
  })
}

function renderParagraphs(text: string, keyPrefix: string): ReactNode[] {
  return text
    .split(/\n{2,}/)
    .map((paragraph) => paragraph.trim())
    .filter((paragraph) => paragraph.length > 0)
    .map((paragraph, index) => (
      <p className="whitespace-pre-line font-sans text-body leading-relaxed text-ink" key={`${keyPrefix}-p-${index}`}>
        {renderInline(paragraph, `${keyPrefix}-p-${index}`)}
      </p>
    ))
}

function renderTable(header: string[], rows: string[][], keyPrefix: string): ReactNode {
  return (
    <div className="overflow-x-auto rounded-xl bg-inset p-1 shadow-inset-sm" key={keyPrefix}>
      <table className="w-full border-collapse font-sans text-[13px]">
        <thead>
          <tr>
            {header.map((cell, index) => (
              <th
                className="border-b border-ink/15 px-3 py-2 text-left font-mono text-[12px] font-bold uppercase tracking-wider text-ink"
                key={`${keyPrefix}-h-${index}`}
              >
                {renderInline(cell, `${keyPrefix}-h-${index}`)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr className="border-b border-ink/10 last:border-b-0" key={`${keyPrefix}-r-${rowIndex}`}>
              {header.map((_, cellIndex) => (
                <td className="px-3 py-2 align-top text-ink" key={`${keyPrefix}-r-${rowIndex}-c-${cellIndex}`}>
                  {renderInline(row[cellIndex] ?? '', `${keyPrefix}-r-${rowIndex}-c-${cellIndex}`)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function codeBlockAsTable(value: string): { header: string[]; rows: string[][] } | null {
  const lines = value.split('\n').filter((line) => line.trim() !== '')
  if (lines.length < 2 || !isTableStart(lines, 0)) return null
  return collectTable(lines, 0).block
}

interface TaskStatementProps {
  statement: string
}

export function TaskStatement({ statement }: TaskStatementProps) {
  const blocks = splitFences(statement).flatMap((block) =>
    block.kind === 'text' ? groupTables(groupCodeRuns(block.value), 'table') : [block],
  )
  return (
    <div className="flex flex-col gap-4">
      {blocks.map((block, index) => {
        if (block.kind === 'code') {
          const table = codeBlockAsTable(block.value)
          if (table !== null) return renderTable(table.header, table.rows, `fence-table-${index}`)
          return (
            <pre className="code-block" key={`code-${index}`}>
              <code>{block.value}</code>
            </pre>
          )
        }
        if (block.kind === 'table') return renderTable(block.header, block.rows, `table-${index}`)
        return (
          <div className="flex flex-col gap-3" key={`text-${index}`}>
            {renderParagraphs(block.value, `text-${index}`)}
          </div>
        )
      })}
    </div>
  )
}
