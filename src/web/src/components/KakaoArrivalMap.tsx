import { useEffect, useRef, useState } from 'react'
import type { Arrival, Place, Ship } from '../api'
import { hhmm } from '../api'
import { loadKakao } from './kakaoLoader'
import { shortBiz } from './ArrivalsCard'

/*
 * 입항 지도(10/10 2차 개편). 지도는 구룡포항 확대(위판장 주변 육지가 자세히 보임)로 고정.
 * - 화면 안: 들어오는 배(빨간 배 모양, 진행 방향 회전, 부드러운 이동), 정박한 배(초록, 위판장 앞 부두 자리)
 * - 화면 밖 들어오는 배: 오른쪽 가장자리 화살표 + 거리. 가까워지면 화면 안으로 들어와 배 모양이 된다
 * - 조업·대기 배: 오른쪽 위 표지 하나(척수·평균 거리)
 * - 배 정보는 마우스를 올리거나 탭했을 때(또는 입항 예보 목록에서 골랐을 때)만
 */

/* eslint-disable @typescript-eslint/no-explicit-any */
type K = any

const POLL_MS = 2000
const reduceMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
// 항구 확대 범위: 위판장 주변 육지 + 항구 + 입구 바깥 접근로(harbor.py APPROACH[0])까지
const VIEW = { s: 35.9822, n: 35.9935, w: 129.5495, e: 129.5672 }

type Props = {
  place: Place | null
  ships: Ship[]
  arriving: Arrival[]
  arrivedCount: number
  truck: { perHour: number; level: string | null } | null
  sensor: { lat: number; lon: number } | null
  notice: string | null
  selected: number | null
  onSelect: (id: number | null) => void
  onFail: () => void
}

