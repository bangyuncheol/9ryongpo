import L from 'leaflet'
import { useEffect, useRef } from 'react'
import { CircleMarker, MapContainer, Marker, TileLayer, Tooltip, useMap } from 'react-leaflet'
import type { Arrival, Place, Ship } from '../api'
import { hhmm } from '../api'

const COLOR: Record<Ship['status'], string> = {
  '입항 중': 'var(--color-arriving)',
  '입항': 'var(--color-arrived)',
  '조업·대기': 'var(--color-idle)',
  '미갱신': 'var(--color-idle)',
}

const placeIcon = L.divIcon({
  className: '',
  html: '<div aria-label="위판장" style="font-size:22px;line-height:22px;color:var(--color-primary-dark)">★</div>',
  iconSize: [22, 22], iconAnchor: [11, 11],
})

/** 처음 데이터가 오면 한 번만 위판장과 배 전체가 보이게 맞춘다. 이후엔 사용자가 움직인 화면을 존중한다. */
function FitOnce({ points }: { points: [number, number][] }) {
  const map = useMap()
  const done = useRef(false)
  useEffect(() => {
    if (done.current || points.length < 2) return
    map.fitBounds(L.latLngBounds(points), { padding: [24, 24], animate: false })
    done.current = true
  }, [map, points])
  return null
}

type Props = { place: Place | null; ships: Ship[]; arriving: Arrival[] }

export default function ShipMap({ place, ships, arriving }: Props) {
  const center: [number, number] = place ? [place.lat, place.lon + 0.045] : [35.99, 129.6]
  const eta = new Map(arriving.map((a) => [a.ship_id, a.eta]))
  // 라벨은 바로 다음에 들어올 1척만 항상 표시(항구 근처에 몰리면 겹침, 10/10). 나머지는 점을 누르면(폰은 탭) 보인다.
  const labeled = new Set(arriving.slice(0, 1).map((a) => a.ship_id))
  return (
    <div className="relative">
    {/* 지도는 고정(10/10): 끌기·확대 없음. 폰에서 페이지를 내릴 때 지도만 움직이는 문제도 없앤다. 배 점 탭은 그대로. */}
    <MapContainer center={center} zoom={12} className="h-72 w-full rounded-card md:h-[440px]"
      dragging={false} touchZoom={false} doubleClickZoom={false} scrollWheelZoom={false}
      boxZoom={false} keyboard={false} zoomControl={false}>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <FitOnce points={place && ships.length ? [[place.lat, place.lon], ...ships.map((s) => [s.lat, s.lon] as [number, number])] : []} />
      {place && (
        <Marker position={[place.lat, place.lon]} icon={placeIcon}>
          <Tooltip>{place.name}</Tooltip>
        </Marker>
      )}
      {ships.map((s) => (
        <CircleMarker
          key={s.ship_id}
          center={[s.lat, s.lon]}
          radius={s.status === '입항 중' || s.status === '입항' ? 7 : 4}
          pathOptions={{ color: COLOR[s.status], fillColor: COLOR[s.status], fillOpacity: 0.85, weight: 1 }}
        >
          <Tooltip permanent={labeled.has(s.ship_id)} direction="top" offset={[0, -6]}>
            {s.status === '입항 중' ? `${hhmm(eta.get(s.ship_id))} ${s.name}` : `${s.name} · ${s.biz ?? '업종 미상'} · ${s.status}`}
          </Tooltip>
        </CircleMarker>
      ))}
    </MapContainer>
    <Legend />
    </div>
  )
}

/** 지도 범례. 색만으로 뜻을 전하지 않도록(One UI 접근성) 기호와 글자를 함께 둔다. 확대 버튼(좌상)·출처(우하)와 겹치지 않게 좌하.
 *  교통 센서는 손님에게 필요 없어 지도·범례에서 뺐다(10/10). 출처는 교통 카드 문구가 설명한다. */
export function Legend({ position = 'bottom-left' }: { position?: 'bottom-left' | 'top-left' }) {
  const dot = (c: string, big = false) => (
    <span aria-hidden className="inline-block rounded-full" style={{ background: c, width: big ? 10 : 7, height: big ? 10 : 7 }} />
  )
  const row = 'flex items-center gap-1.5'
  return (
    <div className={`pointer-events-none absolute left-2 z-[500] rounded-button bg-card/90 px-3 py-2 text-[12px] leading-5 text-ink shadow-sm ${position === 'top-left' ? 'top-2' : 'bottom-2'}`}>
      <p className="sr-only">지도 범례</p>
      <div className="flex flex-wrap gap-x-3">
        <span className={row}><span aria-hidden style={{ color: 'var(--color-primary-dark)' }}>★</span>위판장</span>
      </div>
      <div className="flex flex-wrap gap-x-3">
        <span className={row}>{dot('var(--color-arriving)', true)}입항 중</span>
        <span className={row}>{dot('var(--color-arrived)', true)}입항</span>
        <span className={row}>{dot('var(--color-idle)')}조업·대기</span>
      </div>
    </div>
  )
}
