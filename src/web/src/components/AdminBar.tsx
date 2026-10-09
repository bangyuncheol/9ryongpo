import { useState } from 'react'
import { adminPost } from '../api'
import type { Clock } from '../api'
import { Button } from './Card'

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
  return (
    <div className="mx-[var(--spacing-side)] flex flex-wrap items-center gap-2 rounded-card border border-dashed border-line bg-card p-3 text-small">
      <span className="font-bold">진행</span>
      <input aria-label="관리자 토큰" type="password" value={token} onChange={(e) => save(e.target.value)}
        placeholder="관리자 토큰" className="min-h-9 w-28 rounded-button border border-line bg-card px-3 text-ink" />
      <Button compact onClick={() => run('/api/sim/seek?t=03:00')}>03:00</Button>
      <Button compact onClick={() => run('/api/sim/seek?t=03:10')}>03:10</Button>
      <Button compact onClick={() => run('/api/sim/play?speed=60')}>재생 60배</Button>
      <Button compact onClick={() => run('/api/sim/play?speed=300')}>재생 300배</Button>
      <Button compact onClick={() => run('/api/sim/pause')}>일시정지</Button>
      <Button compact onClick={() => run(`/api/sim/feed?mode=${feed === 'sim' ? 'live' : 'sim'}`)}>
        {feed === 'sim' ? '실데이터로 전환' : '시뮬레이션으로 전환'}
      </Button>
      <Button compact onClick={() => run('/api/push/test')}>시험 알림</Button>
      <span className="text-muted">{clock ? `${clock.playing ? '재생' : '정지'} ×${clock.speed}` : ''}</span>
      {msg && <span role="alert" className="text-arriving">{msg}</span>}
    </div>
  )
}
