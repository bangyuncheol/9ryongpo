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
import BottomSheet from './BottomSheet'
import { snapHeights, useViewportHeight } from './sheet'
import type { Snap } from './sheet'
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
  const [snap, setSnap] = useState<Snap>('mid') // 폰 시트: 내림·기본·다 펼침
  const hs = snapHeights(useViewportHeight())
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
      notice={t?.notice ?? null} selected={selected} onSelect={onSelect} legendToggle fill padBottom={wide ? 0 : hs[snap]} />
  )
  // '들어오면 알림'·질문창의 알림 준비: 알림 신청 칸으로. 폰은 시트를 먼저 다 펼친다
  const toWait = () => {
    const go = () => document.getElementById('wait-title')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    if (wide || snap === 'full') go(); else { setSnap('full'); setTimeout(go, 380) }
  }
  const sheet = (
    <Sheet today={t} list={arriving} idle={idle} visit={visit.data as VisitData | null} call={call.data}
      selected={selected} onSelect={onSelect} admin={admin} onWait={toWait} />
  )

  return (
    <div className={`v4 bg-page text-ink ${wide ? 'min-h-dvh' : 'fixed inset-0 overflow-hidden'}`}>
      <Toast items={inbox.data} />
      {wide ? (
        <div className="grid h-dvh grid-cols-[1fr_440px]">
          <div className="relative h-dvh">{map}</div>
          <aside className="v4-sheet relative z-10 h-dvh overflow-y-auto bg-card" aria-label="입항 정보">
            <div className="sticky top-0 z-10 bg-card/95 px-6 pb-2 pt-5 backdrop-blur-sm"><Badge today={t} /></div>
            {admin && <div className="py-2"><AdminBar clock={t?.clock ?? null} feed={t?.source.feed ?? null} call={call.data} /></div>}
            {sheet}
          </aside>
        </div>
      ) : (
        <>
          <div className="absolute inset-x-0 top-0 z-40 h-[52px] bg-page px-4 py-3"><Badge today={t} /></div>
          {/* 지도는 헤더 아래 전체. 시트가 그 위를 덮고 3단으로 오르내린다 */}
          <div className="absolute inset-x-0 bottom-0 top-[52px]">{map}</div>
          <BottomSheet snap={snap} onSnap={setSnap} peek={<Peek today={t} first={arriving[0]} onOpen={() => setSnap('mid')} />}>
            {admin && <div className="pb-2"><AdminBar clock={t?.clock ?? null} feed={t?.source.feed ?? null} call={call.data} /></div>}
            <div className="pb-10">{sheet}</div>
          </BottomSheet>
        </>
      )}
    </div>
  )
}

/** 앱 아이콘 파일 그대로(탭·홈 화면·푸시와 같은 청록 로고, 10/11 오너) */
function Logo() {
  return <img src="/icon.svg" alt="" aria-hidden className="h-6 w-6 shrink-0" />
}

/** 이름 + 어떤 데이터가 언제 기준인지. 위치가 멈췄을 때는 그 사실이 이 줄을 대신한다. */
function Badge({ today }: { today: Today | null }) {
  const sim = today?.source.feed === 'sim'
  const now = today?.clock.now
  return (
    <div>
      <div className="flex items-center justify-between gap-3">
        <h1 className="flex items-center gap-2 text-main font-extrabold tracking-tight text-primary-dark"><Logo />배마중</h1>
        {/* 시연이어도 실제처럼 보이게 시각만 둔다(10/11 오너 결정, CLAUDE.md '데이터 소스 표시'의 버전 4 헤더 예외). 시연·실시간은 화면 읽기 이름·title로만 */}
        <p className="text-small text-muted" title={sim ? '선박 위치 시연' : '실시간'}>
          <span className="sr-only">{sim ? '선박 위치 시연' : '실시간'}</span>
          {now && <span className="tabular-nums">{hhmm(now)}</span>}
        </p>
      </div>
      {today?.notice && <p role="status" className="mt-2 text-sub font-bold text-arriving">{today.notice}</p>}
    </div>
  )
}

