import { useEffect, useState } from 'react'
import { api, hhmm } from './api'
import type { Place, Sensor } from './api'
import { usePoll } from './usePoll'
import ShipMap from './components/ShipMap'
import ArrivalsCard from './components/ArrivalsCard'
import SpeciesCard from './components/SpeciesCard'
import TrafficCard from './components/TrafficCard'
import AdminBar from './components/AdminBar'
import SubscribeCard from './components/SubscribeCard'
import InboxCard from './components/InboxCard'
import ChatCard from './components/ChatCard'
import { ErrorLine } from './components/Card'

type Mode = 'boss' | 'visitor'

export default function App() {
  const [mode, setMode] = useState<Mode>('boss')
  const [place, setPlace] = useState<Place | null>(null)
  const [sensors, setSensors] = useState<Sensor[]>([])
  const today = usePoll(api.today, 2000)
  const ships = usePoll(api.ships, 2000)
  const traffic = usePoll(api.traffic, 60000)
  const inbox = usePoll(api.notifications, 3000)
  const visit = usePoll(() => api.visit(mode === 'visitor'), 60000, mode)
  const [subPreset, setSubPreset] = useState<{ species: string; at: number } | null>(null)
  const admin = new URLSearchParams(location.search).has('admin')

  useEffect(() => {
    api.place().then(setPlace).catch(console.error)
    api.sensors().then(setSensors).catch(console.error)
  }, [])

  const src = today.data?.source
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-3 p-3">
      <header className="flex items-center gap-2">
        <h1 className="text-lg font-extrabold text-sea">위판 당직</h1>
        <span className="text-sm tabular-nums text-muted">{hhmm(today.data?.clock.now)}</span>
        <div className="ml-auto flex overflow-hidden rounded-lg border border-line text-sm" role="group" aria-label="보기 모드">
          {(['boss', 'visitor'] as const).map((m) => (
            <button key={m} onClick={() => setMode(m)} aria-pressed={mode === m}
              className={`px-3 py-1 ${mode === m ? 'bg-sea text-white' : 'bg-card'}`}>
              {m === 'boss' ? '사장' : '구경'}
            </button>
          ))}
        </div>
        {src && (
          <span title={src.latest ? `마지막 수신 ${src.latest}` : undefined}
            className={`rounded-full px-2 py-0.5 text-xs font-bold text-white ${src.feed === 'sim' ? 'bg-sim' : src.stale ? 'bg-idle' : 'bg-live'}`}>
            ● {src.feed} {src.feed === 'live' && src.stale ? `미갱신(마지막 ${src.latest?.slice(0, 10)})` : ''}
          </span>
        )}
      </header>
      {admin && <AdminBar clock={today.data?.clock ?? null} feed={src?.feed ?? null} />}
      <ShipMap place={place} sensors={sensors} ships={ships.data?.ships ?? []} arriving={today.data?.arriving ?? []} />
      <ErrorLine message={today.error ?? ships.error} />
      <InboxCard items={inbox.data ?? []} />
      <ArrivalsCard today={today.data} mode={mode} />
      <SpeciesCard today={today.data} mode={mode} />
      <TrafficCard traffic={traffic.data} error={traffic.error} advice={visit.data?.advice ?? null} />
      <ChatCard onSubscribe={(species) => setSubPreset({ species, at: Date.now() })} />
      <SubscribeCard preset={subPreset} />
      <footer className="pb-6 text-center text-xs text-muted">
        선박 움직임은 {src?.feed === 'sim' ? '시뮬레이션' : '실데이터'} · 어선 명부·위판장·교통·위판 실적은 실데이터
      </footer>
    </div>
  )
}
