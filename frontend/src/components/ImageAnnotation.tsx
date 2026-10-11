import { useCallback, useEffect, useRef, useState } from 'react'
import type { TouchEvent } from 'react'

export interface AnnotationRect {
  x: number
  y: number
  w: number
  h: number
}

interface ImageAnnotationProps {
  src: string
  value: AnnotationRect | null
  onChange: (rect: AnnotationRect | null) => void
}

function clamp(value: number): number {
  return Math.max(0, Math.min(1, value))
}

export function ImageAnnotation({ src, value, onChange }: ImageAnnotationProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(null)
  const [draft, setDraft] = useState<AnnotationRect | null>(null)

  const relativePoint = useCallback((clientX: number, clientY: number) => {
    const container = containerRef.current
    if (container === null) return { x: 0, y: 0 }
    const rect = container.getBoundingClientRect()
    return {
      x: clamp((clientX - rect.left) / rect.width),
      y: clamp((clientY - rect.top) / rect.height),
    }
  }, [])

  const finish = useCallback(() => {
    setDragStart(null)
    setDraft((current) => {
      if (current !== null && current.w > 0.02 && current.h > 0.02) onChange(current)
      else if (current !== null) onChange(null)
      return null
    })
  }, [onChange])

  useEffect(() => {
    if (dragStart === null) return
    const onMove = (event: MouseEvent) => {
      const point = relativePoint(event.clientX, event.clientY)
      setDraft({
        x: Math.min(dragStart.x, point.x),
        y: Math.min(dragStart.y, point.y),
        w: Math.abs(point.x - dragStart.x),
        h: Math.abs(point.y - dragStart.y),
      })
    }
    const onUp = () => finish()
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    return () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
  }, [dragStart, relativePoint, finish])

  const onTouchStart = (event: TouchEvent<HTMLDivElement>) => {
    const touch = event.touches[0]
    if (touch === undefined) return
    const point = relativePoint(touch.clientX, touch.clientY)
    setDragStart(point)
    setDraft({ x: point.x, y: point.y, w: 0, h: 0 })
  }

  const onTouchMove = (event: TouchEvent<HTMLDivElement>) => {
    if (dragStart === null) return
    const touch = event.touches[0]
    if (touch === undefined) return
    const point = relativePoint(touch.clientX, touch.clientY)
    setDraft({
      x: Math.min(dragStart.x, point.x),
      y: Math.min(dragStart.y, point.y),
      w: Math.abs(point.x - dragStart.x),
      h: Math.abs(point.y - dragStart.y),
    })
  }

  const active = draft ?? value

  return (
    <div className="flex flex-col gap-2">
      <div
        className="relative w-full cursor-crosshair select-none overflow-hidden rounded-xl bg-sunken shadow-inset-sm"
        onMouseDown={(event) => {
          const point = relativePoint(event.clientX, event.clientY)
          setDragStart(point)
          setDraft({ x: point.x, y: point.y, w: 0, h: 0 })
        }}
        onTouchEnd={(event) => {
          event.preventDefault()
          finish()
        }}
        onTouchMove={onTouchMove}
        onTouchStart={onTouchStart}
        ref={containerRef}
      >
        <img alt="РњР°РєРµС‚ РёРЅС‚РµСЂС„РµР№СЃР° СЃ РѕС€РёР±РєРѕР№ РґРёР·Р°Р№РЅР°" className="pointer-events-none block w-full" draggable={false} src={src} />
        {active !== null ? (
          <span
            className="pointer-events-none absolute border-2 border-pvn-red bg-pvn-red/20"
            style={{
              left: `${active.x * 100}%`,
              top: `${active.y * 100}%`,
              width: `${active.w * 100}%`,
              height: `${active.h * 100}%`,
            }}
          />
        ) : null}
      </div>
      <span className="font-sans text-[12px] text-ink-secondary">
        {value !== null ? 'РћР±Р»Р°СЃС‚СЊ РІС‹РґРµР»РµРЅР°. РњРѕР¶РЅРѕ РїРµСЂРµС‚Р°С‰РёС‚СЊ РїСЂСЏРјРѕСѓРіРѕР»СЊРЅРёРє Р·Р°РЅРѕРІРѕ.' : 'РћР±РІРµРґРёС‚Рµ РїСЂРѕР±Р»РµРјРЅС‹Р№ СЌР»РµРјРµРЅС‚ РјС‹С€РєРѕР№ РёР»Рё РїР°Р»СЊС†РµРј.'}
      </span>
    </div>
  )
}
