import { useCallback, useState } from 'react'
import type { Arrival, Place, SensorTraffic, Ship } from '../api'
import KakaoArrivalMap from './KakaoArrivalMap'
import ShipMap from './ShipMap'

/** 지도 선택: 카카오맵 우선(10/10 결정). 키가 없거나 불러오기에 실패하면 기존 지도(Leaflet+OSM)로 자동 전환. */
type Props = {
  place: Place | null; ships: Ship[]; arriving: Arrival[]; arrivedCount: number
  truck: { perHour: number; level: string | null } | null; trucks: SensorTraffic[]; sensor: { lat: number; lon: number } | null
  notice: string | null; selected: number | null; onSelect: (id: number | null) => void
  legendToggle?: boolean // 2차 시안: 범례를 접어 두고 버튼으로 연다(카카오 지도만)
}

export default function MapView(props: Props) {
  const [fallback, setFallback] = useState(!import.meta.env.VITE_KAKAO_MAP_KEY)
  const onFail = useCallback(() => setFallback(true), [])
  return fallback
    ? <ShipMap place={props.place} ships={props.ships} arriving={props.arriving} />
    : <KakaoArrivalMap {...props} onFail={onFail} />
}
