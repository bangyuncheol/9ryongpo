import type { Source, Today } from '../api'
import { hhmm } from '../api'
import { shortBiz } from './ArrivalsCard'

/** 확장 앱바 = 보는 영역(One UI): 넓은 여백, 가운데 큰 제목, 비인터랙티브 요약. */
export default function AppHeader({ today }: { today: Today | null }) {
  const arriving = today?.arriving ?? []
  const top = today?.species.overall[0]?.name
  const line = today?.notice
    ? '실시간 선박 위치가 들어오지 않아 예보를 멈췄습니다'
    : arriving.length
      ? `${headline(arriving)}${top ? ` · ${top} 위주` : ''}`
      : '지금 항구로 향하는 배가 없습니다'
  return (
    <header className="px-[var(--spacing-side)] pb-8 pt-4">
      <div className="flex items-center justify-end gap-2">
        <SourceBadge source={today?.source} />
      </div>
      <div className="mt-10 text-center">
        <h1 className="text-extend font-light tracking-tight">배마중</h1>
        <p className="mt-1 text-sub text-muted">구룡포 새벽 입항·어종 알림</p>
        <p className="mt-3 text-body text-muted">
          <span className="font-bold tabular-nums text-ink">{hhmm(today?.clock.now)}</span> · 구룡포 위판장
        </p>
        <p className="mt-1 text-main font-medium" aria-live="polite">{today ? line : '불러오는 중입니다'}</p>
      </div>
    </header>
  )
}

function SourceBadge({ source }: { source?: Source }) {
  if (!source) return null
  const [dot, text] = source.feed === 'sim'
    ? ['bg-sim', '시뮬레이션']
    : source.stale ? ['bg-idle', `미갱신 · 마지막 ${source.latest?.slice(0, 10) ?? '?'}`] : ['bg-live', '실시간']
  return (
    <span className="inline-flex items-center gap-1.5 rounded-button bg-card px-3 py-1.5 text-small font-bold"
      title={source.latest ? `마지막 수신 ${source.latest}` : undefined}>
      <span aria-hidden className={`h-2 w-2 rounded-full ${dot}`} />선박 위치 {text}
    </span>
  )
}

/** 보는 영역은 한 줄로: 종류가 둘 이하면 다 쓰고, 많으면 가장 많은 종류만. 예) "9척 입항 예정 · 자망선 3척 외" */
function headline(list: Today['arriving']) {
  const c = new Map<string, number>()
  list.forEach((a) => c.set(shortBiz(a.biz), (c.get(shortBiz(a.biz)) ?? 0) + 1))
  const kinds = [...c].sort((a, b) => b[1] - a[1])
  if (kinds.length <= 2) return `${kinds.map(([k, v]) => `${k}선 ${v}척`).join(', ')} 입항 예정`
  return `${list.length}척 입항 예정 · ${kinds[0][0]}선 ${kinds[0][1]}척 외`
}
