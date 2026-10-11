import { useCallback, useEffect, useState } from 'react'
import { api, hhmm } from '../api'
import type { Place, Sensor } from '../api'
import { usePoll } from '../usePoll'
import MapView from '../components/MapView'
import ChatCard from '../components/ChatCard'
import AdminBar from '../components/AdminBar'
import AppV2, { CallUs, Depart, Header, NextShip, Tag, Toast } from '../v2/AppV2'
import type { VisitData } from '../v2/AppV2'
import WaitFish from '../v2/WaitFish'
import { byEta, telHref, telText, trafficWord } from '../v2/bits'
import '../v2/v2.css'

/*
 * 3차 시안(?v=3, 10/11). 웹(1024px 이상)은 버전 2 그대로 — 발표장 큰 화면에서 지도·입항·알림을 한눈에.
 * 폰만 '홈 + 목적별 화면'으로 나눈다(외부 검토 2차): 홈에서 오늘 상황과 다음 배 한 척은 반드시 보여 주고,
 * 자세한 정보·행동은 아래 탭(글자만, 4개 — One UI 하단 탭 규칙)으로. 전화 버튼과 작은 지도는 홈에 남긴다(어르신 입구·움직이는 배).
 */
type Tab = 'home' | 'ships' | 'alerts' | 'ask'
const TABS: [Tab, string][] = [['home', '홈'], ['ships', '들어오는 배'], ['alerts', '알림'], ['ask', '물어보기']]

function useWide() {
  const q = '(min-width: 1024px)'
  const [wide, setWide] = useState(() => window.matchMedia(q).matches)
  useEffect(() => {
    const m = window.matchMedia(q)
    const on = () => setWide(m.matches)
    m.addEventListener('change', on)
    return () => m.removeEventListener('change', on)
  }, [])
  return wide
}

export default function AppV3() {
  return useWide() ? <AppV2 /> : <PhoneV3 />
}

