import { useEffect, useRef, useState } from 'react'
import type { Arrival, Place, Ship } from '../api'
import { hhmm } from '../api'
import { loadKakao } from './kakaoLoader'

/*
 * 입항 지도(10/10 개편). 손님에게 의미 있는 것만: 위판장 ★, 위판장 앞 트럭, 들어오는 배(배 모양·ETA 표지·항로 점선),
 * 이미 들어온 배는 '입항 N척' 배지, 조업 중인 배는 묶음 하나. 지도는 위판장~앞바다 15km로 고정.
 * 배는 서버 위치(2초마다) 사이를 부드럽게 이어 움직이고, 입항 순간 별 주위에 물결이 퍼진다.
 */

/* eslint-disable @typescript-eslint/no-explicit-any */
type K = any

const POLL_MS = 2000
const reduceMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

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

type Track = { o: K; line: K; el: HTMLElement; from: [number, number]; to: [number, number]; t0: number }

const boatSvg = (fill: string) =>
  `<svg width="28" height="28" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2c2.8 3 4 6.4 4 10v7.5c0 1-.8 1.8-1.8 1.8H9.8c-1 0-1.8-.8-1.8-1.8V12c0-3.6 1.2-7 4-10z" fill="${fill}" stroke="#fff" stroke-width="1.6"/><circle cx="12" cy="12" r="1.8" fill="#fff"/></svg>`

function boatEl(onTap: () => void) {
  const el = document.createElement('button')
  el.type = 'button'
  el.style.cssText = 'position:relative;display:flex;align-items:center;gap:4px;background:transparent;border:0;padding:0;cursor:pointer'
  el.innerHTML = '<span class="boat-bob" style="display:block;width:28px;height:28px"><span data-hull style="display:block;transition:transform .5s cubic-bezier(.22,.25,0,1)"></span></span>' +
    '<span data-pill style="padding:2px 8px;border-radius:9999px;font-size:12px;font-weight:700;white-space:nowrap;background:var(--color-card);color:var(--color-ink);box-shadow:0 1px 4px rgba(0,0,0,.18);border:1.5px solid transparent"></span>'
  el.addEventListener('click', (e) => { e.stopPropagation(); onTap() })
  return el
}

/** 가까이 붙은 배의 표지가 겹치지 않게 순서대로 위·가운데·아래로 비켜 놓는다. */
const PILL_SHIFT = [0, -26, 26]

function paintBoat(el: HTMLElement, a: Arrival, course: number | null, selected: boolean, order: number) {
  const hull = el.querySelector('[data-hull]') as HTMLElement
  const pill = el.querySelector('[data-pill]') as HTMLElement
  hull.innerHTML = boatSvg('var(--color-arriving)')
  hull.style.transform = `rotate(${course ?? 270}deg)`
  pill.textContent = `${hhmm(a.eta)} ${a.name ?? ''}`
  pill.style.transform = `translateY(${PILL_SHIFT[order % 3]}px)`
  pill.style.borderColor = selected ? 'var(--color-primary)' : 'transparent'
  el.setAttribute('aria-label', `${a.name} ${hhmm(a.eta)} 도착 예정`)
  el.setAttribute('aria-pressed', String(selected))
}

const chip = (html: string) => {
  const el = document.createElement('div')
  el.style.cssText = 'pointer-events:none;padding:3px 9px;border-radius:9999px;font-size:12px;font-weight:700;white-space:nowrap;' +
    'background:var(--color-card);color:var(--color-ink);box-shadow:0 1px 4px rgba(0,0,0,.15)'
  el.innerHTML = html
  return el
}

