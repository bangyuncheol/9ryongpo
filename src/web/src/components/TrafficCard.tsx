import type { Traffic } from '../api'
import Card, { ErrorLine } from './Card'

export default function TrafficCard({ traffic, error, advice }: { traffic: Traffic | null; error: string | null; advice: string | null }) {
  const last = traffic?.last_hour
  const cmp = traffic && traffic.vs_yesterday.level !== '비교 불가'
    ? `어제 이맘때보다 ${traffic.vs_yesterday.level}`
    : traffic?.vs_day && traffic.vs_day !== '비교 불가' ? `오늘 하루 중 ${traffic.vs_day}` : null
  const tip = advice ? advice.split('. ').slice(-1)[0] : null
  return (
    <Card id="traffic" title="위판장 앞 지금" aside="실제 현재 시각 실측 · 교통센서3(위판장 80m)">
      {last ? (
        <>
          <p className="text-body">
            지난 1시간 트럭 <b className="tabular-nums">{last.truck}</b>대 · 전체 <b className="tabular-nums">{last.total}</b>대
            {cmp && <span className="text-muted"> · {cmp}</span>}
          </p>
          {tip && <p className="mt-1 text-body font-bold text-primary-dark">{tip}</p>}
          <MiniBars hours={traffic!.hours} />
          {traffic!.stale && <p className="mt-1 text-small text-muted">최신 조회에 실패해 직전 값을 보여 줍니다.</p>}
        </>
      ) : (
        !error && <p className="text-sub text-muted">교통 정보를 불러오는 중입니다.</p>
      )}
      <ErrorLine message={error && !last ? '교통 정보를 지금 불러올 수 없습니다. 잠시 후 다시 확인해 주세요.' : null} />
    </Card>
  )
}

function MiniBars({ hours }: { hours: Traffic['hours'] }) {
  const max = Math.max(1, ...hours.map((h) => h.total))
  return (
    <figure className="mt-4">
      <div className="flex h-24 items-end gap-1.5" role="img" aria-label="최근 9시간 시간대별 통행량(진한 부분이 트럭)">
        {hours.map((h) => (
          <div key={h.hour} className="flex flex-1 flex-col items-center gap-1">
            <div className="flex w-full flex-col justify-end" style={{ height: 72 }}>
              <div className="w-full rounded-t-md bg-primary-soft" style={{ height: `${((h.total - h.truck) / max) * 72}px` }} />
              <div className="w-full bg-primary-dark" style={{ height: `${(h.truck / max) * 72}px` }} />
            </div>
            <span className="text-[11px] tabular-nums text-muted">{h.hour.slice(11, 13)}시</span>
          </div>
        ))}
      </div>
      <figcaption className="mt-1 flex gap-3 text-small text-muted">
        <span><span aria-hidden className="mr-1 inline-block h-2.5 w-2.5 rounded-sm bg-primary-dark align-middle" />트럭</span>
        <span><span aria-hidden className="mr-1 inline-block h-2.5 w-2.5 rounded-sm bg-primary-soft align-middle" />그 밖의 차량</span>
      </figcaption>
    </figure>
  )
}
