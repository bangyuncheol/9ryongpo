import { useCallback, useState } from 'react'
import type { Arrival, Place, Ship } from '../api'
import KakaoShipMap from './KakaoShipMap'
import ShipMap from './ShipMap'

/** 지도 선택: 카카오맵 우선(10/10 결정). 키가 없거나 불러오기에 실패하면 기존 지도(Leaflet+OSM)로 자동 전환. */
export default function MapView(props: { place: Place | null; ships: Ship[]; arriving: Arrival[] }) {
  const [fallback, setFallback] = useState(!import.meta.env.VITE_KAKAO_MAP_KEY)
  const onFail = useCallback(() => setFallback(true), [])
  return fallback ? <ShipMap {...props} /> : <KakaoShipMap {...props} onFail={onFail} />
}
