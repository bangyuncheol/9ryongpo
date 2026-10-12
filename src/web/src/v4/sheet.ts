// 버전 4 하단 시트의 단 높이 계산(BottomSheet·AppV4 공용, 10/11)
import { useEffect, useState } from 'react'

export type Snap = 'peek' | 'mid' | 'full'
const HEADER = 52 // 위 헤더 띠 높이(AppV4 와 같아야 한다)
const GAP = 8 // 다 펼쳐도 헤더와 시트 사이에 남기는 틈
const PEEK = 92 // 손잡이 44 + 한 줄 요약

/**
 * fit: 지금 장의 내용이 다 들어가는 시트 높이(10/12 오너: 고정 높이라 카드·버튼이 중간에 잘려 보였다).
 * 주면 기본 높이를 거기에 맞추되 지도가 남게 화면의 60%를 넘지 않는다. 넘치는 장은 안에서 스크롤(아래가 흐려짐).
 */
export function snapHeights(vh: number, fit?: number): Record<Snap, number> {
  const full = vh - HEADER - GAP
  const cap = Math.min(full - 80, Math.round(vh * 0.6))
  const mid = fit ? Math.min(cap, Math.max(220, Math.ceil(fit))) : Math.min(full - 80, Math.max(340, Math.round(vh * 0.44)))
  return { peek: PEEK, mid, full }
}

export function useViewportHeight() {
  const [vh, setVh] = useState(() => window.innerHeight)
  useEffect(() => {
    const on = () => setVh(window.innerHeight)
    window.addEventListener('resize', on)
    return () => window.removeEventListener('resize', on)
  }, [])
  return vh
}
