import { useCallback, useEffect, useState } from 'react'
import { api, hhmm } from '../api'
import type { Arrival, CallState, Place, Sensor, Today } from '../api'
import { usePoll } from '../usePoll'
import MapView from '../components/MapView'
import ChatCard from '../components/ChatCard'
import AdminBar from '../components/AdminBar'
import CallCard from '../components/CallCard'
import Toast from './Toast'
import WaitFish from './WaitFish'
import Icon from './Icon'
import BottomSheet, { HANDLE_H } from './BottomSheet'
import Pager from './Pager'
import { snapHeights, useViewportHeight } from './sheet'
import type { Snap } from './sheet'
import { byEta, likelihood, minutesUntil, shipSpecies, shortBiz, telHref, telText, trafficWord, useThemeColor, useWide } from './bits'
import type { VisitData } from './bits'
import './v4.css'

/*
 * 4차 시안(?v=4, 10/11) — '새벽 바다 지도'. 정본 규칙: .claude/rules/design-v4.md
 * 지도가 화면의 주인공(최소 성공선 '지도에 배가 움직인다')이고, 정보는 지도 위로 올라오는 시트에 담는다.
 * 폰: 지도는 위에 고정, 시트는 스크롤하면 지도 위로 끌려 올라온다(드래그 코드 없이 스크롤만 — 손에 익은 동작).
 * 웹(1024px 이상): 지도가 왼쪽 전체, 시트는 오른쪽 고정 칸.
 * 데이터·동작은 버전 2와 같다(같은 API, 같은 알림 신청 부품). 숫자는 서버 값 그대로.
 */
const PAGE = { light: '#c8dcde', dark: '#c8dcde' } // v4.css --color-band(헤더 띠 색). 다크 모드 기기에서도 라이트(10/12 오너)

export default function AppV4() {
  useThemeColor(PAGE)
  const wide = useWide()
  const admin = new URLSearchParams(location.search).has('admin')
  const [place, setPlace] = useState<Place | null>(null)
  const [sensor, setSensor] = useState<Sensor | null>(null)
  const [selected, setSelected] = useState<number | null>(null)
  const onSelect = useCallback((id: number | null) => setSelected(id), [])
  const [snap, setSnap] = useState<Snap>('mid') // 폰 시트: 내림·기본(다 펼침은 입력할 때만 저절로)
  const [page, setPage] = useState(0) // 폰 시트의 장: 들어오는 배 · 알림 · 물어보기(10/12)
  const [fit, setFit] = useState<number | undefined>(undefined) // 지금 장 내용 높이 + 손잡이·탭
  const onContentHeight = useCallback((h: number) => setFit(h + HANDLE_H + TABS_H), [])
  const hs = snapHeights(useViewportHeight(), fit)
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
  // '생선 알림 받기'·질문창의 알림 준비: 알림 신청 칸으로. 폰은 알림 장으로 넘긴다
  const toWait = () => {
    if (wide) { document.getElementById('wait-title')?.scrollIntoView({ behavior: 'smooth', block: 'center' }); return }
    if (snap === 'peek') setSnap('mid')
    setPage(1)
  }
  const sheet = (pages?: { height: number }) => (
    <Sheet today={t} list={arriving} idle={idle} visit={visit.data as VisitData | null} call={call.data}
      selected={selected} onSelect={onSelect} admin={admin} onWait={toWait}
      pages={pages && { page, onPage: setPage, height: pages.height, onContentHeight }} />
  )

  return (
    <div className={`v4 bg-page text-ink ${wide ? 'min-h-dvh' : 'fixed inset-0 overflow-hidden'}`}>
      <Toast items={inbox.data} />
      {wide ? (
        <div className="grid h-dvh grid-cols-[1fr_440px]">
          <div className="relative h-dvh">{map}</div>
          <aside className="v4-sheet relative z-10 h-dvh overflow-y-auto bg-card" aria-label="입항 정보">
            <div className="sticky top-0 z-10 bg-band px-6 py-3"><Badge today={t} /></div>
            {admin && <div className="py-2"><AdminBar clock={t?.clock ?? null} feed={t?.source.feed ?? null} call={call.data} /></div>}
            {sheet()}
          </aside>
        </div>
      ) : (
        <>
          <div className="absolute inset-x-0 top-0 z-40 flex flex-col justify-center bg-band px-4" style={{ height: HEADER_H }}><Badge today={t} /></div>
          {/* 지도는 헤더 아래 전체. 시트가 그 위를 덮고 두 단(내림·기본)으로 오르내린다 */}
          <div className="absolute inset-x-0 bottom-0" style={{ top: HEADER_H }}>{map}</div>
          <BottomSheet snap={snap} onSnap={setSnap} fit={fit} peek={<Peek today={t} first={arriving[0]} onOpen={() => setSnap('mid')} />}>
            {(h) => <>
              {admin && <div className="pb-2"><AdminBar clock={t?.clock ?? null} feed={t?.source.feed ?? null} call={call.data} /></div>}
              {sheet({ height: Math.max(0, h - TABS_H) })}
            </>}
          </BottomSheet>
        </>
      )}
    </div>
  )
}

