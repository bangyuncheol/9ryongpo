import { hhmm } from '../api'
import Card from './Card'

/** 화면 안 알림함. 폰 푸시가 늦거나 막혀도 같은 내용을 여기서 본다(설계 §11). */
export default function InboxCard({ items }: { items: { vts: string; title: string; body: string }[] }) {
  if (items.length === 0) return null
  return (
    <Card id="inbox" title="알림함" aside="보낸 입항 알림">
      <ul className="space-y-2">
        {items.map((n) => (
          <li key={n.vts + n.body} className="flex gap-3 text-sub">
            <span className="shrink-0 font-bold tabular-nums text-primary-dark">{hhmm(n.vts)}</span>
            <span>{n.body}</span>
          </li>
        ))}
      </ul>
    </Card>
  )
}
