import { useEffect, useRef, useState } from 'react'
import { hhmm } from '../api'
import Icon from './Icon'

/** 새 입항 알림이 나가는 순간을 보이게: 위에서 내려오는 띠(6초). 처음 불러온 목록은 띄우지 않는다. */
export default function Toast({ items }: { items: { vts: string; body: string }[] | null }) {
  const seen = useRef<Set<string> | null>(null)
  const [show, setShow] = useState<{ vts: string; body: string } | null>(null)
  useEffect(() => {
    if (items === null) return // 아직 못 불러왔으면 기준을 잡지 않는다(열자마자 기존 알림이 뜨던 문제)
    const keys = items.map((n) => n.vts + n.body)
    if (seen.current === null) { seen.current = new Set(keys); return }
    const fresh = items.find((n) => !seen.current!.has(n.vts + n.body))
    keys.forEach((k) => seen.current!.add(k))
    if (fresh) setShow(fresh)
  }, [items])
  useEffect(() => { // 타이머는 띠가 바뀔 때만 다시 건다(3초 폴링마다 취소되지 않게)
    if (!show) return
    const id = setTimeout(() => setShow(null), 6000)
    return () => clearTimeout(id)
  }, [show])
  if (!show) return null
  return (
    <div role="status" className="v2-toast fixed inset-x-0 top-0 z-50 mx-auto max-w-xl px-4 pt-3">
      <div className="v2-shadow flex gap-3 rounded-card bg-card p-4">
        <span aria-hidden className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-[var(--color-sunrise-soft)] text-arriving"><Icon name="bell" /></span>
        <div>
          {/* 화면 안 띠는 푸시 신청과 상관없이 누구에게나 뜬다 → '보냈어요'가 아니라 소식으로(10/11 오너) */}
          <p className="text-sub font-bold text-arriving">새 입항 소식 <span className="font-medium tabular-nums text-muted">· {hhmm(show.vts)}</span></p>
          <p className="mt-1 text-body">{show.body}</p>
        </div>
      </div>
    </div>
  )
}
