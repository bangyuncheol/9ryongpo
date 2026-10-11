import { useCallback, useEffect, useState } from 'react'
import { api, hhmm } from '../api'
import type { Arrival, CallState, Place, Sensor, Today } from '../api'
import { usePoll } from '../usePoll'
import MapView from '../components/MapView'
import ChatCard from '../components/ChatCard'
import AdminBar from '../components/AdminBar'
import CallCard from '../components/CallCard'
import { Toast } from '../v2/AppV2'
import type { VisitData } from '../v2/AppV2'
import WaitFish from '../v2/WaitFish'
import Icon from '../v2/Icon'
import { byEta, likelihood, minutesUntil, shipSpecies, shortBiz, telHref, telText, trafficWord, useThemeColor, useWide } from '../v2/bits'
import '../v2/v2.css'
import './v4.css'

/*
 * 4차 시안(?v=4, 10/11) — '새벽 바다 지도'. 정본 규칙: .claude/rules/design-v4.md
 * 지도가 화면의 주인공(최소 성공선 '지도에 배가 움직인다')이고, 정보는 지도 위로 올라오는 시트에 담는다.
 * 폰: 지도는 위에 고정, 시트는 스크롤하면 지도 위로 끌려 올라온다(드래그 코드 없이 스크롤만 — 손에 익은 동작).
 * 웹(1024px 이상): 지도가 왼쪽 전체, 시트는 오른쪽 고정 칸.
 * 데이터·동작은 버전 2와 같다(같은 API, 같은 알림 신청 부품). 숫자는 서버 값 그대로.
 */
const PAGE = { light: '#eef3f2', dark: '#0b1519' } // v4.css --color-page(상단 바 색)

export default function AppV4() {
  useThemeColor(PAGE)
  const wide = useWide()
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

  const map = (
    <MapView place={place} ships={ships.data?.ships ?? []} arriving={t?.arriving ?? []}
      arrivedCount={t?.arrived.length ?? 0} truck={truck} trucks={trucks.data?.sensors ?? []} sensor={sensor}
      notice={t?.notice ?? null} selected={selected} onSelect={onSelect} legendToggle fill />
  )
  const sheet = (
    <Sheet today={t} list={arriving} idle={idle} visit={visit.data as VisitData | null} call={call.data}
      selected={selected} onSelect={onSelect} admin={admin} />
  )

  return (
    <div className="v4 min-h-dvh bg-page text-ink">
      <Toast items={inbox.data} />
      {admin && <div className="relative z-30 bg-page py-2"><AdminBar clock={t?.clock ?? null} feed={t?.source.feed ?? null} call={call.data} /></div>}
      {wide ? (
        <div className="grid h-dvh grid-cols-[1fr_440px]">
          <div className="relative h-dvh">{map}</div>
          <aside className="v4-sheet relative z-10 h-dvh overflow-y-auto bg-card" aria-label="입항 정보">
            <div className="sticky top-0 z-10 bg-card/95 px-6 pb-2 pt-5 backdrop-blur-sm"><Badge today={t} /></div>
            {sheet}
          </aside>
        </div>
      ) : (
        <>
          <div className="sticky top-0 z-20 bg-page px-4 py-3"><Badge today={t} /></div>
          {/* 지도는 헤더 아래 고정. 시트가 스크롤로 그 위를 덮으며 올라온다 */}
          <div className="sticky top-[52px] h-[calc(58dvh-52px)]">{map}</div>
          <main className="v4-sheet relative z-10 -mt-5 min-h-[70dvh] rounded-t-[24px] bg-card pb-10">
            <div aria-hidden className="mx-auto mb-1 h-1.5 w-10 translate-y-2.5 rounded-full bg-line" />
            {sheet}
          </main>
        </>
      )}
    </div>
  )
}

