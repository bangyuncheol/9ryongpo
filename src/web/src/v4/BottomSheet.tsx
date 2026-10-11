import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'

/*
 * 버전 4 폰 하단 시트(10/11 오너 요청) — 멈춤 위치 3단: 내림(한 줄) · 기본 · 다 펼침.
 * 지도는 늘 전체 화면이고 시트가 그 위를 덮는다(지도 크기가 바뀌지 않아 다시 그릴 필요 없음).
 * - 끌기: 손을 뗀 위치 + 속도로 가까운 단에 붙는다(빠르게 올리면 한 단 건너뜀).
 * - 다 펼침에서는 안쪽이 스크롤되므로 손잡이로만 끌어내린다.
 * - 끌기 대안: 손잡이 탭(기본↔내림), 트랙패드·휠(아래로=펼침, 위로=접음). 라이브러리 없이 포인터 이벤트만.
 */
import { snapHeights, useViewportHeight } from './sheet'
import type { Snap } from './sheet'

type Gesture = { id: number; y0: number; v0: number; lastY: number; lastT: number; vel: number; vis: number; active: boolean }

export default function BottomSheet({ snap, onSnap, peek, children }: {
  snap: Snap; onSnap: (s: Snap) => void
  /** 내림 상태에서 손잡이 아래 보이는 한 줄 */ peek: ReactNode
  children: ReactNode
}) {
  const hs = snapHeights(useViewportHeight())
  const [drag, setDrag] = useState<number | null>(null) // 끄는 중의 보이는 높이
  const g = useRef<Gesture | null>(null)
  const dragged = useRef(false) // 끈 직후의 click 은 버튼을 누른 것이 아니다
  const scroller = useRef<HTMLDivElement>(null)
  const wheelUntil = useRef(0)
  const visible = drag ?? hs[snap]

  useEffect(() => { if (snap !== 'full' && scroller.current) scroller.current.scrollTop = 0 }, [snap])

  // 손을 뗀 곳에서 속도만큼 더 간 위치(투사)에 가장 가까운 단
  const settle = (vis: number, vel: number) => {
    const target = vis + vel * 200
    const best = (['peek', 'mid', 'full'] as Snap[]).reduce((a, b) => (Math.abs(hs[b] - target) < Math.abs(hs[a] - target) ? b : a))
    onSnap(best)
  }

  // 누른 뒤의 움직임은 창 전체에서 받는다: 빠르게 끌어 손가락·커서가 시트를 벗어나도 놓치지 않고,
  // 포인터를 붙잡지(capture) 않으니 시트 안 버튼의 click 도 그대로 간다(10/11 마우스 끌기 재현으로 고침)
  const onPointerDown = (e: React.PointerEvent<HTMLElement>) => {
    if (e.button !== 0) return
    if (snap === 'full' && !(e.target as HTMLElement).closest('[data-sheet-handle]')) return // 펼침에선 안쪽 스크롤 우선
    const s: Gesture = { id: e.pointerId, y0: e.clientY, v0: visible, lastY: e.clientY, lastT: e.timeStamp, vel: 0, vis: visible, active: false }
    g.current = s
    dragged.current = false
    const move = (ev: PointerEvent) => {
      if (ev.pointerId !== s.id) return
      const dy = s.y0 - ev.clientY // 위로 끌면 +
      if (!s.active) {
        if (Math.abs(dy) < 6) return // 이 정도는 탭으로 본다
        s.active = true; dragged.current = true
        window.getSelection()?.removeAllRanges() // 마우스로 끌 때 글자가 선택돼 칠해지지 않게
      }
      const dt = Math.max(1, ev.timeStamp - s.lastT)
      s.vel = (s.lastY - ev.clientY) / dt
      s.lastY = ev.clientY; s.lastT = ev.timeStamp
      s.vis = Math.min(hs.full, Math.max(hs.peek - 24, s.v0 + dy))
      setDrag(s.vis)
    }
    const end = (ev: PointerEvent) => {
      if (ev.pointerId !== s.id) return
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', end)
      window.removeEventListener('pointercancel', end)
      g.current = null
      if (!s.active) return
      if (ev.type === 'pointerup') settle(s.vis, s.vel)
      setDrag(null)
      setTimeout(() => { dragged.current = false }, 0) // 끈 뒤 click 이 안 오는 경우에도 다음 탭은 살린다
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
    const atTop = (scroller.current?.scrollTop ?? 0) <= 0
    if (e.deltaY > 0 && snap !== 'full') onSnap(snap === 'peek' ? 'mid' : 'full')
    else if (e.deltaY < 0 && (snap !== 'full' || atTop)) onSnap(snap === 'full' ? 'mid' : 'peek')
    else return
    wheelUntil.current = e.timeStamp + 450 // 관성 스크롤 한 번에 여러 단을 넘지 않게
  }
  const tapHandle = () => onSnap(snap === 'mid' ? 'peek' : 'mid')

  return (
    <section aria-label="입항 정보"
      className={`v4-sheet fixed inset-x-0 bottom-0 z-30 flex flex-col rounded-t-[24px] bg-card ${drag === null ? 'v4-sheet-anim' : ''}`}
      style={{ height: hs.full, transform: `translateY(${hs.full - visible}px)`, touchAction: snap === 'full' ? 'auto' : 'none', userSelect: drag === null ? undefined : 'none' }}
      onPointerDown={onPointerDown}
      onClickCapture={onClickCapture} onWheel={onWheel}>
      <button type="button" data-sheet-handle onClick={tapHandle} style={{ touchAction: 'none' }}
        aria-label={snap === 'peek' ? '입항 정보 펼치기' : '시트 내리고 지도 보기'} aria-expanded={snap !== 'peek'}
        className="flex h-11 w-full shrink-0 cursor-grab items-center justify-center rounded-t-[24px] active:cursor-grabbing">
        <span aria-hidden className="h-1.5 w-10 rounded-full bg-line" />
      </button>
      {snap === 'peek' && peek}
      <div ref={scroller} className={`min-h-0 flex-1 ${snap === 'full' ? 'overflow-y-auto overscroll-contain' : 'overflow-hidden'}`}>
        {children}
      </div>
    </section>
  )
}
