import L from 'leaflet'
import { CircleMarker, MapContainer, Marker, TileLayer, Tooltip } from 'react-leaflet'
import type { Arrival, Place, Sensor, Ship } from '../api'
import { hhmm } from '../api'

const COLOR: Record<Ship['status'], string> = {
  '입항 중': 'var(--color-arriving)',
  '입항': 'var(--color-arrived)',
  '조업·대기': 'var(--color-idle)',
}

const placeIcon = L.divIcon({
  className: '',
  html: '<div aria-label="위판장" style="font-size:22px;line-height:22px;color:var(--color-sea)">★</div>',
  iconSize: [22, 22], iconAnchor: [11, 11],
})
const sensorIcon = L.divIcon({
  className: '',
  html: '<div aria-label="교통 센서" style="font-size:12px;line-height:12px;color:var(--color-muted)">▲</div>',
  iconSize: [12, 12], iconAnchor: [6, 6],
})

type Props = { place: Place | null; sensors: Sensor[]; ships: Ship[]; arriving: Arrival[] }

export default function ShipMap({ place, sensors, ships, arriving }: Props) {
  const center: [number, number] = place ? [place.lat, place.lon + 0.045] : [35.99, 129.6]
  const eta = new Map(arriving.map((a) => [a.ship_id, a.eta]))
  return (
    <MapContainer center={center} zoom={12} scrollWheelZoom={false} className="h-72 w-full rounded-xl md:h-96">
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {place && (
        <Marker position={[place.lat, place.lon]} icon={placeIcon}>
          <Tooltip>{place.name}</Tooltip>
        </Marker>
      )}
      {sensors.map((s) => (
        <Marker key={s.id} position={[s.lat, s.lon]} icon={sensorIcon}>
          <Tooltip>{s.name}{s.nickname ? ` · ${s.nickname}` : ''} ({s.dist_m}m)</Tooltip>
        </Marker>
      ))}
      {ships.map((s) => (
        <CircleMarker
          key={s.ship_id}
          center={[s.lat, s.lon]}
          radius={s.status === '조업·대기' ? 4 : 7}
          pathOptions={{ color: COLOR[s.status], fillColor: COLOR[s.status], fillOpacity: 0.85, weight: 1 }}
        >
          <Tooltip permanent={s.status === '입항 중'} direction="top" offset={[0, -6]}>
            {s.status === '입항 중' ? `${hhmm(eta.get(s.ship_id))} ${s.name}` : `${s.name} · ${s.biz ?? '업종 미상'} · ${s.status}`}
          </Tooltip>
        </CircleMarker>
      ))}
    </MapContainer>
  )
}