type Track = { o: K; el: HTMLElement; from: [number, number]; to: [number, number]; t0: number; status: Ship['status'] }

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
  const k = useRef<K>(null)
  const map = useRef<K>(null)
  const tracks = useRef(new Map<number, Track>())
  const info = useRef<K>(null)
  const statics = useRef<{ star?: HTMLElement; badge?: K; badgeEl?: HTMLElement; truck?: K; truckEl?: HTMLElement }>({})
  const prevArrived = useRef<number | null>(null)
  const arrRef = useRef(new Map<number, Arrival>())
  const [ready, setReady] = useState(false)
  const [hovered, setHovered] = useState<number | null>(null)
  const { place, onFail, onSelect } = p
  const selRef = useRef<number | null>(p.selected)
  selRef.current = p.selected
  arrRef.current = new Map(p.arriving.map((a) => [a.ship_id, a]))

  // 지도: 한 번만 만든다. 구룡포항 확대로 고정, 끌기·확대 없음.
  useEffect(() => {
    let alive = true
    loadKakao().then((kakao) => {
      if (!alive || !box.current || map.current) return
      k.current = kakao
      map.current = new kakao.maps.Map(box.current, {
        center: new kakao.maps.LatLng(35.988, 129.558), level: 5, draggable: false, scrollwheel: false,
        disableDoubleClick: true, disableDoubleClickZoom: true, keyboardShortcuts: false,
      })
      map.current.setZoomable(false)
      const b = new kakao.maps.LatLngBounds()
      b.extend(new kakao.maps.LatLng(VIEW.s, VIEW.w)); b.extend(new kakao.maps.LatLng(VIEW.n, VIEW.e))
      map.current.setBounds(b, 0, 0, 0, 0)
      kakao.maps.event.addListener(map.current, 'click', () => onSelect(null))
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
    const starO = new kakao.maps.CustomOverlay({ position: pos, content: star, yAnchor: 0.5, zIndex: 5 })
    starO.setMap(m)
    const nameO = new kakao.maps.CustomOverlay({ position: pos, content: chip('구룡포수협 위판장'), yAnchor: 2.1, zIndex: 5 })
    nameO.setMap(m)
    const badgeEl = chip()
    const badge = new kakao.maps.CustomOverlay({ position: pos, content: badgeEl, xAnchor: 1.15, yAnchor: 0.5, zIndex: 6 })
    const truckEl = chip()
    const truck = new kakao.maps.CustomOverlay({ position: pos, content: truckEl, xAnchor: 1.08, yAnchor: -0.9, zIndex: 6 })
    statics.current = { star, badge, badgeEl, truck, truckEl }
    return () => { starO.setMap(null); nameO.setMap(null); badge.setMap(null); truck.setMap(null) }
  }, [ready, place])

  // 정박 N척: 실제로 부두에 멈춘 배만 센다. 하나 늘 때 별 주위 물결.
  const dockedCount = p.ships.filter(isDocked).length
  useEffect(() => {
    const s = statics.current
    if (!ready || !s.badge || !map.current) return
    if (dockedCount > 0) { s.badgeEl!.innerHTML = `⚓ 정박 ${dockedCount}척`; s.badge.setMap(map.current) } else s.badge.setMap(null)
    if (prevArrived.current !== null && dockedCount > prevArrived.current && s.star && !reduceMotion()) {
      s.star.classList.remove('port-ripple'); void s.star.offsetWidth; s.star.classList.add('port-ripple')
    }
    prevArrived.current = dockedCount
  }, [ready, dockedCount])

  useEffect(() => {
    const s = statics.current
    if (!ready || !s.truck || !map.current) return
    if (!p.truck) { s.truck.setMap(null); return }
    s.truckEl!.innerHTML = `🚚 트럭 ${p.truck.perHour}대/시${p.truck.level ? ` · <span style="font-weight:500;color:var(--color-muted)">${p.truck.level}</span>` : ''}`
    s.truck.setMap(map.current)
  }, [ready, p.truck])

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
        t = { o, el, from: to, to, t0: now, status: s.status }
        tracks.current.set(id, t)
      } else {
        t.from = lerpPos(t, now); t.to = to; t.t0 = now
      }
      t.status = s.status
      paintBoat(t.el, s, p.selected === s.ship_id)
    }
    for (const [id, t] of tracks.current) if (!seen.has(id)) { t.o.setMap(null); tracks.current.delete(id) }
  }, [ready, p.ships, p.selected, onSelect])

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
    <div ref={wrap} className="relative">
      <div ref={box} className="h-80 w-full overflow-hidden rounded-card bg-primary-soft md:h-[460px]" aria-label="입항 지도" />
      <div ref={edgeBox} className="absolute inset-0 z-[400] overflow-hidden rounded-card [&>*]:pointer-events-auto" style={{ pointerEvents: 'none' }} />
      {idle.length > 0 && (
        <p className="pointer-events-none absolute right-2 top-2 z-[500] rounded-button bg-card/90 px-3 py-1.5 text-[12px] font-bold text-muted shadow-sm">
          {stale ? '선박 위치 미갱신' : '조업·대기'} {idle.length}척 · 동쪽 약 {Math.round(idleKm)}km ▸
        </p>
      )}
      {p.notice && (
        <p className="pointer-events-none absolute inset-x-3 bottom-8 z-[500] rounded-button bg-card/95 px-3 py-2 text-center text-sub shadow-sm">{p.notice}</p>
      )}
      <div className="pointer-events-none absolute left-2 top-2 z-[500] rounded-button bg-card/90 px-3 py-2 text-[12px] leading-5 text-ink shadow-sm">
        <p className="sr-only">지도 범례</p>
        <div className="flex flex-wrap gap-x-3">
          <span><span aria-hidden style={{ color: 'var(--color-primary-dark)' }}>★</span> 위판장</span>
          <span><span aria-hidden>🚚</span> 위판장 앞 교통</span>
        </div>
        <div className="flex flex-wrap gap-x-3">
          <span><span aria-hidden style={{ color: 'var(--color-arriving)' }}>⛴</span> 들어오는 배</span>
          <span><span aria-hidden style={{ color: 'var(--color-arrived)' }}>⛴</span> 정박</span>
          <span><span aria-hidden style={{ color: 'var(--color-arriving)' }}>◀</span> 화면 밖(거리)</span>
        </div>
        <p className="text-muted">배를 누르거나 마우스를 올리면 정보가 보입니다</p>
      </div>
    </div>
  )
}

function lerpPos(t: Track, now: number): [number, number] {
  if (reduceMotion()) return t.to
  const f = Math.min(1, (now - t.t0) / POLL_MS)
  return [t.from[0] + (t.to[0] - t.from[0]) * f, t.from[1] + (t.to[1] - t.from[1]) * f]
}
