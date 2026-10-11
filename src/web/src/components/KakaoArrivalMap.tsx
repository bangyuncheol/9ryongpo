import { useEffect, useRef, useState } from 'react'
import type { Arrival, Place, SensorTraffic, Ship } from '../api'
import { hhmm } from '../api'
import { loadKakao } from './kakaoLoader'
import { shortBiz } from './ArrivalsCard'

/*
 * 입항 지도(10/10 2차 개편). 지도는 구룡포항 확대(위판장 주변 육지가 자세히 보임)로 고정.
 * - 화면 안: 들어오는 배(빨간 배 모양, 진행 방향 회전, 부드러운 이동), 정박한 배(초록, 위판장 앞 부두 자리)
 * - 화면 밖 들어오는 배: 오른쪽 가장자리 화살표 + 거리. 가까워지면 화면 안으로 들어와 배 모양이 된다
 * - 조업·대기 배: 작은 회색 점 + 오른쪽 위 버튼(척수·평균 거리, 누르면 조업 해역이 보이게 넓힘)
 * - 배 정보는 마우스를 올리거나 탭했을 때(또는 입항 예보 목록에서 골랐을 때)만
 */

/* eslint-disable @typescript-eslint/no-explicit-any */
type K = any

const POLL_MS = 2000
const reduceMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
// 항구 확대 범위: 위판장 주변 육지 + 항구 + 입구 바깥 접근로(harbor.py APPROACH[0])까지
// 서쪽은 위판장 1km 안 교통 센서(병포리 교차로·행정복지센터)까지 들어오게(10/10)
const VIEW = { s: 35.9822, n: 35.9935, w: 129.5465, e: 129.5672 }
// 움직일 수 있는 범위(10/11): 처음 화면(VIEW) 둘레 약 1.5km + 조업 해역(동쪽 6~11km, 남쪽 약 4km)까지.
// 지도 가운데가 이 밖으로 나가면 움직임이 멈출 때 처음 위치로 돌아간다. 확대는 처음 단계에서 2단계, 축소는 4단계(조업 해역이 한 화면에).
const LIMIT = { s: 35.945, n: VIEW.n + 0.014, w: VIEW.w - 0.017, e: 129.69 }
const ZOOM_IN = 2
const ZOOM_OUT = 4

type Props = {
  place: Place | null
  ships: Ship[]
  arriving: Arrival[]
  arrivedCount: number
  truck: { perHour: number; level: string | null } | null
  trucks: SensorTraffic[]
  sensor: { lat: number; lon: number } | null
  notice: string | null
  selected: number | null
  onSelect: (id: number | null) => void
  onFail: () => void
  /** true 면 범례를 접어 두고 '범례' 버튼으로 연다(2차 시안, 10/11). 기본 false = 기존처럼 늘 펼침 */
  legendToggle?: boolean
  /** true 면 지도 높이를 줄인다(버전 3 폰 홈의 작은 지도) */
  compact?: boolean
}

// path: 이번 2초 동안 그릴 꺾은선(지금 그린 위치 → 지나친 모서리들 → 새 위치). route: 마지막으로 받은 남은 꺾이는 지점
type Track = { o: K; el: HTMLElement; from: [number, number]; to: [number, number]; path: [number, number][]; route: [number, number][]; t0: number; status: Ship['status']; docked: boolean; heading: number; dockAt: Ship | null }

const boatSvg = (fill: string) =>
  `<svg width="26" height="26" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2c2.8 3 4 6.4 4 10v7.5c0 1-.8 1.8-1.8 1.8H9.8c-1 0-1.8-.8-1.8-1.8V12c0-3.6 1.2-7 4-10z" fill="${fill}" stroke="#fff" stroke-width="1.6"/><circle cx="12" cy="12" r="1.8" fill="#fff"/></svg>`

