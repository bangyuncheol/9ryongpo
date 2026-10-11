import { useCallback, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { api, hhmm } from '../api'
import type { Arrival, Place, Sensor, Today } from '../api'
import { usePoll } from '../usePoll'
import MapView from '../components/MapView'
import ChatCard from '../components/ChatCard'
import AdminBar from '../components/AdminBar'
import CallCard from '../components/CallCard'
import WaitFish from './WaitFish'
import { byEta, dateLine, greeting, likelihood, minutesUntil, shipSpecies, shortBiz, telHref, telText, trafficWord } from './bits'
import './v2.css'

/*
 * 2차 시안(?v=2, 10/11). 기존 화면(/)은 그대로 두고 같은 API로 옆에서 키운다.
 * 원칙: 3초 안에 상황 파악 — 위에서부터 '오늘의 구룡포 → 곧 들어오는 배 → 언제 가면 되나 → 전화로 물어보기 →
 * 기다리는 생선(알림) → 지도 → 물어보기'. 폰 390px 기준, 넓으면 두 칸.
 * 라벨: 예측(입항 시각)·추정(어종)·실측(교통)·시연(선박 위치 시뮬레이션)을 작게 붙여 믿어도 되는 정도를 알린다.
 */
export default function AppV2() {
  const admin = new URLSearchParams(location.search).has('admin')
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
  const tr = traffic.data
  const truck = tr?.last_hour ? {
    perHour: tr.last_hour.truck,
    level: tr.vs_yesterday.level !== '비교 불가' ? `어제보다 ${tr.vs_yesterday.level}` : tr.vs_day !== '비교 불가' ? tr.vs_day : null,
  } : null

  return (
    <div className="v2 min-h-screen bg-page pb-16">
      <Toast items={inbox.data} />
      <Header today={t} arrivingCount={arriving.length} traffic={trafficWord(visit.data ? (visit.data as { now?: string }).now : null)} />
      {admin && <div className="mb-4"><AdminBar clock={t?.clock ?? null} feed={t?.source.feed ?? null} call={call.data} /></div>}
      <main className="mx-auto flex max-w-5xl flex-col gap-4 px-4 lg:grid lg:grid-cols-[5fr_7fr] lg:items-start">
        <div className="flex flex-col gap-4">
          <NextShip today={t} list={arriving} idle={idle} onSelect={onSelect} selected={selected} />
          <Depart visit={visit.data as VisitData | null} />
          {call.data?.enabled && call.data.number && <CallUs number={call.data.number} />}
          <WaitFish phoneEnabled={!!call.data?.enabled} />
        </div>
        <div className="flex flex-col gap-4">
          {admin && <div className="empty:hidden"><CallCard call={call.data} /></div>}
          <section aria-labelledby="map-title">
            <div className="mb-2 flex items-baseline justify-between px-1">
              <h2 id="map-title" className="text-title font-bold text-primary-dark">구룡포항 지금</h2>
              <Tag>{t?.source.feed === 'sim' ? '선박 위치 시연' : '실시간'}</Tag>
            </div>
            <MapView place={place} ships={ships.data?.ships ?? []} arriving={t?.arriving ?? []}
              arrivedCount={t?.arrived.length ?? 0} truck={truck} trucks={trucks.data?.sensors ?? []} sensor={sensor}
              notice={t?.notice ?? null} selected={selected} onSelect={onSelect} legendToggle />
          </section>
          <ChatCard onSubscribe={() => document.getElementById('wait-title')?.scrollIntoView({ behavior: 'smooth', block: 'center' })} />
        </div>
      </main>
      <footer className="mx-auto mt-8 max-w-5xl px-4 text-center text-small text-muted">
        배를 마중 나가는 시간, 기다리지 말고 미리 알아보세요. · 2차 시안 <a className="underline" href="/">지금 화면 보기</a>
      </footer>
    </div>
  )
}

type VisitData = { auction_time: string; arrive_by: string; now?: string | null; advice: string }

function Tag({ children, tone = 'muted' }: { children: ReactNode; tone?: 'muted' | 'sun' }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-small font-bold ${
      tone === 'sun' ? 'bg-[var(--color-sunrise-soft)] text-arriving' : 'bg-chip text-muted'}`}>{children}</span>
  )
}

/** 한 줄 헤더 + 오늘의 구룡포 요약(보는 영역). 제목을 크게 두지 않고 상황을 먼저. */
function Header({ today, arrivingCount, traffic }: { today: Today | null; arrivingCount: number; traffic: string | null }) {
  const top = today?.species.overall[0]
  const now = today?.clock.now
  return (
    <header className="mx-auto max-w-5xl px-4 pb-5 pt-4">
      <div className="flex items-center justify-between">
        <p className="text-main font-extrabold tracking-tight text-primary-dark">⚓ 배마중 <span className="text-sub font-medium text-muted">구룡포항</span></p>
        <Tag>{today?.source.feed === 'sim' ? '선박 위치 시연' : '실시간'}</Tag>
      </div>
      <div className="mt-5 rounded-card bg-gradient-to-b from-[var(--color-sunrise-soft)] to-card p-5">
        <p className="text-sub text-muted">{dateLine(now)} · <span className="font-bold tabular-nums text-ink">{hhmm(now)}</span></p>
        <p className="mt-1 text-dialog font-bold text-primary-dark" aria-live="polite">
          {greeting(now)}. {today?.notice ? '지금은 선박 위치가 들어오지 않아요.' : arrivingCount ? '오늘도 배가 들어오고 있어요.' : '아직 항구로 오는 배가 없어요.'}
        </p>
        <div className="mt-3 flex flex-wrap gap-2 text-sub">
          <span className="rounded-full bg-card px-3 py-1 font-bold">🚢 입항 예정 {arrivingCount}척</span>
          {top && <span className="rounded-full bg-card px-3 py-1 font-bold">{top.name} {likelihood(top.share)}</span>}
          {traffic && <span className="rounded-full bg-card px-3 py-1 font-bold">🚗 위판장 앞 {traffic}</span>}
        </div>
      </div>
    </header>
  )
}

/** 가장 먼저 들어오는 배를 크게, 나머지는 한 줄씩. 모든 배에 같은 공간을 주지 않는다. */
function NextShip({ today, list, idle, selected, onSelect }: {
  today: Today | null; list: Arrival[]; idle: number; selected: number | null; onSelect: (id: number | null) => void
}) {
  if (!today) return <section className="rounded-card bg-card p-5 text-muted">불러오는 중입니다</section>
  const first = list[0]
  if (!first) {
    return (
      <section className="rounded-card bg-card p-5" aria-labelledby="next-title">
        <h2 id="next-title" className="text-title font-bold text-primary-dark">곧 들어오는 배</h2>
        <p className="mt-3 text-main font-bold">아직 항구로 오는 배가 없어요</p>
        <p className="mt-1 text-sub text-muted">바다에서 조업 중인 배 {idle}척 · 들어오기 시작하면 바로 알려 드릴게요.</p>
        {today.arrived.length > 0 && <p className="mt-1 text-sub text-muted">이미 들어온 배 {today.arrived.length}척</p>}
      </section>
    )
  }
  const mins = minutesUntil(today.clock.now, first.eta)
  const sp = shipSpecies(today, first)
  return (
    <section className="rounded-card bg-card p-5" aria-labelledby="next-title">
      <div className="flex items-center justify-between">
        <h2 id="next-title" className="text-title font-bold text-primary-dark">곧 들어오는 배</h2>
        <Tag tone="sun">{mins === 0 ? '곧 도착' : `다음 입항까지 약 ${mins}분`}</Tag>
      </div>
      <button onClick={() => onSelect(selected === first.ship_id ? null : first.ship_id)} aria-pressed={selected === first.ship_id}
        className={`mt-3 w-full rounded-card border-2 p-4 text-left transition-colors duration-200 ${selected === first.ship_id ? 'border-[var(--color-sunrise)]' : 'border-transparent bg-[var(--color-sunrise-soft)]'}`}>
        <div className="flex items-end gap-3">
          <span className="text-[40px] font-extrabold leading-none tabular-nums text-arriving">{hhmm(first.eta)}</span>
          <span className="pb-1 text-small text-muted">예측 · 신뢰도 {first.confidence ?? '보통'}</span>
        </div>
        <p className="mt-2 text-dialog font-bold">{first.name ?? '이름 미상'}</p>
        <p className="text-sub text-muted">{shortBiz(first.biz)}선 {first.gt ? `${Math.round(first.gt)}t` : ''} · 위판장까지 {first.d_km.toFixed(1)}km</p>
        <p className="mt-2 text-body font-bold">
          {sp.top ? <>{sp.top.name} {likelihood(sp.top.share)} <span className="text-small font-medium text-muted">추정 {Math.round(sp.top.share * 100)}%</span></>
            : sp.categoryOnly ? <span className="text-muted">이 업종은 해마다 잡는 생선이 달라요</span> : null}
        </p>
      </button>
      {list.length > 1 && (
        <ul className="mt-3 divide-y divide-line">
          {list.slice(1, 6).map((a) => {
            const s = shipSpecies(today, a)
            return (
              <li key={a.ship_id}>
                <button onClick={() => onSelect(selected === a.ship_id ? null : a.ship_id)} aria-pressed={selected === a.ship_id}
                  className={`flex min-h-[var(--spacing-touch)] w-full items-center gap-3 py-2 text-left ${selected === a.ship_id ? 'font-bold' : ''}`}>
                  <span className="w-14 text-main font-bold tabular-nums text-arriving">{hhmm(a.eta)}</span>
                  <span className="flex-1">
                    <span className="text-body font-bold">{a.name}</span>
                    <span className="block text-small text-muted">{shortBiz(a.biz)}선 · {a.d_km.toFixed(1)}km</span>
                  </span>
                  <span className="text-sub">{s.top ? s.top.name : s.categoryOnly ? '어종 미정' : ''}</span>
                </button>
              </li>
            )
          })}
        </ul>
      )}
      {today.arrived.length > 0 && <p className="mt-2 text-small text-muted">이미 들어온 배 {today.arrived.length}척</p>}
    </section>
  )
}

/** '언제 가면 되나'를 한 문장으로: 경매 시각 + 도착 권장 + 지금 위판장 앞(실측). */
function Depart({ visit }: { visit: VisitData | null }) {
  if (!visit) return null
  const word = trafficWord(visit.now)
  return (
    <section className="rounded-card bg-primary-dark p-5 text-on-primary" aria-label="언제 가면 되나">
      <p className="text-sub opacity-80">언제 가면 될까요?</p>
      <p className="mt-1 text-dialog font-bold">경매 {visit.auction_time} · <span className="tabular-nums">{visit.arrive_by}</span>까지 도착하면 돼요</p>
      {word && <p className="mt-1 text-sub opacity-90">지금 위판장 앞은 {word} <span className="opacity-70">· 실측</span></p>}
    </section>
  )
}

/** 채팅이 어려운 분을 위한 가장 쉬운 입구: 누르면 바로 전화. */
function CallUs({ number }: { number: string }) {
  return (
    <a href={telHref(number)}
      className="flex items-center gap-4 rounded-card border-2 border-[var(--color-sunrise)] bg-card p-4 transition-[filter] duration-200 hover:brightness-95">
      <span aria-hidden className="grid h-12 w-12 shrink-0 place-items-center rounded-full bg-[var(--color-sunrise)] text-2xl">📞</span>
      <span>
        <span className="block text-main font-bold text-primary-dark">전화로 물어보기</span>
        <span className="block text-sub text-muted">{telText(number)} · 말로 물으면 말로 알려 드려요</span>
      </span>
    </a>
  )
}

/** 새 입항 알림이 나가는 순간을 보이게: 위에서 내려오는 띠(6초). 처음 불러온 목록은 띄우지 않는다. */
function Toast({ items }: { items: { vts: string; body: string }[] | null }) {
  const seen = useRef<Set<string> | null>(null)
  const [show, setShow] = useState<{ vts: string; body: string } | null>(null)
  useEffect(() => {
    if (items === null) return // 아직 못 불러왔으면 기준을 잡지 않는다(열자마자 기존 알림이 뜨던 문제)
    const keys = items.map((n) => n.vts + n.body)
    if (seen.current === null) { seen.current = new Set(keys); return }
    const fresh = items.find((n) => !seen.current!.has(n.vts + n.body))
    keys.forEach((k) => seen.current!.add(k))
    if (fresh) setShow(fresh)
  }, [items])
  useEffect(() => { // 타이머는 띠가 바뀔 때만 다시 건다(3초 폴링마다 취소되지 않게)
    if (!show) return
    const id = setTimeout(() => setShow(null), 6000)
    return () => clearTimeout(id)
  }, [show])
  if (!show) return null
  return (
    <div role="status" className="v2-toast fixed inset-x-0 top-0 z-50 mx-auto max-w-xl px-4 pt-3">
      <div className="rounded-card border-l-8 border-[var(--color-sunrise)] bg-card p-4 shadow-lg">
        <p className="text-sub font-bold text-arriving">📣 {hhmm(show.vts)} 입항 알림을 보냈어요</p>
        <p className="mt-1 text-body">{show.body}</p>
      </div>
    </div>
  )
}