/** 이름 + 어떤 데이터가 언제 기준인지. 위치가 멈췄을 때는 그 사실이 이 줄을 대신한다. */
function Badge({ today }: { today: Today | null }) {
  const sim = today?.source.feed === 'sim'
  const now = today?.clock.now
  return (
    <div>
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-main font-extrabold tracking-tight text-primary-dark">배마중 <span className="text-sub font-medium text-muted">구룡포항</span></h1>
        <p className="flex items-center gap-1.5 text-small text-muted">
          <span aria-hidden className={`h-2 w-2 rounded-full ${sim ? 'bg-[var(--color-sunrise)]' : 'bg-arrived'}`} />
          {sim ? '선박 위치 시연' : '실시간'}{now && <span className="tabular-nums"> · {hhmm(now)} 기준</span>}
        </p>
      </div>
      {today?.notice && <p role="status" className="mt-2 text-sub font-bold text-arriving">{today.notice}</p>}
    </div>
  )
}

function Sheet({ today, list, idle, visit, call, selected, onSelect, admin }: {
  today: Today | null; list: Arrival[]; idle: number; visit: VisitData | null; call: CallState | null
  selected: number | null; onSelect: (id: number | null) => void; admin: boolean
}) {
  const number = call?.enabled ? call.number : null
  const toWait = () => document.getElementById('wait-title')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  return (
    <div className="flex flex-col px-6">
      <Next today={today} list={list} idle={idle} selected={selected} onSelect={onSelect} />

      {/* 행동 두 개: 엄지가 닿는 시트 위쪽에 바로. 전화가 꺼져 있으면 알림 하나만 */}
      <div className={`mt-5 grid gap-2 ${number ? 'grid-cols-2' : 'grid-cols-1'}`}>
        {number && (
          <a href={telHref(number)} className="v2-press flex min-h-12 items-center justify-center gap-2 rounded-button bg-primary-dark px-3 text-button font-bold text-on-primary hover:brightness-110">
            <Icon name="phone" />전화로 묻기
          </a>
        )}
        <button onClick={toWait} className="v2-press flex min-h-12 items-center justify-center gap-2 rounded-button bg-chip px-3 text-button font-bold text-ink hover:brightness-95">
          <Icon name="bell" />들어오면 알림
        </button>
      </div>
      {number && <p className="mt-2 text-center text-small text-muted">말로 물으면 말로 알려 드려요 · <span className="tabular-nums">{telText(number)}</span></p>}

      {visit && <Visit visit={visit} />}

      {list.length > 1 && <Queue today={today} list={list} selected={selected} onSelect={onSelect} />}

      <div className="-mx-5 mt-8 border-t border-line pt-3">
        {admin && <div className="empty:hidden"><CallCard call={call} /></div>}
        <WaitFish phoneEnabled={!!call?.enabled} />
        <ChatCard onSubscribe={toWait} />
      </div>
    </div>
  )
}

