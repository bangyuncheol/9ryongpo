import type { Today } from '../api'
import { hhmm } from '../api'
import { useState } from 'react'
import Card from './Card'
import More from './More'

const SHOW = 5

export const shortBiz = (biz: string | null) => (biz ?? '업종 미상').replace(/어업$/, '').replace(/^(연안|근해|동해구)/, '')

export default function ArrivalsCard({ today }: { today: Today | null }) {
  const arriving = today?.arriving ?? []
  const arrived = today?.arrived ?? []
  const [open, setOpen] = useState(false)
  const shown = open ? arriving : arriving.slice(0, SHOW)
  return (
    <Card id="arrivals" title="오늘 입항 예보" aside={today ? `${hhmm(today.clock.now)} 기준` : undefined}>
      {today?.notice && <p role="status" className="rounded-button bg-primary-soft p-3 text-sub">{today.notice}</p>}
      {!today?.notice && arriving.length === 0 && <p className="text-sub text-muted">지금 항구로 향하는 배가 없습니다.</p>}
      <ul className="divide-y divide-line">
        {shown.map((a) => (
          <li key={a.ship_id} className="flex min-h-[var(--spacing-touch)] items-center gap-3 py-2">
            <span className="w-14 text-main font-bold tabular-nums text-arriving">{hhmm(a.eta)}</span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-body font-medium">{a.name}</span>
              <span className="block text-small text-muted">
                {shortBiz(a.biz)} {a.gt ? `${Math.round(a.gt)}t` : ''} · {a.d_km.toFixed(1)}km · 신뢰도 {a.confidence}
              </span>
            </span>
          </li>
        ))}
      </ul>
      <More open={open} hidden={arriving.length - SHOW} label="나머지 배" onToggle={() => setOpen(!open)} />
      {arrived.length > 0 && <p className="mt-2 text-small text-muted">이미 들어온 배 {arrived.length}척</p>}
    </Card>
  )
}
