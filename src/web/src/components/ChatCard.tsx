import { useState } from 'react'
import { askStream, TOOL_LABEL } from '../api'
import type { ChatEvent } from '../api'
import Card, { Button } from './Card'
import More from './More'

const QUICK = ['43톤 자망선 언제 와?', '오늘 오징어 있어?', '몇 시에 가면 돼?', '작년 10월 붉은대게 얼마였어?']

const KEEP = 3 // 최근 질문 3개만 보관·표시하고 AI 맥락으로도 보낸다(10/10 결정)

type Turn = { q: string; log: string[]; answer: string | null; mode?: string; error?: string }

export default function ChatCard({ onSubscribe, quick = QUICK, placeholder = '예: 대게 들어오면 알려줘' }: {
  onSubscribe: (species: string) => void
  /** 자주 묻는 질문 칩(버전 4는 발표 이야기에 맞춘 네 개, 10/12) */
  quick?: string[]
  placeholder?: string
}) {
  const [input, setInput] = useState('')
  const [turns, setTurns] = useState<Turn[]>([])
  const [busy, setBusy] = useState(false)
  const [showOld, setShowOld] = useState(false)
  const [openLog, setOpenLog] = useState<number | null>(null)

  const ask = async (q: string) => {
    const text = q.trim()
    if (!text || busy) return
    setBusy(true); setInput(''); setShowOld(false); setOpenLog(null)
    const history = turns.filter((t) => t.answer).slice(-(KEEP - 1)).map((t) => ({ q: t.q, a: t.answer as string }))
    setTurns((t) => [...t, { q: text, log: [], answer: null }].slice(-KEEP))
    const patch = (f: (t: Turn) => Turn) => setTurns((ts) => ts.map((t, i) => (i === ts.length - 1 ? f(t) : t)))
    await askStream(text, history, (e: ChatEvent) => {
      if (e.type === 'tool') patch((t) => ({ ...t, log: [...t.log, `→ ${TOOL_LABEL[e.name] ?? e.name}`] }))
      else if (e.type === 'tool_result') patch((t) => ({ ...t, log: [...t.log, `  ${TOOL_LABEL[e.name] ?? e.name}: ${e.summary}`] }))
      else if (e.type === 'action') onSubscribe(e.species)
      else if (e.type === 'answer') patch((t) => ({ ...t, answer: e.text, mode: e.mode }))
      else if (e.type === 'error') patch((t) => ({ ...t, error: e.message }))
    })
    setBusy(false)
  }

  return (
    <Card id="chat-card" title="물어보기" aside="숫자는 데이터에서만 가져옵니다">
      {/* 최근 질문 하나만 펼친다. 조회 기록은 답을 만드는 동안만 흐르고, 답이 나오면 한 줄로 접힌다. */}
      <More open={showOld} hidden={turns.length - 1} label="이전 질문" onToggle={() => setShowOld(!showOld)} />
      <div className="space-y-4">
        {turns.map((t, i) => {
          const latest = i === turns.length - 1
          if (!latest && !showOld) return null
          const running = latest && busy && !t.answer && !t.error
          const logOpen = running || openLog === i
          const lookups = t.log.filter((l) => l.startsWith('→')).length
          return (
            <div key={i} className={`space-y-1.5 text-body ${latest ? '' : 'opacity-80'}`}>
              <p className="font-bold">{t.q}</p>
              {t.log.length > 0 && (logOpen ? (
                <pre className="whitespace-pre-wrap rounded-button bg-primary-soft px-3 py-2 font-mono text-small text-muted" aria-label="데이터 조회 기록">{t.log.join('\n')}</pre>
              ) : (
                <button onClick={() => setOpenLog(i)} className="text-small text-muted underline-offset-2 hover:underline">
                  데이터 {lookups}건 조회 · 기록 보기
                </button>
              ))}
              {t.answer && <p>{t.answer}{t.mode === 'simple' && <span className="ml-1 text-small text-muted">(간단 모드)</span>}</p>}
              {t.error && <p role="alert" className="text-sub text-arriving">{t.error}</p>}
              {running && <p className="text-muted" role="status">확인하는 중…</p>}
            </div>
          )
        })}
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        {quick.map((q) => (
          <Button key={q} compact onClick={() => ask(q)} disabled={busy}>{q}</Button>
        ))}
      </div>
      <form className="mt-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); ask(input) }}>
        <label htmlFor="chat-input" className="sr-only">질문</label>
        <input id="chat-input" value={input} onChange={(e) => setInput(e.target.value)} maxLength={300}
          placeholder={placeholder}
          className="min-h-[var(--spacing-touch)] min-w-0 flex-1 rounded-button border border-line bg-card px-4 text-body text-ink placeholder:text-muted focus:border-primary focus:outline-none" />
        <Button emphasis="high" disabled={busy || !input.trim()}>묻기</Button>
      </form>
    </Card>
  )
}