/** 다음 배 한 척: 남은 시간이 가장 크다. 시트를 처음 열었을 때 보이는 곳이라 여기서 상황이 끝나야 한다. */
function Next({ today, list, idle, selected, onSelect }: {
  today: Today | null; list: Arrival[]; idle: number; selected: number | null; onSelect: (id: number | null) => void
}) {
  if (!today) return <p className="pt-6 text-muted" role="status">불러오는 중…</p>
  const first = list[0]
  if (!first) {
    return (
      <section className="pt-6" aria-labelledby="v4-next">
        <h2 id="v4-next" className="text-dialog font-bold">아직 항구로 오는 배가 없어요</h2>
        <p className="mt-1 text-sub text-muted">바다에서 조업 중인 배 {idle}척{today.arrived.length > 0 && ` · 이미 들어온 배 ${today.arrived.length}척`}</p>
      </section>
    )
  }
  const mins = minutesUntil(today.clock.now, first.eta)
  const sp = shipSpecies(today, first)
  const on = selected === first.ship_id
  return (
    <section className="pt-5" aria-labelledby="v4-next">
      <h2 id="v4-next" className="sr-only">곧 들어오는 배</h2>
      <button onClick={() => onSelect(on ? null : first.ship_id)} aria-pressed={on}
        className={`v2-press -mx-3 block w-[calc(100%+1.5rem)] rounded-button px-3 py-2 text-left ${on ? 'bg-[var(--color-sunrise-soft)]' : 'hover:bg-chip'}`}>
        <p className="flex items-baseline gap-2 text-arriving">
          {mins === 0
            ? <span className="text-[44px] font-extrabold leading-none tracking-tight">곧 도착</span>
            : <><span key={mins} className="v4-tick text-[56px] font-extrabold leading-none tracking-tight tabular-nums">{mins}</span><span className="text-dialog font-bold">분 뒤 도착</span></>}
          <span className="ml-auto text-main font-bold tabular-nums">{hhmm(first.eta)}</span>
        </p>
        <p className="mt-3 text-dialog font-bold text-ink">{first.name ?? '이름 미상'}</p>
        <p className="mt-0.5 text-body text-ink">
          {sp.top ? <><b>{sp.top.name}</b> {likelihood(sp.top.share)} <span className="text-small text-muted">추정 {Math.round(sp.top.share * 100)}%</span></>
            : sp.categoryOnly ? '이 업종은 해마다 잡는 생선이 달라요' : null}
        </p>
        <p className="mt-1 text-small text-muted">{shortBiz(first.biz)}선{first.gt ? ` ${Math.round(first.gt)}t` : ''} · 위판장까지 {first.d_km.toFixed(1)}km · 예측(신뢰도 {first.confidence ?? '보통'})</p>
      </button>
    </section>
  )
}

/** 언제 가면 되나: 시트 안에서는 띠가 아니라 한 줄 정보로(지도와 다음 배가 주인공). */
function Visit({ visit }: { visit: VisitData }) {
  const word = trafficWord(visit.now)
  return (
    <section className="mt-6 rounded-button bg-page px-4 py-3" aria-label="언제 가면 되나">
      <p className="text-body font-bold">경매 {visit.auction_time} · <span className="tabular-nums">{visit.arrive_by}</span>까지 도착하면 돼요</p>
      {word && <p className="mt-1 flex items-center gap-1.5 text-sub text-muted"><Icon name="truck" />지금 위판장 앞은 {word} · 실측</p>}
    </section>
  )
}

/** 그다음 배들: 시각표처럼 한 줄씩. 누르면 지도에서 그 배를 짚는다. */
function Queue({ today, list, selected, onSelect }: { today: Today | null; list: Arrival[]; selected: number | null; onSelect: (id: number | null) => void }) {
  return (
    <section className="mt-7" aria-labelledby="v4-queue">
      <h2 id="v4-queue" className="text-title font-bold">그다음 들어오는 배 <span className="text-sub font-medium text-muted">{list.length - 1}척</span></h2>
      <ul className="mt-2 divide-y divide-line">
        {list.slice(1).map((a) => {
          const s = shipSpecies(today, a)
          const on = selected === a.ship_id
          return (
            <li key={a.ship_id}>
              <button onClick={() => onSelect(on ? null : a.ship_id)} aria-pressed={on}
                className={`v2-press -mx-3 flex min-h-[var(--spacing-touch)] w-[calc(100%+1.5rem)] items-center gap-3 rounded-button px-3 py-2 text-left ${on ? 'bg-[var(--color-sunrise-soft)]' : 'hover:bg-chip'}`}>
                <span className="w-14 text-main font-bold tabular-nums text-arriving">{hhmm(a.eta)}</span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-body font-bold">{a.name}</span>
                  <span className="block text-small text-muted">{shortBiz(a.biz)}선 · {a.d_km.toFixed(1)}km</span>
                </span>
                <span className="text-sub">{s.top ? s.top.name : s.categoryOnly ? '어종 미정' : ''}</span>
              </button>
            </li>
          )
        })}
      </ul>
      {today && today.arrived.length > 0 && <p className="mt-2 text-small text-muted">이미 들어온 배 {today.arrived.length}척</p>}
    </section>
  )
}
