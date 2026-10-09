import type { ReactNode } from 'react'

export default function Card({ title, aside, children }: { title: string; aside?: ReactNode; children: ReactNode }) {
  return (
    <section className="rounded-xl border border-line bg-card p-4">
      <div className="mb-2 flex items-baseline justify-between gap-2">
        <h2 className="text-base font-bold text-ink">{title}</h2>
        {aside && <div className="text-xs text-muted">{aside}</div>}
      </div>
      {children}
    </section>
  )
}

export function ErrorLine({ message }: { message: string | null }) {
  if (!message) return null
  return <p role="alert" className="mt-2 text-sm text-arriving">{message}</p>
}