const HEADER_H = 52 // 폰 헤더 띠: 아이콘 + 워드마크 + 시각만(10/13 오너: 한 줄 소개를 빼고 지도 자리를 넓힘)

/** 앱 아이콘(탭·홈 화면·푸시와 같은 그림)과 '배마중' 워드마크. 원본: 03_발표/design-preview/(10/13 오너) */
function Logo() {
  return (
    <span className="flex items-center gap-2">
      <img src="/icon-192.png" alt="" aria-hidden className="h-7 w-7 shrink-0" />
      <img src="/wordmark.png" alt="배마중" className="h-6 w-auto" />
    </span>
  )
}

/** 이름 + 어떤 데이터가 언제 기준인지. 위치가 멈췄을 때는 그 사실이 이 줄을 대신한다. */
function Badge({ today }: { today: Today | null }) {
  const sim = today?.source.feed === 'sim'
  const now = today?.clock.now
  return (
    <div>
      <div className="flex items-center justify-between gap-3">
        <h1 className="min-w-0"><Logo /></h1>
        {/* 시연이어도 실제처럼 보이게 시각만 둔다(10/11 오너 결정, CLAUDE.md '데이터 소스 표시'의 버전 4 헤더 예외). 시연·실시간은 화면 읽기 이름·title로만 */}
        <p className="shrink-0 text-body font-medium text-ink" title={sim ? '선박 위치 시연' : '실시간'}>
          <span className="sr-only">{sim ? '선박 위치 시연' : '실시간'}</span>
          {now && <span className="tabular-nums">{hhmm(now)}</span>}
        </p>
      </div>
      {today?.notice && <p role="status" className="mt-2 text-sub font-bold text-arriving">{today.notice}</p>}
    </div>
  )
}

const TABS_H = 45 // 장 탭 줄 높이(44 + 밑줄 1)

/**
 * 시트 내용. 웹은 한 칸에 세로로 잇고, 폰은 세 장(들어오는 배 · 알림 · 물어보기)으로 나눠 옆으로 넘긴다(10/12 오너:
 * 끝까지 끌어올려 보는 대신 지도와 같이 보게).
 */
