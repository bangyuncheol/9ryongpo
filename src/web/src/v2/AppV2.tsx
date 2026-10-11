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
import Icon from './Icon'
import { byEta, likelihood, useThemeColor, minutesUntil, shipSpecies, shortBiz, telHref, telText, trafficWord } from './bits'
import './v2.css'

/*
 * 2차 시안(?v=2, 10/11). 기존 화면(/)은 그대로 두고 같은 API로 옆에서 키운다.
 * 원칙: 3초 안에 상황 파악 — 위에서부터 '오늘의 구룡포 → 곧 들어오는 배 → 언제 가면 되나 → 전화로 물어보기 →
 * 기다리는 생선(알림) → 지도 → 물어보기'. 폰 390px 기준, 넓으면 두 칸.
 * 라벨: 예측(입항 시각)·추정(어종)·실측(교통)·시연(선박 위치 시뮬레이션)을 작게 붙여 믿어도 되는 정도를 알린다.
 */
export default function AppV2() {
  useThemeColor()
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
      <Header today={t} />
      {admin && <div className="mb-4"><AdminBar clock={t?.clock ?? null} feed={t?.source.feed ?? null} call={call.data} /></div>}
      <main className="mx-auto flex max-w-5xl flex-col gap-4 px-4 lg:grid lg:grid-cols-[5fr_7fr] lg:items-start">
        <div className="flex flex-col gap-4">
          <NextShip today={t} list={arriving} idle={idle} onSelect={onSelect} selected={selected} />
          <Depart visit={visit.data as VisitData | null} />
          {call.data?.enabled && call.data.number && <CallUs number={call.data.number} />}
          <WaitFish phoneEnabled={!!call.data?.enabled} />
        </div>
        <div className="flex flex-col gap-4 lg:sticky lg:top-4">
          {admin && <div className="empty:hidden"><CallCard call={call.data} /></div>}
          <section aria-labelledby="map-title">
            <h2 id="map-title" className="mb-2 px-1 text-title font-bold text-primary-dark">구룡포항 지금</h2>
            <MapView place={place} ships={ships.data?.ships ?? []} arriving={t?.arriving ?? []}
              arrivedCount={t?.arrived.length ?? 0} truck={truck} trucks={trucks.data?.sensors ?? []} sensor={sensor}
              notice={t?.notice ?? null} selected={selected} onSelect={onSelect} legendToggle />
          </section>
          <ChatCard onSubscribe={() => document.getElementById('wait-title')?.scrollIntoView({ behavior: 'smooth', block: 'center' })} />
        </div>
      </main>
    </div>
  )
}

export type VisitData = { auction_time: string; arrive_by: string; now?: string | null; advice: string }

