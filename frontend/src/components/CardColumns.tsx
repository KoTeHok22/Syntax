import type { ReactNode } from 'react'

interface CardColumnsProps<T> {
  items: T[]
  columns: 1 | 2 | 3
  getKey: (item: T) => string | number
  renderItem: (item: T) => ReactNode
}

const COLUMN_CLASS: Record<1 | 2 | 3, string> = {
  1: 'grid-cols-1',
  2: 'md:grid-cols-2',
  3: 'md:grid-cols-2 lg:grid-cols-3',
}

export function CardColumns<T>({ items, columns, getKey, renderItem }: CardColumnsProps<T>) {
  return (
    <div className={`grid grid-cols-1 items-stretch gap-5 ${COLUMN_CLASS[columns]}`}>
      {items.map((item) => (
        <div className="flex min-w-0 [&>*]:w-full" key={getKey(item)}>
          {renderItem(item)}
        </div>
      ))}
    </div>
  )
}
