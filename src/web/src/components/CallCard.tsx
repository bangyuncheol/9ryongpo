import { TOOL_LABEL } from '../api'
import type { CallState } from '../api'
import Card from './Card'

/*
 * 실시간 통화 내역(설계 §4.3). 전화 알림이 걸리면 오가는 말과 데이터 조회 기록을 그대로 보여 준다.
 * 발표장에서는 폰 소리가 잘 안 들리므로 화면으로 통화를 따라가게 한다. 통화가 없으면 카드를 숨긴다.
 */
const STATUS: Record<string, string> = {
  dialing: '전화 거는 중', 'in-progress': '통화 중', completed: '통화 끝남',
  'no-answer': '받지 않음', busy: '통화 중이라 연결 안 됨', rejected: '거절됨', canceled: '취소됨', failed: '연결 실패',
}
const WHO = { ai: '배마중', user: '상대방' } as const

export default function CallCard({ call }: { call: CallState | null }) {
  if (!call?.enabled || (call.status === 'idle' && call.lines.length === 0)) return null
  const status = STATUS[call.status] ?? call.status
  return (
    <Card id="call" title="실시간 통화 내역" aside={call.who ? `${call.direction === 'inbound' ? '걸려 온 전화' : '건 전화'} · ${call.who}` : undefined}>
      <p role="status" className={`mb-3 text-sub font-bold ${call.active ? 'text-arriving' : 'text-muted'}`}>
        {call.active ? '● ' : ''}{status}{call.duration ? ` · ${call.duration}초` : ''}
      </p>
      <ol className="space-y-2 text-body" aria-live="polite">
        {call.lines.map((l, i) => {
          if (l.role === 'tool') {
            const at = l.text.indexOf(': ')
            const name = at > 0 ? l.text.slice(0, at) : l.text
            return (
              <li key={i} className="rounded-button bg-primary-soft px-3 py-1.5 font-mono text-small text-muted">
                → {TOOL_LABEL[name] ?? name}{at > 0 ? `: ${l.text.slice(at + 2)}` : ''}
              </li>
            )
          }
          return (
            <li key={i}>
              <span className={`mr-2 text-sub font-bold ${l.role === 'ai' ? 'text-primary-dark' : 'text-ink'}`}>{WHO[l.role]}</span>
              {l.text}
            </li>
          )
        })}
      </ol>
    </Card>
  )
}