export function Tag({ children, tone = 'muted' }: { children: ReactNode; tone?: 'muted' | 'sun' }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-small font-bold ${
      tone === 'sun' ? 'bg-[var(--color-sunrise-soft)] text-arriving' : 'bg-chip text-muted'}`}>{children}</span>
  )
}

/**
 * 한 줄 헤더: 이름 + 언제 기준의 어떤 데이터인지(10/11 다듬기). 입항 척수·어종·교통은 바로 아래 카드들이 말하므로
 * 여기서 되풀이하지 않는다. 선박 위치가 멈췄을 때만 그 사실을 한 줄 더 띄운다.
 */
export function Header({ today }: { today: Today | null }) {
  const now = today?.clock.now
  const sim = today?.source.feed === 'sim'
  return (
    <header className="mx-auto max-w-5xl px-4 pb-4 pt-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-main font-extrabold tracking-tight text-primary-dark">배마중 <span className="text-sub font-medium text-muted">구룡포항</span></p>
        <p className="flex items-center gap-1.5 text-small text-muted">
          <span aria-hidden className={`h-2 w-2 rounded-full ${sim ? 'bg-[var(--color-sunrise)]' : 'bg-arrived'}`} />
          <span>{sim ? '선박 위치 시연' : '실시간'}</span>
          {now && <span className="tabular-nums">· {hhmm(now)} 기준</span>}
        </p>
      </div>
      {today?.notice && <p role="status" className="mt-3 rounded-card bg-card px-4 py-3 text-sub font-bold text-arriving">{today.notice}</p>}
    </header>
  )
}

/** 가장 먼저 들어오는 배를 크게, 나머지는 한 줄씩. 모든 배에 같은 공간을 주지 않는다. */
export function NextShip({ today, list, idle, selected, onSelect, limit = 5, onMore, share = 'short' }: {
  today: Today | null; list: Arrival[]; idle: number; selected: number | null; onSelect: (id: number | null) => void
  /** 큰 카드 아래 한 줄씩 보여 줄 배 수(버전 3 홈은 0) */ limit?: number
  /** 있으면 '들어오는 배 N척 모두 보기' 버튼을 단다 */ onMore?: () => void
  /** 어종 비율 표기: short='추정 79%', basis='최근 4년 10월 위판의 79%'(정확도로 오해 방지), none=말만 */ share?: 'short' | 'basis' | 'none'
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
      <h2 id="next-title" className="text-title font-bold text-primary-dark">곧 들어오는 배</h2>
      {/* 카드 안에 카드를 두지 않는다: 첫 배는 크기로 앞세우고, 고른 배만 옅은 바탕으로 표시(10/11 다듬기) */}
      <button onClick={() => onSelect(selected === first.ship_id ? null : first.ship_id)} aria-pressed={selected === first.ship_id}
        className={`v2-press -mx-3 mt-2 block w-[calc(100%+1.5rem)] rounded-button px-3 py-3 text-left ${selected === first.ship_id ? 'bg-[var(--color-sunrise-soft)]' : 'hover:bg-chip'}`}>
        <div className="flex flex-wrap items-baseline gap-x-3">
          <span className="text-[44px] font-extrabold leading-none tracking-tight tabular-nums text-arriving">{hhmm(first.eta)}</span>
          <span className="text-main font-bold text-arriving">{mins === 0 ? '곧 도착' : `${mins}분 뒤`}</span>
        </div>
        <p className="mt-3 text-dialog font-bold">{first.name ?? '이름 미상'}</p>
        <p className="text-sub text-muted">{shortBiz(first.biz)}선 {first.gt ? `${Math.round(first.gt)}t` : ''} · 위판장까지 {first.d_km.toFixed(1)}km · 예측(신뢰도 {first.confidence ?? '보통'})</p>
        <p className="mt-3 text-body font-bold">
          {sp.top ? <>{sp.top.name} {likelihood(sp.top.share)} {share !== 'none' && <span className="text-small font-medium text-muted">{
            share === 'basis' ? `최근 4년 ${Number(today.clock.now.slice(5, 7))}월 위판의 ${Math.round(sp.top.share * 100)}%` : `추정 ${Math.round(sp.top.share * 100)}%`}</span>}</>
            : sp.categoryOnly ? <span className="text-muted">이 업종은 해마다 잡는 생선이 달라요</span> : null}
        </p>
      </button>
      {list.length > 1 && limit > 0 && (
        <ul className="mt-2 divide-y divide-line">
          {list.slice(1, 1 + limit).map((a) => {
            const s = shipSpecies(today, a)
            return (
              <li key={a.ship_id}>
                <button onClick={() => onSelect(selected === a.ship_id ? null : a.ship_id)} aria-pressed={selected === a.ship_id}
                  className={`v2-press -mx-3 flex min-h-[var(--spacing-touch)] w-[calc(100%+1.5rem)] items-center gap-3 rounded-button px-3 py-2 text-left ${selected === a.ship_id ? 'bg-[var(--color-sunrise-soft)]' : 'hover:bg-chip'}`}>
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
      {onMore && (
        <button onClick={onMore} className="v2-press mt-3 flex min-h-[var(--spacing-touch)] w-full items-center justify-between rounded-button bg-chip px-4 text-button font-bold hover:brightness-95">
          들어오는 배 {list.length}척 모두 보기 <Icon name="arrow" />
        </button>
      )}
    </section>
  )
}

/** '언제 가면 되나'를 한 문장으로: 경매 시각 + 도착 권장 + 지금 위판장 앞(실측). */
export function Depart({ visit }: { visit: VisitData | null }) {
  if (!visit) return null
  const word = trafficWord(visit.now)
  return (
    <section className="rounded-card bg-[var(--color-hero)] p-5 text-[var(--color-on-hero)]" aria-label="언제 가면 되나">
      {/* 머리말("언제 가면 될까요?") 없이 답이 곧 제목(10/11 다듬기) */}
      <p className="text-dialog font-bold">경매 {visit.auction_time} · <span className="tabular-nums">{visit.arrive_by}</span>까지 도착하면 돼요</p>
      {word && <p className="mt-2 flex items-center gap-1.5 text-sub opacity-90"><Icon name="truck" />지금 위판장 앞은 {word} <span className="opacity-75">· 실측</span></p>}
    </section>
  )
}

/** 채팅이 어려운 분을 위한 가장 쉬운 입구: 누르면 바로 전화. */
export function CallUs({ number }: { number: string }) {
  return (
    <a href={telHref(number)}
      className="v2-press flex items-center gap-4 rounded-card bg-card p-4 hover:brightness-95">
      <span aria-hidden className="grid h-12 w-12 shrink-0 place-items-center rounded-full bg-primary-dark text-[22px] text-on-primary"><Icon name="phone" /></span>
      <span className="flex-1">
        <span className="block text-main font-bold text-primary-dark">전화로 물어보기</span>
        <span className="block text-sub text-muted"><span className="tabular-nums">{telText(number)}</span> · 말로 물으면 말로 알려 드려요</span>
      </span>
      <Icon name="arrow" className="text-muted" />
    </a>
  )
}

/** 새 입항 알림이 나가는 순간을 보이게: 위에서 내려오는 띠(6초). 처음 불러온 목록은 띄우지 않는다. */
export function Toast({ items }: { items: { vts: string; body: string }[] | null }) {
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
      <div className="v2-shadow flex gap-3 rounded-card bg-card p-4">
        <span aria-hidden className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-[var(--color-sunrise-soft)] text-arriving"><Icon name="bell" /></span>
        <div>
          <p className="text-sub font-bold text-arriving"><span className="tabular-nums">{hhmm(show.vts)}</span> 입항 알림을 보냈어요</p>
          <p className="mt-1 text-body">{show.body}</p>
        </div>
      </div>
    </div>
  )
}
