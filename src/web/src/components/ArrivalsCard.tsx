import type { Today } from '../api'
import { hhmm } from '../api'
import Card from './Card'

export const shortBiz = (biz: string | null) => (biz ?? '업종 미상').replace(/어업$/, '').replace(/^(연안|근해|동해구)/, '')

export default function ArrivalsCard({ today, mode }: { today: Today | null; mode: 'boss' | 'visitor' }) {
  const arriving = today?.arriving ?? []
  const arrived = today?.arrived ?? []
  return (
    <Card id="arrivals" title="오늘 입항 예보" aside={today ? `${hhmm(today.clock.now)} 기준` : undefined}>
      {today?.notice && <p role="status" className="rounded-button bg-primary-soft p-3 text-sub">{today.notice}</p>}
      {!today?.notice && arriving.length === 0 && <p className="text-sub text-muted">지금 항구로 향하는 배가 없습니다.</p>}
      {mode === 'boss' ? (
        <ul className="divide-y divide-line">
          {arriving.map((a) => (
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
      ) : (
        arriving.length > 0 && <p className="text-body">{summary(arriving)}이 들어오는 중입니다.</p>
      )}
      {arrived.length > 0 && <p className="mt-2 text-small text-muted">이미 들어온 배 {arrived.length}척</p>}
    </Card>
  )
}

export function summary(list: Today['arriving']) {
  const c = new Map<string, number>()
  list.forEach((a) => c.set(shortBiz(a.biz), (c.get(shortBiz(a.biz)) ?? 0) + 1))
  return [...c].map(([k, v]) => `${k}선 ${v}척`).join(', ')
}
