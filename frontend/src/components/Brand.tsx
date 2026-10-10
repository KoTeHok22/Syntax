interface BrandMarkProps {
  size?: number
  className?: string
}

export function BrandMark({ size = 32, className = '' }: BrandMarkProps) {
  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center rounded-[10px] bg-pvn-blue shadow-blue ${className}`}
      style={{ width: size, height: size }}
    >
      <svg
        fill="none"
        height={Math.round(size * 0.56)}
        viewBox="0 0 24 24"
        width={Math.round(size * 0.56)}
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          d="M16.4 5.2 9.6 5.2 C7.6 5.2 6.2 6.5 6.2 8.3 C6.2 10 7.5 11 9.4 11 L14.6 11 C16.5 11 17.8 12 17.8 13.7 C17.8 15.5 16.4 16.8 14.4 16.8 L7.6 16.8"
          stroke="#FFFFFF"
          strokeWidth="2.3"
          strokeLinecap="round"
        />
        <circle cx="18.4" cy="18.4" fill="#EC1D35" r="1.9" />
      </svg>
    </span>
  )
}

export function BrandLockup({ size = 32, tone = 'light' }: { size?: number; tone?: 'light' | 'dark' }) {
  return (
    <span className="inline-flex items-center gap-2.5">
      <BrandMark size={size} />
      <span
        className={`font-mono text-[22px] font-extrabold lowercase tracking-tight ${
          tone === 'light' ? 'text-white' : 'text-ink'
        }`}
      >
        syntax
      </span>
    </span>
  )
}
