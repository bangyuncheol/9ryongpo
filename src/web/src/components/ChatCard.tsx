import { useState } from 'react'
import { askStream } from '../api'
import type { ChatEvent } from '../api'
import Card from './Card'

const TOOL_LABEL: Record<string, string> = {
  get_arrival_forecast: '입항 예보 조회', get_species_estimate: '어종 추정', get_traffic_now: '위판장 앞 교통 조회',
  recommend_visit_time: '방문 시각 계산', get_past_auction: '과거 경매 실적 조회', subscribe: '알림 준비', llm: 'AI',
}
const QUICK = ['43톤 자망선 언제 와?', '오늘 오징어 있어?', '몇 시에 가면 돼?', '작년 10월 붉은대게 얼마였어?']

type Turn = { q: string; log: string[]; answer: string | null; mode?: string; error?: string }

export default function ChatCard({ onSubscribe }: { onSubscribe: (species: string) => void }) {
  const [input, setInput] = useState('')
  const [turns, setTurns] = useState<Turn[]>([])
  const [busy, setBusy] = useState(false)

  const ask = async (q: string) => {
    const text = q.trim()
    if (!text || busy) return
    setBusy(true); setInput('')
    setTurns((t) => [...t, { q: text, log: [], answer: null }])
    const patch = (f: (t: Turn) => Turn) => setTurns((ts) => ts.map((t, i) => (i === ts.length - 1 ? f(t) : t)))
    await askStream(text, (e: ChatEvent) => {
      if (e.type === 'tool') patch((t) => ({ ...t, log: [...t.log, `→ ${TOOL_LABEL[e.name] ?? e.name}`] }))
      else if (e.type === 'tool_result') patch((t) => ({ ...t, log: [...t.log, `  ${TOOL_LABEL[e.name] ?? e.name}: ${e.summary}`] }))
      else if (e.type === 'action') onSubscribe(e.species)
      else if (e.type === 'answer') patch((t) => ({ ...t, answer: e.text, mode: e.mode }))
      else if (e.type === 'error') patch((t) => ({ ...t, error: e.message }))
    })
    setBusy(false)
  }

  return (
    <Card title="물어보기" aside="숫자는 데이터에서만 가져옵니다">
      <div className="space-y-3">
        {turns.map((t, i) => (
          <div key={i} className="space-y-1 text-sm">
            <p className="font-medium">Q. {t.q}</p>
            {t.log.length > 0 && (
              <pre className="whitespace-pre-wrap rounded bg-sea-soft p-2 font-mono text-xs text-muted">{t.log.join('\n')}</pre>
            )}
            {t.answer && <p>{t.answer}{t.mode === 'simple' && <span className="ml-1 text-xs text-muted">(간단 모드)</span>}</p>}
            {t.error && <p role="alert" className="text-arriving">{t.error}</p>}
            {!t.answer && !t.error && busy && i === turns.length - 1 && <p className="text-muted">확인하는 중…</p>}
          </div>
        ))}
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {QUICK.map((q) => (
          <button key={q} onClick={() => ask(q)} disabled={busy}
            className="rounded-full border border-line px-3 py-1 text-xs hover:bg-sea-soft disabled:opacity-50">{q}</button>
        ))}
      </div>
      <form className="mt-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); ask(input) }}>
        <label htmlFor="chat-input" className="sr-only">질문</label>
        <input id="chat-input" value={input} onChange={(e) => setInput(e.target.value)} maxLength={300}
          placeholder="예: 대게 들어오면 알려줘" className="flex-1 rounded-lg border border-line px-3 py-2 text-sm" />
        <button disabled={busy || !input.trim()} className="rounded-lg bg-sea px-4 py-2 text-sm font-bold text-white disabled:opacity-50">묻기</button>
      </form>
    </Card>
  )
}
