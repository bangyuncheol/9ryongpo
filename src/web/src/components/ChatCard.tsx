import { useEffect, useRef, useState } from 'react'
import { askStream, TOOL_LABEL } from '../api'
import type { ChatEvent } from '../api'
import Card, { Button } from './Card'
import More from './More'

const QUICK = ['43톤 자망선 언제 와?', '오늘 오징어 있어?', '몇 시에 가면 돼?', '작년 10월 붉은대게 얼마였어?']

const KEEP = 3 // 최근 질문 3개만 보관·표시하고 AI 맥락으로도 보낸다(10/10 결정)

type Turn = { q: string; log: string[]; answer: string | null; mode?: string; error?: string }

export default function ChatCard({ onSubscribe, quick = QUICK, placeholder = '예: 대게 들어오면 알려줘', aside = '숫자는 데이터에서만 가져옵니다', bubbles = false }: {
  onSubscribe: (species: string) => void
  /** 자주 묻는 질문 칩(버전 4는 발표 이야기에 맞춘 네 개, 10/12) */
  quick?: string[]
  placeholder?: string
  /** 제목 옆 안내. 버전 4는 빼고(10/12 오너) 나머지는 그대로 */
  aside?: string | null
  /**
   * 대화 모양(버전 4, 10/12 오너: 쌓이면 '나무위키 읽는 것 같다'). 질문은 오른쪽 색 말풍선, 답은 왼쪽 글.
   * 입력창은 장 아래에 붙여 대화와 갈라 두고, 한 번 물은 뒤엔 자주 묻는 질문을 입력창 위 한 줄로 줄인다.
   */
  bubbles?: boolean
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

  const last = useRef<HTMLDivElement>(null)
  const lastDone = turns[turns.length - 1]?.answer ?? turns[turns.length - 1]?.error
  // 새 질문으로 옮겨 갈 때 이전 대화가 위로 밀려 올라가는 게 보이게(10/13 오너: '딱' 뜨면 이전 대화가 사라진 것 같다).
  // 메신저처럼 대화 끝에 맞추되, 답이 길면 질문이 화면 위로 넘어가지 않게 질문 머리에서 멈춘다. 아래에 빈 자리를
  // 만들지 않는다(10/13 오너: 새 질문 아래 여백이 너무 큼). 답이 붙으면 한 번 더 맞춘다.
  // 브라우저 smooth 는 짧고 기기마다 달라 직접 600ms 로 민다. 움직임 줄이기면 바로.
  useEffect(() => {
    if (!bubbles || !turns.length) return
    const el = last.current
    let sc = el?.parentElement ?? null
    while (sc && !/(auto|scroll)/.test(getComputedStyle(sc).overflowY)) sc = sc.parentElement
    if (!sc || !el) return
    const box = sc
    let id = 0
    id = requestAnimationFrame(() => {
      const from = box.scrollTop
      const head = from + el.getBoundingClientRect().top - box.getBoundingClientRect().top - 12
      const to = Math.max(0, Math.min(head, box.scrollHeight - box.clientHeight))
      if (to <= from + 1) return // 이미 보이거나 위로 되돌릴 필요 없음
      if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) { box.scrollTop = to; return }
      const t0 = performance.now(), D = 600
      const step = (now: number) => {
        const k = Math.min(1, (now - t0) / D)
        box.scrollTop = from + (to - from) * (1 - Math.pow(1 - k, 3)) // 빠르게 출발해 천천히 멈춤
        if (k < 1) id = requestAnimationFrame(step)
      }
      id = requestAnimationFrame(step)
    })
    return () => cancelAnimationFrame(id)
  }, [bubbles, turns.length, lastDone])

  if (bubbles) {
    return (
      <Card id="chat-card" title="물어보기" aside={aside ?? undefined}>
        <div className="space-y-5">
          {turns.map((t, i) => {
            const latest = i === turns.length - 1
            const running = latest && busy && !t.answer && !t.error
            const logOpen = running || openLog === i
            const lookups = t.log.filter((l) => l.startsWith('→')).length
            return (
              <div key={i} ref={latest ? last : undefined} className="scroll-mt-3 space-y-2 text-body">
                <p className="ml-auto w-fit max-w-[85%] rounded-[18px] rounded-br-md bg-primary-soft px-4 py-2.5 text-ink">{t.q}</p>
                <div className="max-w-[95%] space-y-1.5">
                  {t.answer && <p>{t.answer}{t.mode === 'simple' && <span className="ml-1 text-small text-muted">(간단 모드)</span>}</p>}
                  {t.error && <p role="alert" className="text-sub text-arriving">{t.error}</p>}
                  {running && <p className="text-muted" role="status">확인하는 중…</p>}
                  {t.log.length > 0 && (logOpen ? (
                    <pre className="whitespace-pre-wrap rounded-button bg-page px-3 py-2 font-mono text-small text-muted" aria-label="데이터 조회 기록">{t.log.join('\n')}</pre>
                  ) : (
                    <button onClick={() => setOpenLog(i)} className="text-small text-muted underline-offset-2 hover:underline">
                      데이터 {lookups}건 조회 · 기록 보기
                    </button>
                  ))}
                </div>
              </div>
            )
          })}
        </div>
        {turns.length === 0 && (
          <div className="flex flex-wrap gap-2">
            {quick.map((q) => <Button key={q} compact onClick={() => ask(q)} disabled={busy}>{q}</Button>)}
          </div>
        )}
        {/* 입력 칸: 장 아래에 붙어 대화와 갈린다(선 + 바탕). 물은 뒤엔 자주 묻는 질문이 이 위 한 줄로 */}
        <div className="sticky bottom-0 -mx-5 mt-4 border-t border-line bg-card px-5 pb-3 pt-3">
          {turns.length > 0 && (
            <div className="v4-noscrollbar -mx-5 mb-2 flex gap-2 overflow-x-auto px-5">
              {quick.map((q) => <Button key={q} compact onClick={() => ask(q)} disabled={busy} className="shrink-0 whitespace-nowrap">{q}</Button>)}
            </div>
          )}
          <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); ask(input) }}>
            <label htmlFor="chat-input" className="sr-only">질문</label>
            <input id="chat-input" value={input} onChange={(e) => setInput(e.target.value)} maxLength={300}
              placeholder={placeholder}
              className="min-h-[var(--spacing-touch)] min-w-0 flex-1 rounded-button border border-line bg-card px-4 text-body text-ink placeholder:text-muted focus:border-primary focus:outline-none" />
            <Button emphasis="high" disabled={busy || !input.trim()}>묻기</Button>
          </form>
        </div>
      </Card>
    )
  }

  return (
    <Card id="chat-card" title="물어보기" aside={aside ?? undefined}>
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
