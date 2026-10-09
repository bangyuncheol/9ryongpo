import type { Traffic } from '../api'
import Card, { ErrorLine } from './Card'

const AUCTION = '09:00'

export default function TrafficCard({ traffic, error, advice }: { traffic: Traffic | null; error: string | null; advice: string | null }) {
  const last = traffic?.last_hour
  const cmp = traffic?.vs_yesterday.level !== '비교 불가'
    ? `어제 이맘때보다 ${traffic?.vs_yesterday.level}`
    : traffic?.vs_day ? `오늘 하루 중 ${traffic.vs_day}` : null
  return (
    <Card title="위판장 앞 지금" aside="실제 현재 시각 실측 · E-UM 교통센서3">
      {last ? (
        <>
          <p className="text-sm">
            경매 {AUCTION}(기본값) · 지난 1시간 트럭 <b className="tabular-nums">{last.truck}</b>대, 전체{' '}
            <b className="tabular-nums">{last.total}</b>대{cmp ? ` · ${cmp}` : ''}
          </p>
          {advice && <p className="mt-1 text-sm font-medium text-sea">{advice.split('. ').slice(-1)[0]}</p>}
          <MiniBars hours={traffic!.hours} />
          {traffic!.stale && <p className="mt-1 text-xs text-muted">최신 조회에 실패해 직전 값을 보여 줍니다.</p>}
        </>
      ) : (
        !error && <p className="text-sm text-muted">교통 정보를 불러오는 중입니다.</p>
      )}
      <ErrorLine message={error && !last ? '교통 정보를 지금 불러올 수 없습니다. 잠시 후 다시 확인해 주세요.' : null} />
    </Card>
  )
}

function MiniBars({ hours }: { hours: Traffic['hours'] }) {
  const max = Math.max(1, ...hours.map((h) => h.total))
  return (
    <div className="mt-3 flex h-20 items-end gap-1" role="img" aria-label="최근 9시간 시간대별 통행량">
      {hours.map((h) => (
        <div key={h.hour} className="flex flex-1 flex-col items-center gap-1">
          <div className="flex w-full flex-col justify-end" style={{ height: 64 }}>
            <div className="w-full rounded-t bg-sea-soft" style={{ height: `${((h.total - h.truck) / max) * 64}px` }} />
            <div className="w-full bg-sea" style={{ height: `${(h.truck / max) * 64}px` }} />
          </div>
          <span className="text-[10px] text-muted">{h.hour.slice(11, 13)}</span>
        </div>
      ))}
    </div>
  )
}
