import type { LogoCrop } from '../lib/logoCrop'

interface LogoAvatarProps {
  src: string
  crop: LogoCrop
  size: number
  alt: string
}

export function LogoAvatar({ src, crop, size, alt }: LogoAvatarProps) {
  return (
    <span
      className="relative flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-white"
      style={{ width: size, height: size }}
    >
      <img
        alt={alt}
        className="pointer-events-none max-h-none max-w-none select-none"
        draggable={false}
        src={src}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'contain',
          transform: `translate(${crop.offsetX}%, ${crop.offsetY}%) scale(${crop.zoom})`,
          transformOrigin: 'center',
        }}
      />
    </span>
  )
}