function boatEl(onTap: () => void, onHover: (on: boolean) => void) {
  const el = document.createElement('button')
  el.type = 'button'
  el.style.cssText = 'display:grid;place-items:center;width:32px;height:32px;background:transparent;border:0;padding:0;cursor:pointer'
  el.innerHTML = '<span class="boat-bob" style="display:block"><span data-hull style="display:block;transition:transform .5s cubic-bezier(.22,.25,0,1)"></span></span>'
  el.addEventListener('click', (e) => { e.stopPropagation(); onTap() })
  el.addEventListener('pointerenter', (e) => { if (e.pointerType === 'mouse') onHover(true) })
  el.addEventListener('pointerleave', (e) => { if (e.pointerType === 'mouse') onHover(false) })
  return el
}

/** 정박 = 위판장 500m 안('입항')이면서 멈춘 배. 항구 안에서 아직 움직이면 들어오는 배로 그린다. */
const isDocked = (s: Ship) => s.status === '입항' && !(s.speed && s.speed > 0)

function paintBoat(el: HTMLElement, s: Ship, selected: boolean) {
  const docked = isDocked(s)
  const hull = el.querySelector('[data-hull]') as HTMLElement
  hull.innerHTML = boatSvg(docked ? 'var(--color-arrived)' : 'var(--color-arriving)')
  // 정박한 배 방향은 서버가 자리마다 정한 값(부두와 나란히 / 뱃머리를 해안에, harbor.py)
  hull.style.transform = `rotate(${s.course ?? 270}deg) scale(${docked ? 0.8 : 1})`
  hull.style.filter = selected ? 'drop-shadow(0 0 3px var(--color-primary)) drop-shadow(0 0 2px var(--color-primary))' : ''
  ;(el.firstChild as HTMLElement).className = docked ? '' : 'boat-bob'
  el.setAttribute('aria-label', `${s.name ?? '배'} ${s.status}`)
}

const chip = (html = '') => {
  const el = document.createElement('div')
  el.style.cssText = 'pointer-events:none;padding:3px 9px;border-radius:9999px;font-size:12px;font-weight:700;white-space:nowrap;' +
    'background:var(--color-card);color:var(--color-ink);box-shadow:0 1px 4px rgba(0,0,0,.15)'
  el.innerHTML = html
  return el
}

function infoText(s: Ship, a: Arrival | undefined) {
  const kind = `${shortBiz(s.biz)} ${s.gt ? `${Math.round(s.gt)}t` : ''}`.trim()
  if (isDocked(s)) return `${s.name} · ${kind} · 정박`
  if (s.status === '입항') return `${s.name} · ${kind} · 항구 안 · 부두로 이동 중`
  if (a) return `${hhmm(a.eta)} 도착 예정 · ${s.name} · ${kind} · ${a.d_km.toFixed(1)}km`
  return `${s.name} · ${kind} · ${s.status}`
}

