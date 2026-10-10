import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import type { Place, Sensor } from './api'
import { usePoll } from './usePoll'
import AppHeader from './components/AppHeader'
import BottomBar from './components/BottomBar'
import MapView from './components/MapView'
import ArrivalsCard from './components/ArrivalsCard'
import SpeciesCard from './components/SpeciesCard'
import TrafficCard from './components/TrafficCard'
import AdminBar from './components/AdminBar'
import AlertsCard from './components/AlertsCard'
import ChatCard from './components/ChatCard'
import CallCard from './components/CallCard'
import { ErrorLine } from './components/Card'

/*
 * 배치(One UI): 위 = 보는 영역(AppHeader), 아래 = 누르는 영역(카드·입력, 폰은 하단 바).
 * 폰: 한 줄(지도 → 알림(받기+보낸 알림) → 예보 → 어종 → 교통 → 질문).
 * 600px 이상: 두 칸 42:58, 960px 이상 38:62(대형 화면 분할비). 왼쪽 = 알림·예보·어종·교통, 오른쪽 = 지도·질문.
 */
export default function App() {
  const [place, setPlace] = useState<Place | null>(null)
  const [sensor, setSensor] = useState<Sensor | null>(null)
  const [selected, setSelected] = useState<number | null>(null) // 지도·입항 예보 목록에서 함께 강조할 배
  const onSelect = useCallback((id: number | null) => setSelected(id), [])
  const today = usePoll(api.today, 2000)
  const ships = usePoll(api.ships, 2000)
  const traffic = usePoll(api.traffic, 60000)
  const trucks = usePoll(api.trafficSensors, 60000)
  const inbox = usePoll(api.notifications, 3000)
  const visit = usePoll(() => api.visit(false), 60000)
  const call = usePoll(api.callState, 1500)
  const [subPreset, setSubPreset] = useState<{ species: string; at: number } | null>(null)
  const admin = new URLSearchParams(location.search).has('admin')

  useEffect(() => {
    api.place().then(setPlace).catch(console.error)
    api.sensors().then((s) => setSensor(s[0] ?? null)).catch(console.error) // 위판장에서 가장 가까운 센서(센서3)
  }, [])

  const src = today.data?.source
  const t = traffic.data
  const truck = t?.last_hour ? {
    perHour: t.last_hour.truck,
    level: t.vs_yesterday.level !== '비교 불가' ? `어제보다 ${t.vs_yesterday.level}` : t.vs_day !== '비교 불가' ? t.vs_day : null,
  } : null
  return (
    <div className="mx-auto min-h-screen max-w-6xl pb-24 sm:pb-10">
      <AppHeader today={today.data} />
      {admin && <div className="mb-4"><AdminBar clock={today.data?.clock ?? null} feed={src?.feed ?? null} call={call.data} /></div>}
      <main className="flex flex-col gap-4 px-[var(--spacing-side)] sm:grid sm:grid-cols-[42fr_58fr] sm:items-start lg:grid-cols-[38fr_62fr]">
        <div className="contents sm:flex sm:flex-col sm:gap-4">
          <div className="order-2"><AlertsCard items={inbox.data ?? []} preset={subPreset} phone={!!call.data?.enabled} /></div>
          <div className="order-3"><ArrivalsCard today={today.data} selected={selected} onSelect={onSelect} /></div>
          <div className="order-4"><SpeciesCard today={today.data} /></div>
          <div className="order-5"><TrafficCard traffic={traffic.data} error={traffic.error} advice={visit.data?.advice ?? null} /></div>
        </div>
        <div className="contents sm:flex sm:flex-col sm:gap-4">
          <div className="order-1">
            <MapView place={place} ships={ships.data?.ships ?? []} arriving={today.data?.arriving ?? []}
              arrivedCount={today.data?.arrived.length ?? 0} truck={truck} trucks={trucks.data?.sensors ?? []} sensor={sensor}
              notice={today.data?.notice ?? null} selected={selected} onSelect={onSelect} />
            <ErrorLine message={today.error ?? ships.error} />
          </div>
          <div className="order-6 empty:hidden"><CallCard call={call.data} /></div>
          <div className="order-6"><ChatCard onSubscribe={(species) => setSubPreset({ species, at: Date.now() })} /></div>
        </div>
      </main>
      <footer className="mt-8 px-[var(--spacing-side)] text-center text-small text-muted">
        선박 움직임은 {src?.feed === 'sim' ? '시뮬레이션' : '실데이터'}입니다. 어선 명부·위판장·교통·위판 실적은 실데이터입니다.
      </footer>
      <BottomBar />
    </div>
  )
}
