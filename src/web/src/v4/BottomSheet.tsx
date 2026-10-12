import { useRef, useState } from 'react'
import type { ReactNode } from 'react'

/*
 * 버전 4 폰 하단 시트. 지도는 늘 전체 화면이고 시트가 그 위를 덮는다(지도 크기가 바뀌지 않아 다시 그릴 필요 없음).
 * 10/12 오너: 끝까지 끌어올려 지도를 가리는 단을 뺐다(지도와 같이 보고 싶다는 피드백). 단은 둘 — 내림(한 줄) · 기본.
 * 10/13 오너: 입력칸을 눌러도 끝까지 올라가지 않는다(전엔 입력 중에만 다 펼쳤음). 키보드가 뜨면 화면 높이가 줄어
 * 시트 높이도 그에 맞춰 다시 잰다.
 * - 끌기는 손잡이·한 줄 요약에서만. 안쪽(옆으로 넘기는 장)은 자기 스크롤·옆 밀기를 쓴다.
 * - 손을 뗀 위치 + 속도로 가까운 단에 붙는다. 끌기 대안: 손잡이 탭(기본↔내림), 손잡이 위 휠.
 * 라이브러리 없이 포인터 이벤트만(움직임은 창 전체에서 받는다).
 */
import { snapHeights, useViewportHeight } from './sheet'
import type { Snap } from './sheet'

type Gesture = { id: number; y0: number; v0: number; lastY: number; lastT: number; vel: number; vis: number; active: boolean }
const USER_SNAPS: Snap[] = ['peek', 'mid']
export const HANDLE_H = 44

export default function BottomSheet({ snap, onSnap, peek, fit, children }: {
  snap: Snap; onSnap: (s: Snap) => void
  /** 지금 장 내용이 다 들어가는 높이(기본 단을 여기에 맞춘다) */ fit?: number
  /** 내림 상태에서 손잡이 아래 보이는 한 줄 */ peek: ReactNode
  /** 지금 보이는 높이(손잡이 제외)를 받아 그린다 */ children: (bodyHeight: number) => ReactNode
}) {
  const hs = snapHeights(useViewportHeight(), fit)
  const [drag, setDrag] = useState<number | null>(null) // 끄는 중의 보이는 높이
  const dragged = useRef(false) // 끈 직후의 click 은 버튼을 누른 것이 아니다
  const wheelUntil = useRef(0)
  const visible = drag ?? hs[snap]

  const settle = (vis: number, vel: number) => {
    const target = vis + vel * 200
    onSnap(USER_SNAPS.reduce((a, b) => (Math.abs(hs[b] - target) < Math.abs(hs[a] - target) ? b : a)))
  }

  const onPointerDown = (e: React.PointerEvent<HTMLElement>) => {
    if (e.button !== 0) return
    const s: Gesture = { id: e.pointerId, y0: e.clientY, v0: visible, lastY: e.clientY, lastT: e.timeStamp, vel: 0, vis: visible, active: false }
    dragged.current = false
    const top = Math.max(hs.mid, visible)
    const move = (ev: PointerEvent) => {
      if (ev.pointerId !== s.id) return
      const dy = s.y0 - ev.clientY // 위로 끌면 +
      if (!s.active) {
        if (Math.abs(dy) < 6) return // 이 정도는 탭으로 본다
        s.active = true; dragged.current = true
        window.getSelection()?.removeAllRanges()
      }
      const dt = Math.max(1, ev.timeStamp - s.lastT)
      s.vel = (s.lastY - ev.clientY) / dt
      s.lastY = ev.clientY; s.lastT = ev.timeStamp
      const raw = s.v0 + dy
      // 기본 높이 위로는 고무줄처럼 조금만(더 올라가는 단이 없다는 표시)
      s.vis = raw > top ? top + Math.min(40, (raw - top) * 0.25) : Math.max(hs.peek - 24, raw)
      setDrag(s.vis)
    }
    const end = (ev: PointerEvent) => {
      if (ev.pointerId !== s.id) return
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', end)
      window.removeEventListener('pointercancel', end)
      if (!s.active) return
      if (ev.type === 'pointerup') settle(s.vis, s.vel)
      setDrag(null)
      setTimeout(() => { dragged.current = false }, 0)
    }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', end)
    window.addEventListener('pointercancel', end)
  }
  const onClickCapture = (e: React.MouseEvent) => {
    if (!dragged.current) return
    dragged.current = false
    e.preventDefault(); e.stopPropagation()
  }
  const onWheel = (e: React.WheelEvent) => {
    if (e.timeStamp < wheelUntil.current || Math.abs(e.deltaY) < 8) return
    if (e.deltaY > 0 && snap === 'peek') onSnap('mid')
    else if (e.deltaY < 0 && snap === 'mid') onSnap('peek')
    else return
    wheelUntil.current = e.timeStamp + 450
  }
  const tapHandle = () => onSnap(snap === 'peek' ? 'mid' : 'peek')
  const drag_ = { onPointerDown, onWheel, style: { touchAction: 'none' as const } }

  return (
    <section aria-label="입항 정보"
      className={`v4-sheet fixed inset-x-0 bottom-0 z-30 flex flex-col rounded-t-[24px] bg-card ${drag === null ? 'v4-sheet-anim' : ''}`}
      style={{ height: hs.full, transform: `translateY(${hs.full - visible}px)`, userSelect: drag === null ? undefined : 'none' }}
      onClickCapture={onClickCapture}>
      <button type="button" onClick={tapHandle} {...drag_}
        aria-label={snap === 'peek' ? '입항 정보 펼치기' : '시트 내리고 지도 보기'} aria-expanded={snap !== 'peek'}
        className="flex h-11 w-full shrink-0 cursor-grab items-center justify-center rounded-t-[24px] active:cursor-grabbing">
        <span aria-hidden className="h-1.5 w-10 rounded-full bg-line" />
      </button>
      {snap === 'peek' && <div {...drag_}>{peek}</div>}
      <div className="min-h-0 flex-1">{children(Math.max(0, visible - HANDLE_H))}</div>
    </section>
  )
}