function Sheet({ today, list, idle, visit, call, selected, onSelect, admin, onWait: toWait }: {
  today: Today | null; list: Arrival[]; idle: number; visit: VisitData | null; call: CallState | null
  selected: number | null; onSelect: (id: number | null) => void; admin: boolean; onWait: () => void
}) {
  const number = call?.enabled ? call.number : null
  const [wait, setWait] = useState<{ on: boolean; species: string }>({ on: false, species: '' })
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
        {/* 배 한 척이 아니라 '생선' 기준 알림이라는 게 보이게(10/11 오너: '들어오면 알림'은 남진호 알림으로 읽힘) */}
        <button onClick={toWait} className="v2-press flex min-h-12 min-w-0 items-center justify-center gap-2 rounded-button bg-chip px-3 text-button font-bold text-ink hover:brightness-95">
          <Icon name="bell" className={wait.on ? 'text-arriving' : ''} />
          <span className="truncate">{wait.on ? `${wait.species === '전체' ? '모든 생선' : wait.species} 알림 켜짐` : '생선 알림 받기'}</span>
        </button>
      </div>
      {/* 사람이 받는 수협 문의 전화로 오해하지 않게 AI가 받는다는 것부터(10/11 오너) */}
      {number && <p className="mt-2 text-center text-small text-muted"><span className="tabular-nums">{telText(number)}</span>로 걸면 AI가 바로 받아요</p>}

      {visit && <Visit visit={visit} />}

      {list.length > 1 && <Queue today={today} list={list} selected={selected} onSelect={onSelect} />}

      <div className="-mx-5 mt-8 border-t border-line pt-3">
        {admin && <div className="empty:hidden"><CallCard call={call} /></div>}
        <WaitFish phoneEnabled={!!call?.enabled} onChange={setWait} showMore oneTap />
        {/* 시트 안에선 카드 경계가 사라지므로 구역은 선으로 나눈다(10/11 오너: 알림과 물어보기가 붙어 보임) */}
        <div aria-hidden className="border-t border-line" />
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

/** 시트를 내렸을 때 손잡이 아래 남는 한 줄: 다음 배만. 누르면 기본 높이로. */
function Peek({ today, first, onOpen }: { today: Today | null; first?: Arrival; onOpen: () => void }) {
  const mins = first ? minutesUntil(today?.clock.now, first.eta) : null
  return (
    <button type="button" onClick={onOpen} className="flex h-11 w-full shrink-0 items-baseline gap-2 px-6 text-left">
      {first ? <>
        <span className="text-main font-extrabold tabular-nums text-arriving">{mins === 0 ? '곧 도착' : `${mins}분 뒤`}</span>
        <span className="min-w-0 truncate text-body font-bold">{first.name ?? '이름 미상'}</span>
        <span className="ml-auto text-sub tabular-nums text-muted">{hhmm(first.eta)}</span>
      </> : <span className="text-body font-bold">아직 항구로 오는 배가 없어요</span>}
    </button>
  )
}

/** 경매 시작과 권장 도착 사이 분(서버 visit.EARLY_MIN 을 화면에 다시 적지 않으려고 두 시각에서 계산). */
function early(v: VisitData) {
  const m = (t: string) => { const [h, mm] = t.split(':').map(Number); return h * 60 + mm }
  return (m(v.auction_time) - m(v.arrive_by) + 1440) % 1440
}

/** 언제 가면 되나: 시트 안에서는 띠가 아니라 한 줄 정보로(지도와 다음 배가 주인공). */
function Visit({ visit }: { visit: VisitData }) {
  const word = trafficWord(visit.now)
  return (
    <section className="mt-6 rounded-button bg-page px-4 py-3" aria-label="언제 가면 되나">
      {/* 왜 그 시각인지 한 번에 읽히게: 경매 시작 → 몇 분 전 → 도착 시각(10/11 오너) */}
      <p className="text-body font-bold">경매가 <span className="tabular-nums">{visit.auction_time}</span>에 시작해요.<br />
        {early(visit) > 0 ? `${early(visit)}분 전인 ` : ''}<span className="tabular-nums">{visit.arrive_by}</span>까지 오시면 돼요</p>
      {word && <p className="mt-1 flex items-start gap-1.5 text-sub text-muted"><Icon name="truck" className="mt-[3px]" /><span>지금 위판장 앞은 {word}</span></p>}
    </section>
  )
}

/** 그다음 배들: 시각표처럼 한 줄씩. 누르면 지도에서 그 배를 짚는다. */
function Queue({ today, list, selected, onSelect }: { today: Today | null; list: Arrival[]; selected: number | null; onSelect: (id: number | null) => void }) {
  return (
    <section className="mt-7" aria-labelledby="v4-queue">
      <h2 id="v4-queue" className="text-title font-bold text-primary-dark">그다음 들어오는 배 <span className="text-sub font-medium text-muted">{list.length - 1}척</span></h2>
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