function PhoneV3() {
  const admin = new URLSearchParams(location.search).has('admin')
  const [tab, setTabRaw] = useState<Tab>('home')
  const setTab = (t: Tab) => { setTabRaw(t); window.scrollTo({ top: 0 }) }
  const [place, setPlace] = useState<Place | null>(null)
  const [sensor, setSensor] = useState<Sensor | null>(null)
  const [selected, setSelected] = useState<number | null>(null)
  const onSelect = useCallback((id: number | null) => setSelected(id), [])
  const today = usePoll(api.today, 2000)
  const ships = usePoll(api.ships, 2000)
  const visit = usePoll(() => api.visit(false), 60000)
  const traffic = usePoll(api.traffic, 60000)
  const trucks = usePoll(api.trafficSensors, 60000)
  const inbox = usePoll(api.notifications, 3000)
  const call = usePoll(() => api.callState(admin), admin ? 1500 : 60000)

  useEffect(() => {
    api.place().then(setPlace).catch(console.error)
    api.sensors().then((s) => setSensor(s[0] ?? null)).catch(console.error)
  }, [])

  const t = today.data
  const arriving = [...(t?.arriving ?? [])].sort(byEta)
  const idle = (ships.data?.ships ?? []).filter((s) => s.status === '조업·대기').length
  const v = visit.data as VisitData | null
  const tr = traffic.data
  const truck = tr?.last_hour ? {
    perHour: tr.last_hour.truck,
    level: tr.vs_yesterday.level !== '비교 불가' ? `어제보다 ${tr.vs_yesterday.level}` : tr.vs_day !== '비교 불가' ? tr.vs_day : null,
  } : null
  const map = (compact: boolean) => (
    <MapView place={place} ships={ships.data?.ships ?? []} arriving={t?.arriving ?? []}
      arrivedCount={t?.arrived.length ?? 0} truck={truck} trucks={trucks.data?.sensors ?? []} sensor={sensor}
      notice={t?.notice ?? null} selected={selected} onSelect={onSelect} legendToggle compact={compact} />
  )
  const number = call.data?.enabled ? call.data.number : null
  const sim = t?.source.feed === 'sim' ? '선박 위치 시연' : '실시간'

  return (
    <div className="v2 min-h-screen bg-page pb-24">
      <Toast items={inbox.data} />
      {admin && <div className="pt-3"><AdminBar clock={t?.clock ?? null} feed={t?.source.feed ?? null} call={call.data} /></div>}

      {tab === 'home' && <>
        <Header today={t} arrivingCount={arriving.length} traffic={trafficWord(v?.now)} />
        <main className="flex flex-col gap-4 px-4">
          <NextShip today={t} list={arriving} idle={idle} selected={selected} onSelect={onSelect}
            limit={0} share="none" onMore={arriving.length > 1 ? () => setTab('ships') : undefined} />
          <Depart visit={v} />
          {number && <CallRow number={number} />}
          <section aria-labelledby="mini-map">
            <div className="mb-2 flex items-baseline justify-between px-1">
              <h2 id="mini-map" className="text-title font-bold text-primary-dark">구룡포항 지금</h2>
              <button onClick={() => setTab('ships')} className="text-sub font-bold text-primary-dark">크게 보기 →</button>
            </div>
            {map(true)}
          </section>
        </main>
      </>}

      {tab === 'ships' && (
        <main className="flex flex-col gap-4 px-4 pt-5">
          <TabTitle title="들어오는 배" sub={`${hhmm(t?.clock.now)} 기준 · ${sim}`} />
          <NextShip today={t} list={arriving} idle={idle} selected={selected} onSelect={onSelect} limit={20} share="basis" />
          <section aria-label="구룡포항 지도">{map(false)}</section>
          <Depart visit={v} />
          {tr?.last_hour && (
            <p className="px-1 text-sub text-muted">위판장 앞 지난 1시간 트럭 {tr.last_hour.truck}대 · 전체 {tr.last_hour.total}대 <Tag>실측</Tag></p>
          )}
        </main>
      )}

      {tab === 'alerts' && (
        <main className="flex flex-col gap-4 px-4 pt-5">
          <TabTitle title="알림" sub="원하는 생선이 들어오면 휴대폰이나 전화로 먼저 알려 드려요" />
          <WaitFish phoneEnabled={!!call.data?.enabled} />
          <section className="rounded-card bg-card p-5" aria-labelledby="sent-title">
            <h2 id="sent-title" className="text-title font-bold text-primary-dark">보낸 알림</h2>
            {!(inbox.data ?? []).length ? <p className="mt-2 text-sub text-muted">아직 보낸 알림이 없어요.</p> : (
              <ul className="mt-3 space-y-3">
                {(inbox.data ?? []).map((n) => (
                  <li key={n.vts + n.body} className="flex gap-3 text-body">
                    <span className="shrink-0 font-bold tabular-nums text-arriving">{hhmm(n.vts)}</span><span>{n.body}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </main>
      )}

      {tab === 'ask' && (
        <main className="flex flex-col gap-4 px-4 pt-5">
          <TabTitle title="구룡포에 대해 물어보세요" sub="배가 언제 들어오는지, 오늘 어떤 생선이 들어오는지 알려 드릴게요" />
          {number && <CallUs number={number} />}
          <ChatCard onSubscribe={() => setTab('alerts')} />
        </main>
      )}

      <nav aria-label="화면 이동" className="fixed inset-x-0 bottom-0 z-[1000] border-t border-line bg-card/95 backdrop-blur">
        <ul className="mx-auto flex max-w-xl">
          {TABS.map(([k, label]) => (
            <li key={k} className="flex-1">
              <button onClick={() => setTab(k)} aria-current={tab === k ? 'page' : undefined}
                className={`relative flex h-14 w-full items-center justify-center text-sub font-bold ${tab === k ? 'text-primary-dark' : 'text-muted'}`}>
                {tab === k && <span aria-hidden className="absolute inset-x-6 top-0 h-[3px] rounded-full bg-[var(--color-sunrise)]" />}
                {label}
              </button>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  )
}

function TabTitle({ title, sub }: { title: string; sub: string }) {
  return (
    <header className="px-1">
      <h1 className="text-dialog font-bold text-primary-dark">{title}</h1>
      <p className="mt-1 text-sub text-muted">{sub}</p>
    </header>
  )
}

/** 홈용 한 줄 전화 버튼(물어보기 탭에는 큰 버튼). 어르신에게 가장 쉬운 입구라 홈에서 빼지 않는다. */
function CallRow({ number }: { number: string }) {
  return (
    <a href={telHref(number)} className="flex min-h-[var(--spacing-touch)] items-center justify-between rounded-button border-2 border-[var(--color-sunrise)] bg-card px-4 py-2">
      <span className="text-button font-bold text-primary-dark">📞 전화로 물어보기</span>
      <span className="text-sub tabular-nums text-muted">{telText(number)}</span>
    </a>
  )
}
