import type { ButtonHTMLAttributes, ReactNode } from 'react'

/** 카드: One UI 카드형 인터랙션 영역. 라운드 20px, 좌우 여백은 페이지(24px)가 준다. */
export default function Card({ id, title, aside, children }: { id?: string; title: string; aside?: ReactNode; children: ReactNode }) {
  return (
    <section id={id} className="rounded-card bg-card p-5" aria-labelledby={id ? `${id}-title` : undefined}>
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-x-2 gap-y-1">
        <h2 id={id ? `${id}-title` : undefined} className="text-title font-bold">{title}</h2>
        {aside && <div className="text-small text-muted">{aside}</div>}
      </div>
      {children}
    </section>
  )
}

export function ErrorLine({ message }: { message: string | null }) {
  if (!message) return null
  return <p role="alert" className="mt-2 text-sub text-arriving">{message}</p>
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { emphasis?: 'high' | 'medium'; compact?: boolean }

/** 화면 전체가 쓰는 단일 버튼 체계(contained). 강조는 배경색으로만: 유채색=높음, 회색=중간. */
export function Button({ emphasis = 'medium', compact = false, className = '', ...rest }: ButtonProps) {
  const tone = emphasis === 'high' ? 'bg-primary-dark text-on-primary' : 'bg-chip text-ink'
  const size = compact ? 'min-h-9 px-3 text-sub' : 'min-h-[var(--spacing-touch)] px-4 text-button'
  return (
    <button
      {...rest}
      className={`${tone} ${size} inline-flex items-center justify-center gap-1.5 rounded-button font-bold transition-[filter,opacity] duration-200 ease-oneui hover:brightness-95 active:brightness-90 disabled:opacity-50 ${className}`}
    />
  )
}
