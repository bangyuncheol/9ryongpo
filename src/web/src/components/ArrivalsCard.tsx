import type { Today } from '../api'
import { hhmm } from '../api'
import Card from './Card'

const short = (biz: string | null) => (biz ?? '업종 미상').replace(/어업$/, '').replace(/^(연안|근해)/, '')

export default function ArrivalsCard({ today, mode }: { today: Today | null; mode: 'boss' | 'visitor' }) {
  const arriving = today?.arriving ?? []
  const arrived = today?.arrived ?? []
  return (
    <Card title="오늘 입항 예보" aside={today ? `${hhmm(today.clock.now)} 기준` : undefined}>
      {today?.notice && <p role="status" className="mb-2 rounded bg-sea-soft p-2 text-sm">{today.notice}</p>}
      {!today?.notice && arriving.length === 0 && <p className="text-sm text-muted">지금 항구로 향하는 배가 없습니다.</p>}
      {mode === 'boss' ? (
        <ul className="divide-y divide-line">
          {arriving.map((a) => (
            <li key={a.ship_id} className="flex items-center gap-3 py-2 text-sm">
              <span className="w-12 font-bold tabular-nums text-arriving">{hhmm(a.eta)}</span>
              <span className="w-24 text-muted">{short(a.biz)} {a.gt ? `${Math.round(a.gt)}t` : ''}</span>
              <span className="flex-1 font-medium">{a.name}</span>
              <span className="text-xs text-muted">{a.d_km.toFixed(1)}km · {a.confidence}</span>
            </li>
          ))}
        </ul>
      ) : (
        arriving.length > 0 && <p className="text-sm">{summary(arriving)} 들어오는 중</p>
      )}
      {arrived.length > 0 && <p className="mt-2 text-xs text-muted">이미 들어온 배 {arrived.length}척</p>}
    </Card>
  )
}

function summary(list: Today['arriving']) {
  const c = new Map<string, number>()
  list.forEach((a) => c.set(short(a.biz), (c.get(short(a.biz)) ?? 0) + 1))
  return [...c].map(([k, v]) => `${k} ${v}척`).join(', ')
}
