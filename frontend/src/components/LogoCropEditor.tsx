import { useRef } from 'react'
import { LogoAvatar } from './LogoAvatar'
import type { LogoCrop } from '../lib/logoCrop'

interface LogoCropEditorProps {
  src: string
  crop: LogoCrop
  onChange: (crop: LogoCrop) => void
}

const MIN_ZOOM = 1
const MAX_ZOOM = 3
const OFFSET_LIMIT = 50
const PREVIEW_SIZE = 160

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value))
}

export function LogoCropEditor({ src, crop, onChange }: LogoCropEditorProps) {
  const dragRef = useRef<{ x: number; y: number; offsetX: number; offsetY: number } | null>(null)

  const startDrag = (event: React.PointerEvent<HTMLDivElement>) => {
    event.currentTarget.setPointerCapture(event.pointerId)
    dragRef.current = { x: event.clientX, y: event.clientY, offsetX: crop.offsetX, offsetY: crop.offsetY }
  }

  const moveDrag = (event: React.PointerEvent<HTMLDivElement>) => {
    const origin = dragRef.current
    if (origin === null) return
    const scale = PREVIEW_SIZE / 100
    onChange({
      ...crop,
      offsetX: clamp(origin.offsetX + (event.clientX - origin.x) / scale, -OFFSET_LIMIT, OFFSET_LIMIT),
      offsetY: clamp(origin.offsetY + (event.clientY - origin.y) / scale, -OFFSET_LIMIT, OFFSET_LIMIT),
    })
  }

  const endDrag = () => {
    dragRef.current = null
  }

  return (
    <div className="flex flex-wrap items-center gap-5">
      <div
        aria-label="Перетащите, чтобы выбрать область логотипа"
        className="cursor-grab touch-none rounded-full shadow-inset-sm active:cursor-grabbing"
        onPointerDown={startDrag}
        onPointerMove={moveDrag}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        role="application"
      >
        <LogoAvatar alt="Предпросмотр логотипа" crop={crop} size={PREVIEW_SIZE} src={src} />
      </div>
      <div className="flex min-w-[220px] flex-1 flex-col gap-3">
        <label className="flex flex-col gap-1.5">
          <span className="flex items-center justify-between font-mono text-[11px] uppercase tracking-wider text-ink-secondary">
            Масштаб
            <span className="font-bold text-ink">{Math.round(crop.zoom * 100)}%</span>
          </span>
          <input
            className="w-full accent-pvn-blue"
            max={MAX_ZOOM}
            min={MIN_ZOOM}
            onChange={(event) => onChange({ ...crop, zoom: Number(event.target.value) })}
            step={0.05}
            type="range"
            value={crop.zoom}
          />
        </label>
        <p className="font-sans text-caption text-ink-secondary">
          Перетащите круг, чтобы выбрать часть логотипа. Этот же кадр показывается в шапке.
        </p>
        <button
          className="btn-ghost w-fit py-2 text-[13px]"
          onClick={() => onChange({ zoom: 1, offsetX: 0, offsetY: 0 })}
          type="button"
        >
          Сбросить кадр
        </button>
      </div>
    </div>
  )
}
