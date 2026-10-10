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

interface TaskStatementProps {
  statement: string
}

export function TaskStatement({ statement }: TaskStatementProps) {
  const blocks = splitFences(statement).flatMap((block) => (block.kind === 'text' ? groupCodeRuns(block.value) : [block]))
  return (
    <div className="flex flex-col gap-4">
      {blocks.map((block, index) =>
        block.kind === 'code' ? (
          <pre className="code-block" key={`code-${index}`}>
            <code>{block.value}</code>
          </pre>
        ) : (
          <div className="flex flex-col gap-3" key={`text-${index}`}>
            {renderParagraphs(block.value, `text-${index}`)}
          </div>
        ),
      )}
    </div>
  )
}
