import { useEffect, useRef, useState } from 'react'
import type { Arrival, Place, Ship } from '../api'
import { hhmm } from '../api'
import { Legend } from './ShipMap'

/* 카카오맵 JavaScript SDK 타입(필요한 것만). */
type KMap = {
  setBounds: (b: unknown, t?: number, r?: number, bt?: number, l?: number) => void
  setZoomable: (z: boolean) => void
  relayout: () => void
}
type KOverlay = { setMap: (m: KMap | null) => void; setPosition: (p: unknown) => void; setContent: (c: HTMLElement) => void }
type Kakao = {
  maps: {
    load: (cb: () => void) => void
    LatLng: new (lat: number, lng: number) => unknown
    LatLngBounds: new () => { extend: (p: unknown) => void }
    Map: new (el: HTMLElement, opt: Record<string, unknown>) => KMap
    CustomOverlay: new (opt: Record<string, unknown>) => KOverlay
  }
}
declare global { interface Window { kakao?: Kakao } }

const KEY = import.meta.env.VITE_KAKAO_MAP_KEY
let loading: Promise<Kakao> | null = null

/** SDK를 한 번만 불러온다. 8초 안에 못 불러오면 실패(호출한 쪽이 기존 지도로 돌아감). */
export function loadKakao(): Promise<Kakao> {
  if (!KEY) return Promise.reject(new Error('VITE_KAKAO_MAP_KEY 없음'))
  if (loading) return loading
  loading = new Promise<Kakao>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('카카오맵 SDK 시간 초과')), 8000)
    const done = () => window.kakao!.maps.load(() => { clearTimeout(timer); resolve(window.kakao!) })
    if (window.kakao?.maps) return done()
    const s = document.createElement('script')
    s.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${KEY}&autoload=false`
    s.async = true
    s.onload = () => (window.kakao?.maps ? done() : reject(new Error('카카오맵 SDK 응답 이상(도메인 등록·사용 설정 확인)')))
    s.onerror = () => { clearTimeout(timer); reject(new Error('카카오맵 SDK를 불러오지 못함')) }
    document.head.appendChild(s)
  })
  loading.catch(() => { loading = null })
  return loading
}

const COLOR: Record<Ship['status'], string> = {
  '입항 중': 'var(--color-arriving)', '입항': 'var(--color-arrived)',
  '조업·대기': 'var(--color-idle)', '미갱신': 'var(--color-idle)',
}

function dotEl(s: Ship, onPick: () => void) {
  const big = s.status === '입항 중' || s.status === '입항'
  const el = document.createElement('button')
  el.type = 'button'
  el.setAttribute('aria-label', `${s.name ?? '배'} ${s.status}`)
  const size = big ? 14 : 9
  el.style.cssText = `width:${size}px;height:${size}px;border-radius:50%;padding:0;cursor:pointer;` +
    `background:${COLOR[s.status]};border:1.5px solid rgba(255,255,255,.9);box-shadow:0 0 0 1px rgba(0,0,0,.15)`
  el.addEventListener('click', onPick)
  el.addEventListener('mouseenter', onPick)
  return el
}

function labelEl(text: string) {
  const el = document.createElement('div')
  el.textContent = text
  el.style.cssText = 'margin-bottom:12px;padding:3px 8px;border-radius:8px;font-size:12px;white-space:nowrap;' +
    'background:var(--color-card);color:var(--color-ink);border:1px solid var(--color-line);box-shadow:0 1px 3px rgba(0,0,0,.15)'
  return el
}

type Props = { place: Place | null; ships: Ship[]; arriving: Arrival[]; onFail: () => void }

/** 카카오맵 버전. 동작은 기존 지도와 같다: 처음 한 번 위판장·배 전체에 맞춘 뒤 고정, 다음 입항 1척 라벨, 점을 누르면 정보. */
export default function KakaoShipMap({ place, ships, arriving, onFail }: Props) {
  const box = useRef<HTMLDivElement>(null)
  const kakao = useRef<Kakao | null>(null)
  const map = useRef<KMap | null>(null)
  const dots = useRef(new Map<number, KOverlay>())
  const label = useRef<KOverlay | null>(null)
  const fitted = useRef(false)
  const [picked, setPicked] = useState<number | null>(null)
  const [ready, setReady] = useState(false)

  // 지도는 한 번만 만든다(위판장 정보가 늦게 와도 다시 만들지 않음 — 다시 만들면 점이 옛 지도에 붙는다, 10/10).
  useEffect(() => {
    let alive = true
    loadKakao().then((k) => {
      if (!alive || !box.current || map.current) return
      kakao.current = k
      const center = new k.maps.LatLng(35.99, 129.6)
      map.current = new k.maps.Map(box.current, {
        center, level: 8, draggable: false, scrollwheel: false, disableDoubleClick: true,
        disableDoubleClickZoom: true, keyboardShortcuts: false,
      })
      map.current.setZoomable(false) // 지도 고정(10/10)
      setReady(true)
    }).catch((e) => { console.error(e); onFail() })
    return () => { alive = false }
  }, [onFail])

  // 위판장 별
  useEffect(() => {
    const k = kakao.current, m = map.current
    if (!ready || !k || !m || !place) return
    const el = document.createElement('div')
    el.setAttribute('aria-label', '위판장')
    el.title = place.name
    el.textContent = '★'
    el.style.cssText = 'font-size:22px;line-height:22px;color:var(--color-primary-dark);text-shadow:0 0 3px #fff'
    const o = new k.maps.CustomOverlay({ position: new k.maps.LatLng(place.lat, place.lon), content: el, yAnchor: 0.5, zIndex: 3 })
    o.setMap(m)
    return () => o.setMap(null)
  }, [ready, place])

  // 배 점: 2초마다 위치·상태 갱신
  useEffect(() => {
    const k = kakao.current, m = map.current
    if (!ready || !k || !m) return
    const seen = new Set<number>()
    for (const s of ships) {
      seen.add(s.ship_id)
      const pos = new k.maps.LatLng(s.lat, s.lon)
      const content = dotEl(s, () => setPicked(s.ship_id))
      const o = dots.current.get(s.ship_id)
      if (o) { o.setPosition(pos); o.setContent(content) } else {
        const n = new k.maps.CustomOverlay({ position: pos, content, yAnchor: 0.5, xAnchor: 0.5, zIndex: s.status === '조업·대기' ? 1 : 2 })
        n.setMap(m); dots.current.set(s.ship_id, n)
      }
    }
    for (const [id, o] of dots.current) if (!seen.has(id)) { o.setMap(null); dots.current.delete(id) }
    if (!fitted.current && place && ships.length) {
      const b = new k.maps.LatLngBounds()
      b.extend(new k.maps.LatLng(place.lat, place.lon))
      ships.forEach((s) => b.extend(new k.maps.LatLng(s.lat, s.lon)))
      m.setBounds(b, 24, 24, 24, 24)
      fitted.current = true
    }
  }, [ready, ships, place])

  // 누른 배 정보는 5초 뒤 사라지고 다음 입항 라벨로 돌아간다(10/10).
  useEffect(() => {
    if (picked === null) return
    const id = setTimeout(() => setPicked(null), 5000)
    return () => clearTimeout(id)
  }, [picked])

  // 라벨: 고른 배가 있으면 그 배, 없으면 다음에 들어올 1척
  useEffect(() => {
    const k = kakao.current, m = map.current
    if (!ready || !k || !m) return
    label.current?.setMap(null)
    const eta = new Map(arriving.map((a) => [a.ship_id, a.eta]))
    const s = ships.find((x) => x.ship_id === picked) ?? ships.find((x) => x.ship_id === arriving[0]?.ship_id)
    if (!s) return
    const text = eta.has(s.ship_id) ? `${hhmm(eta.get(s.ship_id))} ${s.name}` : `${s.name} · ${s.biz ?? '업종 미상'} · ${s.status}`
    label.current = new k.maps.CustomOverlay({ position: new k.maps.LatLng(s.lat, s.lon), content: labelEl(text), yAnchor: 1, zIndex: 4 })
    label.current.setMap(m)
  }, [ready, ships, arriving, picked])

  return (
    <div className="relative">
      <div ref={box} className="h-72 w-full overflow-hidden rounded-card bg-primary-soft md:h-[440px]" aria-label="입항 지도" />
      {/* 카카오 로고(좌하)·저작권(우하)을 가리지 않게 범례는 좌상 */}
      <Legend position="top-left" />
    </div>
  )
}