function Sheet({ today, list, idle, visit, call, selected, onSelect, admin, onWait: toWait, pages }: {
  today: Today | null; list: Arrival[]; idle: number; visit: VisitData | null; call: CallState | null
  selected: number | null; onSelect: (id: number | null) => void; admin: boolean; onWait: () => void
  pages?: { page: number; onPage: (i: number) => void; height: number; onContentHeight: (h: number) => void }
}) {
  const number = call?.enabled ? call.number : null
  const [wait, setWait] = useState<{ on: boolean; species: string }>({ on: false, species: '' })
  const ships = (
    <>
      <Next today={today} list={list} idle={idle} selected={selected} onSelect={onSelect} />

      {/* 행동 두 개: 엄지가 닿는 시트 위쪽에 바로. 알림은 브랜드 시안의 민트 카드(10/13), 전화가 꺼져 있으면 알림 하나만.
          배 한 척이 아니라 '생선' 기준 알림이라는 게 보이게(10/11 오너: '들어오면 알림'은 남진호 알림으로 읽힘) */}
      <button onClick={toWait} className="v2-press mt-3 flex w-full items-center gap-4 rounded-card bg-mint px-5 py-4 text-left hover:brightness-[0.98]">
        <Icon name="bell" className={`text-[28px] fill-current ${wait.on ? 'text-arriving' : 'text-primary-dark'}`} />
        <span className="min-w-0 flex-1">
          <span className="block text-main font-bold text-ink">{wait.on ? `${wait.species} 알림 켜짐` : '생선 알림 받기'}</span>
          <span className="mt-0.5 block text-sub text-muted">{wait.on ? '다른 생선도 고를 수 있어요' : '들어오면 바로 알려 드려요'}</span>
        </span>
        <Icon name="chevron" className="text-[22px] text-muted" />
      </button>
      {number && (
        <a href={telHref(number)} className="v2-press mt-2 flex min-h-12 items-center justify-center gap-2 rounded-button bg-primary-dark px-3 text-button font-bold text-on-primary hover:brightness-110">
          <Icon name="phone" />전화로 묻기
        </a>
      )}
      {/* 사람이 받는 수협 문의 전화로 오해하지 않게 AI가 받는다는 것부터(10/11 오너) */}
      {number && <p className="mt-2 text-center text-small text-muted"><span className="tabular-nums">{telText(number)}</span>로 걸면 AI가 바로 받아요</p>}

      {visit && <Visit visit={visit} />}

      {list.length > 1 && <Queue today={today} list={list} selected={selected} onSelect={onSelect} />}
    </>
  )
  const alerts = (
    <>
      {admin && <div className="empty:hidden"><CallCard call={call} /></div>}
      <WaitFish phoneEnabled={!!call?.enabled} onChange={setWait} showMore oneTap multi />
    </>
  )
  const ask = <ChatCard onSubscribe={toWait} quick={QUICK} placeholder="예: 대게랑 오징어 들어오면 알려줘" aside={null} bubbles={!!pages} />

  if (pages) {
    return (
      <Pager tabs={['들어오는 배', '알림', '물어보기']} noFade={[2]} page={pages.page} onPage={pages.onPage} height={pages.height} onContentHeight={pages.onContentHeight}>
        {[
          <div key="ships" className="flex flex-col px-6 pb-8">{ships}</div>,
          <div key="alerts" className="px-1 pb-8">{alerts}</div>,
          <div key="ask" className="v4-no-title px-1">{ask}</div>,
        ]}
      </Pager>
    )
  }
  return (
    <div className="flex flex-col px-6 pb-10">
      {ships}
      <div className="-mx-5 mt-8 border-t border-line pt-3">
        {alerts}
        {/* 시트 안에선 카드 경계가 사라지므로 구역은 선으로 나눈다(10/11 오너: 알림과 물어보기가 붙어 보임) */}
        <div aria-hidden className="border-t border-line" />
        {ask}
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
    <section className="pt-4" aria-labelledby="v4-next">
      <h2 id="v4-next" className="sr-only">곧 들어오는 배</h2>
      {/* 브랜드 시안(10/13)의 다음 배 카드: 큰 산호 숫자 · 옆에 '분 뒤 도착'과 시각 · 선 · 배 이름 · 어종 한 줄 */}
      <button onClick={() => onSelect(on ? null : first.ship_id)} aria-pressed={on}
        className={`v2-press block w-full rounded-card px-5 py-4 text-left ring-2 transition-colors ${on ? 'bg-[var(--color-sunrise-soft)] ring-arriving/40' : 'bg-surface ring-transparent hover:brightness-[0.98]'}`}>
        <p className="flex items-center gap-3 text-arriving">
          {mins === 0
            ? <span className="text-[48px] font-extrabold leading-none tracking-tight">곧 도착</span>
            : <><span key={mins} className="v4-tick text-[64px] font-extrabold leading-none tracking-tighter tabular-nums">{mins}</span>
              <span className="flex flex-col">
                <span className="text-dialog font-bold leading-tight">분 뒤 도착</span>
                <span className="text-dialog font-semibold leading-tight tabular-nums text-muted">{hhmm(first.eta)}</span>
              </span></>}
          {mins === 0 && <span className="ml-auto text-dialog font-semibold tabular-nums text-muted">{hhmm(first.eta)}</span>}
        </p>
        <div aria-hidden className="my-3 border-t border-line" />
        <p className="text-[24px] font-extrabold leading-tight text-ink">{first.name ?? '이름 미상'}</p>
        <p className="mt-1 text-main font-bold text-arriving">
          {sp.top ? <>{sp.top.name} {likelihood(sp.top.share)} <span className="text-small font-medium text-muted">추정 {Math.round(sp.top.share * 100)}%</span></>
            : sp.categoryOnly ? <span className="text-ink">이 업종은 해마다 잡는 생선이 달라요</span> : null}
        </p>
        <p className="mt-1.5 text-small text-muted">{shortBiz(first.biz)}선{first.gt ? ` ${Math.round(first.gt)}t` : ''} · 위판장까지 {first.d_km.toFixed(1)}km · 예측(신뢰도 {first.confidence ?? '보통'})</p>
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

/**
 * 물어보기 칩(10/12 오너, 발표에서 소개). 발표 문제 장면의 사장님 질문('오늘 붉은대게 들어오나? 몇 척이나? 몇 시에 가면
 * 되나?')과 도구 넷을 한 번씩: 어종 추정 · 입항 예보 · 가는 시간(카카오) · 과거 실적. 04:00 장면에서 답 확인함.
 */
const QUICK = ['오늘 붉은대게 들어와?', '지금 들어오는 배 몇 척이야?', '포항시청에서 몇 시에 출발하면 돼?', '작년 10월 붉은대게 얼마였어?']

/** 경매 시작과 권장 도착 사이 분(서버 visit.EARLY_MIN 을 화면에 다시 적지 않으려고 두 시각에서 계산). */
function early(v: VisitData) {
  const m = (t: string) => { const [h, mm] = t.split(':').map(Number); return h * 60 + mm }
  return (m(v.auction_time) - m(v.arrive_by) + 1440) % 1440
}

/** 언제 가면 되나: 시트 안에서는 띠가 아니라 한 줄 정보로(지도와 다음 배가 주인공). */
function Visit({ visit }: { visit: VisitData }) {
  const word = trafficWord(visit.now)
  return (
    <section className="mt-3 rounded-card bg-surface px-5 py-4" aria-label="언제 가면 되나">
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
