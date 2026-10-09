import { useState } from 'react'
import { adminPost } from '../api'
import type { Clock } from '../api'

const KEY = 'wipan_admin_token'
const read = () => { try { return localStorage.getItem(KEY) ?? '' } catch { return '' } }

/** 데모 진행용. 주소에 ?admin=1 을 붙였을 때만 보인다. 권한 검사는 서버가 한다. */
export default function AdminBar({ clock, feed }: { clock: Clock | null; feed: string | null }) {
  const [token, setToken] = useState(read)
  const [msg, setMsg] = useState<string | null>(null)
  const run = async (path: string) => {
    try { await adminPost(path, token); setMsg(null) } catch (e) { setMsg(e instanceof Error ? e.message : '실패했습니다.') }
  }
  const save = (v: string) => { setToken(v); try { localStorage.setItem(KEY, v) } catch { /* 저장 못 해도 동작 */ } }
  const btn = 'rounded border border-line bg-card px-2 py-1 text-xs hover:bg-sea-soft'
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-xl border border-dashed border-sim bg-card p-2 text-xs">
      <span className="font-bold text-sim">진행</span>
      <input aria-label="관리자 토큰" type="password" value={token} onChange={(e) => save(e.target.value)}
        placeholder="관리자 토큰" className="w-28 rounded border border-line px-2 py-1" />
      <button className={btn} onClick={() => run('/api/sim/seek?t=03:00')}>03:00</button>
      <button className={btn} onClick={() => run('/api/sim/seek?t=03:10')}>03:10</button>
      <button className={btn} onClick={() => run('/api/sim/play?speed=60')}>▶ 60배</button>
      <button className={btn} onClick={() => run('/api/sim/play?speed=300')}>▶ 300배</button>
      <button className={btn} onClick={() => run('/api/sim/pause')}>❚❚</button>
      <button className={btn} onClick={() => run(`/api/sim/feed?mode=${feed === 'sim' ? 'live' : 'sim'}`)}>
        {feed === 'sim' ? '실데이터로 전환' : '시뮬레이션으로 전환'}
      </button>
      <button className={btn} onClick={() => run('/api/push/test')}>시험 알림</button>
      <span className="text-muted">{clock ? `${clock.playing ? '재생' : '정지'} ×${clock.speed}` : ''}</span>
      {msg && <span role="alert" className="text-arriving">{msg}</span>}
    </div>
  )
}