export default function KakaoArrivalMap(p: Props) {
  const box = useRef<HTMLDivElement>(null)
  const k = useRef<K>(null)
  const map = useRef<K>(null)
  const tracks = useRef(new Map<number, Track>())
  const statics = useRef<{ star?: HTMLElement; badge?: K; badgeEl?: HTMLElement; truck?: K; truckEl?: HTMLElement; cluster?: K; clusterLabel?: K; clusterEl?: HTMLElement }>({})
  const prevArrived = useRef<number | null>(null)
  const [ready, setReady] = useState(false)
  const { place, onFail, onSelect } = p
  const selRef = useRef<number | null>(p.selected)
  selRef.current = p.selected

  // 지도: 한 번만 만든다. 위판장~앞바다 15km 고정, 끌기·확대 없음.
  useEffect(() => {
    let alive = true
    loadKakao().then((kakao) => {
      if (!alive || !box.current || map.current) return
      k.current = kakao
      map.current = new kakao.maps.Map(box.current, {
        center: new kakao.maps.LatLng(35.99, 129.62), level: 8, draggable: false, scrollwheel: false,
        disableDoubleClick: true, disableDoubleClickZoom: true, keyboardShortcuts: false,
      })
      map.current.setZoomable(false)
      kakao.maps.event.addListener(map.current, 'click', () => onSelect(null))
      setReady(true)
    }).catch((e: unknown) => { console.error(e); onFail() })
    return () => { alive = false }
  }, [onFail, onSelect])

  // 위판장 기준 화면 맞춤 + 별·입항 배지·트럭(위치 고정 요소)
  useEffect(() => {
    const kakao = k.current, m = map.current
    if (!ready || !kakao || !m || !place) return
    const b = new kakao.maps.LatLngBounds()
    b.extend(new kakao.maps.LatLng(place.lat + 0.03, place.lon - 0.015)) // 육지는 위판장 주변만
    b.extend(new kakao.maps.LatLng(place.lat - 0.035, place.lon + 0.16))  // 앞바다 약 15km(입항 판정 반경)
    m.setBounds(b, 8, 8, 8, 8)
    const pos = new kakao.maps.LatLng(place.lat, place.lon)

    const star = document.createElement('div')
    star.style.cssText = 'position:relative;width:26px;height:26px;display:grid;place-items:center;border-radius:9999px;' +
      'background:var(--color-card);box-shadow:0 1px 4px rgba(0,0,0,.2);font-size:17px;color:var(--color-primary-dark)'
    star.setAttribute('aria-label', '위판장'); star.title = place.name; star.textContent = '★'
    const starO = new kakao.maps.CustomOverlay({ position: pos, content: star, yAnchor: 0.5, zIndex: 5 })
    starO.setMap(m)

    const badgeEl = chip('')
    const badge = new kakao.maps.CustomOverlay({ position: pos, content: badgeEl, xAnchor: -0.15, yAnchor: 1.6, zIndex: 6 })
    const truckEl = chip('')
    // 트럭 표지는 위판장 바로 아래. 왼쪽은 화면 끝에서 잘리고, 오른쪽은 배가 들어오는 길목이다.
    const truck = new kakao.maps.CustomOverlay({ position: pos, content: truckEl, xAnchor: 0.35, yAnchor: -1.3, zIndex: 6 })
    statics.current = { ...statics.current, star, badge, badgeEl, truck, truckEl }
    return () => { starO.setMap(null); badge.setMap(null); truck.setMap(null) }
  }, [ready, place])

  // 입항 N척 배지 + 입항 순간 물결
  useEffect(() => {
    const s = statics.current
    if (!ready || !s.badge || !map.current) return
    if (p.arrivedCount > 0) { s.badgeEl!.innerHTML = `⚓ 입항 ${p.arrivedCount}척`; s.badge.setMap(map.current) } else s.badge.setMap(null)
    if (prevArrived.current !== null && p.arrivedCount > prevArrived.current && s.star && !reduceMotion()) {
      s.star.classList.remove('port-ripple'); void s.star.offsetWidth; s.star.classList.add('port-ripple')
    }
    prevArrived.current = p.arrivedCount
  }, [ready, p.arrivedCount])

  // 위판장 앞 트럭(교통센서3 실측)
  useEffect(() => {
    const s = statics.current
    if (!ready || !s.truck || !map.current) return
    if (!p.truck) { s.truck.setMap(null); return }
    s.truckEl!.innerHTML = `🚚 트럭 ${p.truck.perHour}대/시${p.truck.level ? ` · <span style="font-weight:500;color:var(--color-muted)">${p.truck.level}</span>` : ''}`
    s.truck.setMap(map.current)
  }, [ready, p.truck])

  // 조업 중(또는 미갱신) 배는 묶음 하나
  useEffect(() => {
    const kakao = k.current, m = map.current, s = statics.current
    if (!ready || !kakao || !m) return
    const idle = p.ships.filter((x) => x.status === '조업·대기' || x.status === '미갱신')
    s.cluster?.setMap(null); s.clusterLabel?.setMap(null)
    if (!idle.length) return
    const lat = idle.reduce((a, x) => a + x.lat, 0) / idle.length
    const lon = idle.reduce((a, x) => a + x.lon, 0) / idle.length
    const center = new kakao.maps.LatLng(lat, lon)
    const r = Math.min(3500, Math.max(900, ...idle.map((x) => Math.hypot((x.lat - lat) * 111000, (x.lon - lon) * 90000))))
    s.cluster = new kakao.maps.Circle({ center, radius: r * 0.75, strokeWeight: 1, strokeColor: '#8a9099', strokeOpacity: 0.5,
      strokeStyle: 'dash', fillColor: '#8a9099', fillOpacity: 0.12 })
    s.cluster.setMap(m)
    const stale = idle[0].status === '미갱신'
    s.clusterEl = chip(`${stale ? '선박 위치 미갱신' : '조업·대기'} ${idle.length}척`)
    s.clusterEl.style.color = 'var(--color-muted)'
    // 글씨는 원의 위쪽 가장자리에(가운데는 들어오는 배 표지와 겹친다)
    const top = new kakao.maps.LatLng(lat + (r * 0.75) / 111000, lon)
    s.clusterLabel = new kakao.maps.CustomOverlay({ position: top, content: s.clusterEl, yAnchor: 1.1, zIndex: 1 })
    s.clusterLabel.setMap(m)
  }, [ready, p.ships])

  // 들어오는 배: 배 모양 + ETA 표지 + 항로 점선. 2초 사이를 부드럽게 잇는다.
  useEffect(() => {
    const kakao = k.current, m = map.current
    if (!ready || !kakao || !m || !place) return
    const port = new kakao.maps.LatLng(place.lat, place.lon)
    const byId = new Map(p.ships.map((s) => [s.ship_id, s]))
    const now = performance.now()
    const seen = new Set<number>()
    p.arriving.forEach((a, i) => {
      seen.add(a.ship_id)
      const s = byId.get(a.ship_id)
      const to: [number, number] = [s?.lat ?? a.lat, s?.lon ?? a.lon]
      let t = tracks.current.get(a.ship_id)
      if (!t) {
        const id = a.ship_id
        const el = boatEl(() => onSelect(selRef.current === id ? null : id)) // 같은 배 다시 탭 → 해제
        const pos = new kakao.maps.LatLng(to[0], to[1])
        const o = new kakao.maps.CustomOverlay({ position: pos, content: el, xAnchor: 0.06, yAnchor: 0.5, zIndex: 10 })
        const line = new kakao.maps.Polyline({ path: [pos, port], strokeWeight: 2, strokeColor: '#0072de', strokeOpacity: 0.35, strokeStyle: 'shortdash' })
        line.setMap(m); o.setMap(m)
        t = { o, line, el, from: to, to, t0: now }
        tracks.current.set(a.ship_id, t)
      } else {
        const cur = lerpPos(t, now)
        t.from = cur; t.to = to; t.t0 = now
      }
      const sel = p.selected === a.ship_id
      paintBoat(t.el, a, s?.course ?? null, sel, i)
      t.o.setZIndex?.(sel ? 30 : 20 - Math.min(i, 9))
    })
    for (const [id, t] of tracks.current) if (!seen.has(id)) { t.o.setMap(null); t.line.setMap(null); tracks.current.delete(id) }
  }, [ready, place, p.arriving, p.ships, p.selected, onSelect])

  // 애니메이션 루프
  useEffect(() => {
    const kakao = k.current
    if (!ready || !kakao || !place) return
    const port = new kakao.maps.LatLng(place.lat, place.lon)
    let raf = 0
    const tick = () => {
      const now = performance.now()
      for (const t of tracks.current.values()) {
        const [la, lo] = lerpPos(t, now)
        const pos = new kakao.maps.LatLng(la, lo)
        t.o.setPosition(pos); t.line.setPath([pos, port])
      }
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [ready, place])

  return (
    <div className="relative">
      <div ref={box} className="h-80 w-full overflow-hidden rounded-card bg-primary-soft md:h-[460px]" aria-label="입항 지도" />
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
          <span><span aria-hidden style={{ color: 'var(--color-arriving)' }}>▲</span> 들어오는 배</span>
          <span><span aria-hidden>⚓</span> 입항</span>
          <span><span aria-hidden style={{ color: 'var(--color-idle)' }}>◌</span> 조업·대기</span>
        </div>
      </div>
    </div>
  )
}

function lerpPos(t: Track, now: number): [number, number] {
  if (reduceMotion()) return t.to
  const f = Math.min(1, (now - t.t0) / POLL_MS)
  return [t.from[0] + (t.to[0] - t.from[0]) * f, t.from[1] + (t.to[1] - t.from[1]) * f]
}
