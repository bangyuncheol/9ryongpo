import type { Source, Today } from '../api'
import { hhmm } from '../api'
import { summary } from './ArrivalsCard'

type Mode = 'boss' | 'visitor'

/** 확장 앱바 = 보는 영역(One UI): 넓은 여백, 가운데 큰 제목, 비인터랙티브 요약. 조작은 우측 상단 하나뿐. */
export default function AppHeader({ today, mode, setMode }: { today: Today | null; mode: Mode; setMode: (m: Mode) => void }) {
  const arriving = today?.arriving ?? []
  const top = today?.species.overall[0]?.name
  const line = today?.notice
    ? '실시간 선박 위치가 들어오지 않아 예보를 멈췄습니다'
    : arriving.length
      ? `${summary(arriving)} 입항 예정${top ? ` · ${top} 위주` : ''}`
      : '지금 항구로 향하는 배가 없습니다'
  return (
    <header className="px-[var(--spacing-side)] pb-8 pt-4">
      <div className="flex items-center justify-end gap-2">
        <SourceBadge source={today?.source} />
        <div className="flex rounded-button bg-chip p-1" role="group" aria-label="보기 모드">
          {(['boss', 'visitor'] as const).map((m) => (
            <button key={m} onClick={() => setMode(m)} aria-pressed={mode === m}
              className={`min-h-9 rounded-button px-4 text-button font-bold transition-colors duration-200 ease-oneui ${mode === m ? 'bg-control text-on-control' : 'text-muted'}`}>
              {m === 'boss' ? '사장' : '구경'}
            </button>
          ))}
        </div>
      </div>
      <div className="mt-10 text-center">
        <h1 className="text-extend font-light tracking-tight">위판 당직</h1>
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
