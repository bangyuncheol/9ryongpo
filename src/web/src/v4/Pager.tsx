import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'

/*
 * 버전 4 폰 시트의 옆으로 넘기는 장(10/12 오너). 위 글자 탭을 누르거나 옆으로 밀어 넘긴다.
 * - 순환하지 않는다: 첫 장·끝 장에서 더 밀면 고무줄처럼 조금만 따라오다 '팅' 돌아온다(지도 범위 튕김과 같은 감각).
 * - 손가락은 touch-action: pan-y 로 위아래 스크롤은 브라우저에 맡기고 옆 움직임만 받는다. 마우스로도 끌 수 있다.
 * - 장마다 안쪽이 위아래로 스크롤된다(시트 높이는 그대로, 지도가 늘 보이게).
 * 라이브러리 없이 포인터 이벤트만(npm 의존성 금지).
 */
const FADE = 'linear-gradient(to bottom, #000 calc(100% - 48px), transparent)'

type Drag = { id: number; x0: number; y0: number; lastX: number; lastT: number; vel: number; axis: 'x' | 'y' | null }

export default function Pager({ tabs, page, onPage, height, onContentHeight, noFade = [], children }: {
  tabs: string[]; page: number; onPage: (i: number) => void
  /** 아래 흐림을 쓰지 않는 장(물어보기: 입력칸이 아래에 붙어 있다) */ noFade?: number[]
  /** 지금 장 내용의 높이(시트 기본 높이를 맞추는 데 쓴다) */ onContentHeight?: (h: number) => void
  /** 장이 보이는 높이(px). 시트에서 손잡이·탭을 뺀 만큼 */ height: number
  children: ReactNode[]
}) {
  const box = useRef<HTMLDivElement>(null)
  const [dx, setDx] = useState<number | null>(null) // 끄는 중 옆으로 움직인 거리
  const dragged = useRef(false)
  const panels = useRef<(HTMLDivElement | null)[]>([])
  const wheel = useRef({ sum: 0, lockUntil: 0, last: 0 })
  const n = tabs.length

  // 다른 장으로 가면 그 장은 맨 위부터
  useEffect(() => { panels.current[page]?.scrollTo({ top: 0 }) }, [page])

  // 지금 장 내용 높이를 재서 알린다(내용이 바뀌면 다시: 칩 펼치기·번호 칸·질문 답)
  const [contentH, setContentH] = useState<number[]>([])
  useEffect(() => {
    const ro = new ResizeObserver(() => setContentH(panels.current.map((el) => (el?.firstElementChild as HTMLElement | null)?.offsetHeight ?? 0)))
    panels.current.forEach((el) => { const c = el?.firstElementChild; if (c) ro.observe(c) })
    return () => ro.disconnect()
  }, [n])
  useEffect(() => { if (contentH[page]) onContentHeight?.(contentH[page]) }, [contentH, page, onContentHeight])

  // 장이 넘쳐 아래가 남았으면 아래를 흐리게(칼로 자른 듯 잘려 보이지 않게, 더 있다는 표시)
  const [more, setMore] = useState(false)
  const checkMore = () => { const el = panels.current[page]; setMore(!!el && el.scrollHeight - el.scrollTop - el.clientHeight > 4) }
  useEffect(checkMore)

  const onPointerDown = (e: React.PointerEvent) => {
    if (e.pointerType === 'mouse' && e.button !== 0) return
    if ((e.target as HTMLElement).closest('input, textarea, select')) return // 입력칸 안 글자 고르기는 그대로
    const W = box.current?.clientWidth ?? 1
    const s: Drag = { id: e.pointerId, x0: e.clientX, y0: e.clientY, lastX: e.clientX, lastT: e.timeStamp, vel: 0, axis: null }
    dragged.current = false
    const move = (ev: PointerEvent) => {
      if (ev.pointerId !== s.id) return
      const mx = ev.clientX - s.x0, my = ev.clientY - s.y0
      if (!s.axis) {
        if (Math.hypot(mx, my) < 8) return // 이 정도는 탭
        s.axis = Math.abs(mx) > Math.abs(my) ? 'x' : 'y'
        if (s.axis === 'x') { dragged.current = true; window.getSelection()?.removeAllRanges() }
      }
      if (s.axis !== 'x') return
      const dt = Math.max(1, ev.timeStamp - s.lastT)
      s.vel = (ev.clientX - s.lastX) / dt
      s.lastX = ev.clientX; s.lastT = ev.timeStamp
      const edge = (page === 0 && mx > 0) || (page === n - 1 && mx < 0)
      setDx(edge ? Math.sign(mx) * Math.min(W * 0.18, Math.abs(mx) * 0.3) : mx) // 끝에선 고무줄
    }
    const end = (ev: PointerEvent) => {
      if (ev.pointerId !== s.id) return
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', end)
      window.removeEventListener('pointercancel', end)
      if (s.axis === 'x' && ev.type === 'pointerup') {
        const mx = ev.clientX - s.x0
        const go = Math.abs(mx) > W * 0.2 || Math.abs(s.vel) > 0.45 ? -Math.sign(mx || -s.vel) : 0
        const next = Math.min(n - 1, Math.max(0, page + go))
        if (next !== page) onPage(next)
      }
      setDx(null)
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
  // 트랙패드 두 손가락 옆 스크롤·가로 휠(10/12 오너: '옆으로 스크롤해도 안 넘어간다'). 한 번 밀면 한 장,
  // 관성으로 이어지는 휠은 멈출 때까지 무시한다. 끝 장에선 살짝 밀렸다 돌아온다.
  const onWheel = (e: React.WheelEvent) => {
    if (Math.abs(e.deltaX) <= Math.abs(e.deltaY)) return // 위아래 스크롤은 장 안에서
    const w = wheel.current, now = e.timeStamp
    if (now < w.lockUntil) { w.lockUntil = now + 180; return }
    if (now - w.last > 200) w.sum = 0
    w.last = now
    w.sum += e.deltaX
    if (Math.abs(w.sum) < 40) return
    const d = Math.sign(w.sum)
    w.sum = 0; w.lockUntil = now + 180
    const next = page + d
    if (next < 0 || next > n - 1) { setDx(-d * 28); setTimeout(() => setDx(null), 120); return }
    onPage(next)
  }

  // 탭 목록: 화살표 키로도 옮긴다(WAI-ARIA tabs)
  const onTabKey = (e: React.KeyboardEvent) => {
    const d = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0
    if (!d) return
    e.preventDefault()
    const next = Math.min(n - 1, Math.max(0, page + d))
    onPage(next)
    document.getElementById(`v4-tab-${next}`)?.focus()
  }

  return (
    <div className="flex min-h-0 flex-col">
      <div role="tablist" aria-label="정보 고르기" onKeyDown={onTabKey} className="flex shrink-0 gap-1 border-b border-line px-4">
        {tabs.map((t, i) => (
          <button key={t} id={`v4-tab-${i}`} role="tab" type="button" aria-selected={page === i} aria-controls={`v4-panel-${i}`}
            tabIndex={page === i ? 0 : -1} onClick={() => onPage(i)}
            className={`relative min-h-11 flex-1 text-body font-bold ${page === i ? 'text-primary-dark' : 'text-muted hover:text-ink'}`}>
            {t}
            <span aria-hidden className={`absolute inset-x-3 -bottom-px h-[3px] rounded-full ${page === i ? 'bg-primary-dark' : 'bg-transparent'}`} />
          </button>
        ))}
      </div>
      <div ref={box} className="overflow-hidden" style={{ height }} onPointerDown={onPointerDown} onClickCapture={onClickCapture} onWheel={onWheel}>
        <div className={`flex h-full ${dx === null ? 'v4-pager-anim' : ''}`}
          style={{ transform: `translateX(calc(${-page * 100}% + ${dx ?? 0}px))`, touchAction: 'pan-y', userSelect: dx === null ? undefined : 'none' }}>
          {children.map((c, i) => (
            <div key={i} id={`v4-panel-${i}`} role="tabpanel" aria-labelledby={`v4-tab-${i}`} aria-hidden={page !== i}
              ref={(el) => { panels.current[i] = el }} inert={page !== i} onScroll={i === page ? checkMore : undefined}
              style={i === page && more && !noFade.includes(i) ? { maskImage: FADE, WebkitMaskImage: FADE } : undefined}
              className="v4-noscrollbar h-full w-full shrink-0 overflow-y-auto overscroll-contain">
              {c}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
