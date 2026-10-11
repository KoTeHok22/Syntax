const WORK_FORMAT_LABELS: Record<string, string> = {
  remote: 'Удалённо',
  office: 'Офис',
  hybrid: 'Гибрид',
}

export function workFormatLabel(value: string | null | undefined): string {
  if (!value) return ''
  return WORK_FORMAT_LABELS[value] ?? ''
}
