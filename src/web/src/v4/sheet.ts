// 버전 4 하단 시트의 단 높이 계산(BottomSheet·AppV4 공용, 10/11)
import { useEffect, useState } from 'react'

export type Snap = 'peek' | 'mid' | 'full'
const HEADER = 52 // 위 헤더 띠 높이(AppV4 와 같아야 한다)
const GAP = 8 // 다 펼쳐도 헤더와 시트 사이에 남기는 틈
const PEEK = 92 // 손잡이 44 + 한 줄 요약

export function snapHeights(vh: number): Record<Snap, number> {
  const full = vh - HEADER - GAP
  const mid = Math.min(full - 80, Math.max(340, Math.round(vh * 0.44)))
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
