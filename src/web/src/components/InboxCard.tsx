import { hhmm } from '../api'
import Card from './Card'

/** 화면 안 알림함. 폰 푸시가 늦거나 막혀도 같은 내용을 여기서 본다(설계 §11). */
export default function InboxCard({ items }: { items: { vts: string; title: string; body: string }[] }) {
  if (items.length === 0) return null
  return (
    <Card title="알림함" aside="보낸 입항 알림">
      <ul className="space-y-1.5">
        {items.map((n) => (
          <li key={n.vts + n.body} className="text-sm">
            <span className="mr-2 tabular-nums text-muted">{hhmm(n.vts)}</span>{n.body}
          </li>
        ))}
      </ul>
    </Card>
  )
}