export default function KakaoArrivalMap(p: Props) {
  const wrap = useRef<HTMLDivElement>(null)
  const box = useRef<HTMLDivElement>(null)
  const edgeBox = useRef<HTMLDivElement>(null)
  const [legendOpen, setLegendOpen] = useState(false)
  const k = useRef<K>(null)
  const map = useRef<K>(null)
  const tracks = useRef(new Map<number, Track>())
  const info = useRef<K>(null)
  const statics = useRef<{ star?: HTMLElement }>({})
  const truckOs = useRef<K[]>([])
  const [sensorFocus, setSensorFocus] = useState<string | null>(null)  // 누르거나 올린 트럭 아이콘(센서 이름)
  const prevArrived = useRef<number | null>(null)
  const arrRef = useRef(new Map<number, Arrival>())
  const [ready, setReady] = useState(false)
  const [hovered, setHovered] = useState<number | null>(null)
  const { place, onFail, onSelect } = p
  const selRef = useRef<number | null>(p.selected)
  selRef.current = p.selected
  arrRef.current = new Map(p.arriving.map((a) => [a.ship_id, a]))

  // 지도: 한 번만 만든다. 처음엔 구룡포항 확대 화면. 끌기·확대·축소 가능(10/11 오너: 고정 해제), 범위를 벗어나면 원위치.
  const home = useRef<{ center: unknown; level: number } | null>(null)
  const [moved, setMoved] = useState(false)
  // 처음 위치로: 확대 단계를 먼저(애니메이션 없이) 맞추고 가운데를 옮긴다. 확대 애니메이션과 panTo 를 동시에
  // 보내면 이동이 무시돼 바다 한가운데 멈추는 일이 있었다(10/11 재현).
  const resetView = (m: K) => {
    const h = home.current
    if (!h) return
    m.setLevel(h.level)
    m.setCenter(h.center)
  }
  const goHome = () => { if (map.current) resetView(map.current) }
  useEffect(() => {
    let alive = true
    loadKakao().then((kakao) => {
      if (!alive || !box.current || map.current) return
      k.current = kakao
      map.current = new kakao.maps.Map(box.current, {
        center: new kakao.maps.LatLng(35.988, 129.558), level: 5, draggable: true, scrollwheel: true,
        keyboardShortcuts: false,
      })
      const m = map.current
      const b = new kakao.maps.LatLngBounds()
      b.extend(new kakao.maps.LatLng(VIEW.s, VIEW.w)); b.extend(new kakao.maps.LatLng(VIEW.n, VIEW.e))
      m.setBounds(b, 0, 0, 0, 0)
      const lv = m.getLevel()
      home.current = { center: m.getCenter(), level: lv }
      if (m.setMinLevel) m.setMinLevel(Math.max(1, lv - ZOOM_IN))
      if (m.setMaxLevel) m.setMaxLevel(lv + ZOOM_OUT)
      const limit = new kakao.maps.LatLngBounds(new kakao.maps.LatLng(LIMIT.s, LIMIT.w), new kakao.maps.LatLng(LIMIT.n, LIMIT.e))
      kakao.maps.event.addListener(m, 'idle', () => {
        const h = home.current
        if (!h) return
        if (!limit.contain(m.getCenter())) { resetView(m); return } // 범위 밖이면 처음 위치로
        const c = m.getCenter() as { getLat: () => number; getLng: () => number }
        const hc = h.center as { getLat: () => number; getLng: () => number }
        setMoved(m.getLevel() !== h.level || Math.abs(c.getLat() - hc.getLat()) > 1e-4 || Math.abs(c.getLng() - hc.getLng()) > 1e-4)
      })
      kakao.maps.event.addListener(m, 'click', () => { onSelect(null); setSensorFocus(null) })
      setReady(true)
    }).catch((e: unknown) => { console.error(e); onFail() })
    return () => { alive = false }
  }, [onFail, onSelect])

  // 위판장 별·입항 배지·트럭
  useEffect(() => {
    const kakao = k.current, m = map.current
    if (!ready || !kakao || !m || !place) return
    const pos = new kakao.maps.LatLng(place.lat, place.lon)
    const star = document.createElement('div')
    star.style.cssText = 'pointer-events:none;position:relative;width:28px;height:28px;display:grid;place-items:center;border-radius:9999px;' +
      'background:var(--color-card);box-shadow:0 1px 4px rgba(0,0,0,.2);font-size:18px;color:var(--color-primary-dark)'
    star.setAttribute('aria-label', '위판장'); star.textContent = '★'
    const starO = new kakao.maps.CustomOverlay({ position: pos, content: star, yAnchor: 0.5, zIndex: 9 })  // 별은 늘 맨 위
    starO.setMap(m)
    // 이름표·정박 N척 배지는 두지 않는다(10/10): 범례에 ★ 위판장, 정박 척수는 입항 예보 카드에 있다
    statics.current = { star }
    return () => { starO.setMap(null) }
  }, [ready, place])

  // 배가 부두에 닿는 순간(멈춘 배 수가 늘 때) 별 주위 물결
  const dockedCount = p.ships.filter(isDocked).length
  useEffect(() => {
    const s = statics.current
    if (!ready || !map.current) return
    if (prevArrived.current !== null && dockedCount > prevArrived.current && s.star && !reduceMotion()) {
      s.star.classList.remove('port-ripple'); void s.star.offsetWidth; s.star.classList.add('port-ripple')
    }
    prevArrived.current = dockedCount
  }, [ready, dockedCount])

  // 트럭 아이콘: 위판장 1km 안 교통 센서 자리. 크기는 지난 1시간 트럭 수(트럭의 위치가 아니라 그 지점을 지난 수)
  useEffect(() => {
    const kakao = k.current, m = map.current
    if (!ready || !kakao || !m) return
    truckOs.current.forEach((o) => o.setMap(null))
    truckOs.current = p.trucks.map((t) => {
      const size = Math.round(14 + Math.min(12, Math.sqrt(t.truck) * 1.3))
      const el = document.createElement('button')
      el.type = 'button'
      el.setAttribute('aria-label', `${t.nickname ?? t.name} 지난 1시간 트럭 ${t.truck}대`)
      // 흰 원 배경 없이 트럭 모양만. 둘레에 흰 테두리를 둘러 지도 위에서도 또렷하게(10/10)
      el.style.cssText = `display:grid;place-items:center;background:transparent;border:0;padding:2px;cursor:pointer;` +
        `font-size:${size}px;line-height:1;filter:drop-shadow(0 0 1px #fff) drop-shadow(0 0 1px #fff) drop-shadow(0 0 2px #fff) drop-shadow(0 1px 2px rgba(0,0,0,.25))`
      el.textContent = '🚚'
      el.addEventListener('click', (e) => { e.stopPropagation(); onSelect(null); setSensorFocus((f) => (f === t.name ? null : t.name)) })
      el.addEventListener('pointerenter', (e) => { if (e.pointerType === 'mouse') setSensorFocus(t.name) })
      el.addEventListener('pointerleave', (e) => { if (e.pointerType === 'mouse') setSensorFocus((f) => (f === t.name ? null : f)) })
      // 위판장 앞 센서는 위판장에서 77m라 별·이름표를 가린다 → 육지 쪽(왼쪽 위)으로 비켜 놓는다
      const near = t.dist_m < 150
      const o = new kakao.maps.CustomOverlay({ position: new kakao.maps.LatLng(t.lat, t.lon), content: el,
        xAnchor: near ? 1.35 : 0.5, yAnchor: near ? 1.0 : 0.5, zIndex: 7 })
      o.setMap(m)
      return o
    })
  }, [ready, p.trucks, onSelect])

  // 트럭 아이콘 정보: 위판장 앞 센서는 어제 대비도 함께
  const sensorInfo = useRef<K>(null)
  useEffect(() => {
    const kakao = k.current, m = map.current
    if (!ready || !kakao || !m) return
    sensorInfo.current?.setMap(null)
    const t = p.trucks.find((x) => x.name === sensorFocus)
    if (!t) return
    const main = t === p.trucks[0]
    const extra = main && p.truck?.level ? ` · ${p.truck.level}` : ''
    const el = chip(`🚚 ${t.nickname ?? t.name} · 지난 1시간 트럭 ${t.truck}대 · 전체 ${t.total}대${extra}`)
    sensorInfo.current = new kakao.maps.CustomOverlay({ position: new kakao.maps.LatLng(t.lat, t.lon), content: el, yAnchor: 2.2, zIndex: 41 })
    sensorInfo.current.setMap(m)
    if (el.parentElement) el.parentElement.style.pointerEvents = 'none'
  }, [ready, sensorFocus, p.trucks, p.truck])

  // 들어오는 배·정박한 배: 배 모양. 위치는 2초 사이를 부드럽게 잇는다.
  useEffect(() => {
    const kakao = k.current, m = map.current
    if (!ready || !kakao || !m) return
    const now = performance.now()
    const seen = new Set<number>()
    for (const s of p.ships) {
      if (s.status !== '입항 중' && s.status !== '입항') continue
      seen.add(s.ship_id)
      const to: [number, number] = [s.lat, s.lon]
      let t = tracks.current.get(s.ship_id)
      if (!t) {
        const id = s.ship_id
        const el = boatEl(() => onSelect(selRef.current === id ? null : id), (on) => setHovered((h) => (on ? id : h === id ? null : h)))
        const o = new kakao.maps.CustomOverlay({ position: new kakao.maps.LatLng(...to), content: el, xAnchor: 0.5, yAnchor: 0.5, zIndex: 10 })
        o.setMap(m)
        t = { o, el, from: to, to, path: [to, to], route: s.route ?? [], t0: now, status: s.status, docked: isDocked(s), heading: s.course ?? 270, dockAt: null }
        tracks.current.set(id, t)
      } else {
        const here = lerpPos(t, now)
        const next = s.route ?? []
        // 지난 2초 사이에 지나친 모서리 = 이전 남은 경로 중 새 남은 경로에 없는 앞부분(남은 경로는 항상 뒷부분이 같다)
        const passed = t.route.length >= next.length ? t.route.slice(0, t.route.length - next.length) : []
        const rewound = next.length > t.route.length // 남은 경로가 늘었다 = 시계를 되감았다 → 거꾸로 미끄러지지 않게 바로 옮긴다
        t.from = rewound ? to : here; t.to = to; t.t0 = now
        t.path = rewound ? [to, to] : [here, ...passed, to]
        t.route = next
        if (rewound) t.heading = s.course ?? t.heading // 되감은 뒤 멈춰 있으면 서버 침로로(되감기 전 방향이 남지 않게)
      }
      t.status = s.status
      // 막 정박한 배: 화면에선 아직 부두까지 2초 동안 가는 중이다. 그동안은 진행 방향을 보며 빨간 배로 가고,
      // 닿은 뒤에 뱃머리를 부두 방향으로 돌리며 초록으로 바꾼다(애니메이션 루프). 미리 돌리면 옆·뒤로 가 보였다(10/11).
      const arriving = isDocked(s) && !t.docked && pathLength(t.path) > 1e-7
      t.dockAt = arriving ? s : null
      t.docked = isDocked(s) && !arriving
      paintBoat(t.el, arriving ? { ...s, status: '입항 중', speed: HARBOR_SPEED } : s, p.selected === s.ship_id)
      if (!t.docked) setHeading(t, t.heading) // 움직이는 배는 그리는 위치의 진행 방향(애니메이션 루프가 매 프레임 갱신)
    }
    for (const [id, t] of tracks.current) if (!seen.has(id)) { t.o.setMap(null); tracks.current.delete(id) }
  }, [ready, p.ships, p.selected, onSelect])

  // 조업·대기 배: 작은 회색 점(10/11). 처음 화면 밖이라 지도를 옮기거나 축소해야 보인다. 올리면 이름.
  const idleDots = useRef(new Map<number, K>())
  useEffect(() => {
    const kakao = k.current, m = map.current
    if (!ready || !kakao || !m) return
    const seen = new Set<number>()
    for (const s of p.ships) {
      if (s.status !== '조업·대기') continue
      seen.add(s.ship_id)
      const pos = new kakao.maps.LatLng(s.lat, s.lon)
      const o = idleDots.current.get(s.ship_id)
      if (o) { o.setPosition(pos); continue }
      const el = document.createElement('div')
      el.title = `${s.name ?? '어선'} · 조업·대기`
      el.setAttribute('aria-label', `${s.name ?? '어선'} 조업·대기`)
      el.style.cssText = 'width:9px;height:9px;border-radius:9999px;background:var(--color-idle);border:1.5px solid #fff;box-shadow:0 0 1px rgba(0,0,0,.4)'
      const dot = new kakao.maps.CustomOverlay({ position: pos, content: el, xAnchor: 0.5, yAnchor: 0.5, zIndex: 5 })
      dot.setMap(m)
      idleDots.current.set(s.ship_id, dot)
    }
    for (const [id, o] of idleDots.current) if (!seen.has(id)) { o.setMap(null); idleDots.current.delete(id) }
  }, [ready, p.ships])

  /** '조업·대기 N척 ▸' 버튼: 조업 중인 배와 위판장이 한 화면에 들어오게 맞춘다. */
  const showIdle = () => {
    const kakao = k.current, m = map.current
    if (!kakao || !m || !place) return
    const b = new kakao.maps.LatLngBounds()
    b.extend(new kakao.maps.LatLng(place.lat, place.lon))
    for (const s of p.ships) if (s.status === '조업·대기') b.extend(new kakao.maps.LatLng(s.lat, s.lon))
    m.setBounds(b, 30, 30, 30, 30)
  }

  // 정보 표지: 올린 배 → 고른 배. 화면 안에 있을 때만(화면 밖이면 가장자리 화살표가 펼쳐진다).
  useEffect(() => {
    const kakao = k.current, m = map.current
    if (!ready || !kakao || !m) return
    info.current?.setMap(null)
    const id = hovered ?? p.selected
    const s = p.ships.find((x) => x.ship_id === id)
    if (!s || !m.getBounds().contain(new kakao.maps.LatLng(s.lat, s.lon))) return
    const el = chip(infoText(s, arrRef.current.get(s.ship_id)))
    const t = tracks.current.get(s.ship_id)
    const pos = t ? new kakao.maps.LatLng(...lerpPos(t, performance.now())) : new kakao.maps.LatLng(s.lat, s.lon)
    info.current = new kakao.maps.CustomOverlay({ position: pos, content: el, yAnchor: 1.9, zIndex: 40 })
    info.current.setMap(m)
    if (el.parentElement) el.parentElement.style.pointerEvents = 'none'
  }, [ready, hovered, p.selected, p.ships])

  // 애니메이션 루프: 배 위치 보간 + 화면 밖 배 가장자리 화살표
  useEffect(() => {
    const kakao = k.current, m = map.current
    if (!ready || !kakao || !m) return
    let raf = 0
    const tick = () => {
      const now = performance.now()
      const bounds = m.getBounds()
      const proj = m.getProjection()
      const W = box.current?.clientWidth ?? 0, H = box.current?.clientHeight ?? 0
      const edges: { id: number; y: number; ship: Arrival }[] = []
      for (const [id, t] of tracks.current) {
        const [la, lo] = lerpPos(t, now)
        const pos = new kakao.maps.LatLng(la, lo)
        t.o.setPosition(pos)
        if (!t.docked) { const h = lerpHeading(t, now); if (h !== null && Math.abs(h - t.heading) > 0.5) setHeading(t, h) }
        if (t.dockAt && now - t.t0 >= POLL_MS) { // 정박 지점에 닿았다 → 이제 뱃머리를 돌려 정박
          const d = t.dockAt
          t.dockAt = null; t.docked = true
          const hull = t.el.querySelector('[data-hull]') as HTMLElement | null
          if (hull) hull.style.transition = 'transform 600ms cubic-bezier(0.22, 0.25, 0, 1)'
          paintBoat(t.el, d, selRef.current === id)
          setTimeout(() => { if (hull) hull.style.transition = '' }, 700)
        }
        if (id === (selRef.current) || id === hoveredRef.current) info.current?.setPosition(pos)
        const inView = bounds.contain(pos)
        t.el.style.visibility = inView ? 'visible' : 'hidden'
        const a = arrRef.current.get(id)
        if (!inView && a && t.status === '입항 중') {
          const pt = proj.containerPointFromCoords(pos)
          edges.push({ id, y: Math.min(H - 40, Math.max(56, pt.y)), ship: a })
        }
      }
      drawEdges(edgeBox.current, edges, W)
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [ready])

  const hoveredRef = useRef<number | null>(null)
  hoveredRef.current = hovered

  // 가장자리 화살표(React 밖에서 매 프레임 갱신). 누르면 그 배를 고른다.
  function drawEdges(root: HTMLDivElement | null, edges: { id: number; y: number; ship: Arrival }[], W: number) {
    if (!root) return
    edges.sort((a, b) => a.y - b.y)
    for (let i = 1; i < edges.length; i++) edges[i].y = Math.max(edges[i].y, edges[i - 1].y + 30)
    // 아래로 넘치면 아래에서부터 위로 쌓는다(잘리지 않게)
    const H = root.clientHeight
    for (let i = edges.length - 1; i >= 0; i--) {
      const limit = i === edges.length - 1 ? H - 40 : edges[i + 1].y - 30
      if (edges[i].y > limit) edges[i].y = limit
    }
    const keep = new Set(edges.map((e) => String(e.id)))
    for (const c of [...root.children]) if (!keep.has((c as HTMLElement).dataset.id!)) c.remove()
    for (const e of edges) {
      let el = root.querySelector<HTMLButtonElement>(`[data-id="${e.id}"]`)
      if (!el) {
        el = document.createElement('button')
        el.type = 'button'; el.dataset.id = String(e.id)
        el.style.cssText = 'position:absolute;right:6px;display:flex;align-items:center;gap:4px;padding:3px 8px;border-radius:9999px;' +
          'font-size:12px;font-weight:700;white-space:nowrap;background:var(--color-card);color:var(--color-ink);box-shadow:0 1px 4px rgba(0,0,0,.18);' +
          'border:1.5px solid transparent;cursor:pointer'
        const id = e.id
        el.addEventListener('click', (ev) => { ev.stopPropagation(); onSelect(selRef.current === id ? null : id) })
        el.addEventListener('pointerenter', (ev) => { if (ev.pointerType === 'mouse') setHovered(id) })
        el.addEventListener('pointerleave', (ev) => { if (ev.pointerType === 'mouse') setHovered((h) => (h === id ? null : h)) })
        root.appendChild(el)
      }
      const open = selRef.current === e.id || hoveredRef.current === e.id
      el.style.top = `${e.y - 13}px`
      el.style.maxWidth = `${Math.max(120, W - 24)}px`
      el.style.borderColor = selRef.current === e.id ? 'var(--color-primary)' : 'transparent'
      el.setAttribute('aria-label', `${e.ship.name} ${hhmm(e.ship.eta)} 도착 예정, ${e.ship.d_km.toFixed(1)}km`)
      const text = open ? `${hhmm(e.ship.eta)} ${e.ship.name} · ${e.ship.d_km.toFixed(1)}km` : `${e.ship.d_km.toFixed(1)}km`
      el.innerHTML = `<span aria-hidden style="color:var(--color-arriving)">◀</span>${text}`
    }
  }

  const idle = p.ships.filter((x) => x.status === '조업·대기' || x.status === '미갱신')
  const idleKm = place && idle.length
    ? idle.reduce((s, x) => s + Math.hypot((x.lat - place.lat) * 111, (x.lon - place.lon) * 90), 0) / idle.length : 0
  const stale = idle[0]?.status === '미갱신'

  return (
    <div ref={wrap} className="relative isolate">{/* isolate: 지도 안 표시(z-400~500)가 지도 밖 고정 탭 막대 위로 올라오지 않게(10/11) */}
      <div ref={box} className={`${p.compact ? 'h-52' : 'h-80 md:h-[460px]'} w-full overflow-hidden rounded-card bg-primary-soft`} aria-label="입항 지도" />
      <div ref={edgeBox} className="absolute inset-0 z-[400] overflow-hidden rounded-card [&>*]:pointer-events-auto" style={{ pointerEvents: 'none' }} />
      {idle.length > 0 && (
        <button type="button" onClick={showIdle} title="조업 중인 배가 보이게 지도를 넓힙니다"
          className="absolute right-2 top-2 z-[500] rounded-button bg-card/90 px-3 py-1.5 text-[12px] font-bold text-muted shadow-sm hover:text-ink">
          {stale ? '선박 위치 미갱신' : '조업·대기'} {idle.length}척 · 동쪽 약 {Math.round(idleKm)}km ▸
        </button>
      )}
      {moved && (
        <button type="button" onClick={goHome}
          className="absolute bottom-7 left-2 z-[500] rounded-button bg-card/95 px-3 py-1.5 text-[12px] font-bold text-ink shadow-sm">
          ⟲ 처음 위치
        </button>
      )}
      {p.notice && (
        <p className="pointer-events-none absolute inset-x-3 bottom-8 z-[500] rounded-button bg-card/95 px-3 py-2 text-center text-sub shadow-sm">{p.notice}</p>
      )}
      {p.legendToggle && !legendOpen ? (
        <button type="button" onClick={() => setLegendOpen(true)} aria-expanded={false}
          className="absolute left-2 top-2 z-[500] rounded-button bg-card/90 px-3 py-1.5 text-[12px] font-bold text-ink shadow-sm">
          ⓘ 범례
        </button>
      ) : (
      <div className={`${p.legendToggle ? '' : 'pointer-events-none '}absolute left-2 top-2 z-[500] rounded-button bg-card/90 px-3 py-2 text-[12px] leading-5 text-ink shadow-sm`}>
        <p className="sr-only">지도 범례</p>
        <div className="flex flex-wrap gap-x-3">
          <span><span aria-hidden style={{ color: 'var(--color-primary-dark)' }}>★</span> 위판장</span>
          <span><span aria-hidden>🚚</span> 지난 1시간 트럭 수(클수록 많음)</span>
        </div>
        <div className="flex flex-wrap gap-x-3">
          <span><span aria-hidden style={{ color: 'var(--color-arriving)' }}>⛴</span> 들어오는 배</span>
          <span><span aria-hidden style={{ color: 'var(--color-arrived)' }}>⛴</span> 정박</span>
          <span><span aria-hidden style={{ color: 'var(--color-arriving)' }}>◀</span> 화면 밖(거리)</span>
        </div>
        <p className="text-muted">배를 누르거나 마우스를 올리면 정보가 보입니다</p>
        {p.legendToggle && <button type="button" onClick={() => setLegendOpen(false)} aria-expanded className="mt-1 font-bold text-primary-dark">접기</button>}
      </div>
      )}
    </div>
  )
}

const HARBOR_SPEED = 3 // 정박 직전 표시용(항구 안 속도, harbor.py HARBOR_KN)

function pathLength(pts: [number, number][]) {
  return pts.slice(1).reduce((a, p, i) => a + Math.hypot(p[0] - pts[i][0], (p[1] - pts[i][1]) * 0.81), 0)
}

/** 지금 그리는 구간의 진행 방향(°, 북=0 동=90). 서버 침로는 2초 앞선 위치 기준이라 모서리 앞에서 미리 꺾여 보였다(10/11). */
function lerpHeading(t: Track, now: number): number | null {
  const f = reduceMotion() ? 1 : Math.min(1, (now - t.t0) / POLL_MS)
  const pts = t.path
  const seg = pts.slice(1).map((p, i) => Math.hypot(p[0] - pts[i][0], (p[1] - pts[i][1]) * 0.81))
  const total = seg.reduce((a, b) => a + b, 0)
  if (total < 1e-7) return null // 멈춤: 마지막 방향 유지
  let d = Math.min(f * total, total - 1e-9)
  for (let i = 0; i < seg.length; i++) {
    if (seg[i] > 1e-9 && d <= seg[i]) {
      const dy = pts[i + 1][0] - pts[i][0], dx = (pts[i + 1][1] - pts[i][1]) * 0.81
      return (Math.atan2(dx, dy) * 180 / Math.PI + 360) % 360
    }
    d -= seg[i]
  }
  return null
}

function setHeading(t: Track, deg: number) {
  t.heading = deg
  const hull = t.el.querySelector('[data-hull]') as HTMLElement | null
  if (hull) hull.style.transform = `rotate(${deg}deg) scale(1)`
}

function lerpPos(t: Track, now: number): [number, number] {
  if (reduceMotion()) return t.to
  const f = Math.min(1, (now - t.t0) / POLL_MS)
  // 꺾은선을 거리 비율로 따라간다(직선으로 이으면 빠른 재생에서 방파제·육지를 가로지른다, 10/11)
  const pts = t.path
  const seg = pts.slice(1).map((p, i) => Math.hypot(p[0] - pts[i][0], (p[1] - pts[i][1]) * 0.81))
  const total = seg.reduce((a, b) => a + b, 0)
  if (!total) return t.to
  let d = f * total
  for (let i = 0; i < seg.length; i++) {
    if (d <= seg[i] || i === seg.length - 1) {
      const g = seg[i] ? Math.min(1, d / seg[i]) : 1
      return [pts[i][0] + (pts[i + 1][0] - pts[i][0]) * g, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * g]
    }
    d -= seg[i]
  }
  return t.to
}
